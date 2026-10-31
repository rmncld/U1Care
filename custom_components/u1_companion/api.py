"""Bounded, read-only Moonraker access; no commands or firmware changes."""

import asyncio
import ipaddress
import json
import math

import aiohttp

HEADS = ("extruder", "extruder1", "extruder2", "extruder3")


def parse_heads(status):
    """U1Deck model.mjs / diagnostics.mjs: four physical extruder counters."""
    heads = []
    for name in HEADS:
        raw = status.get(name, {}) if isinstance(status, dict) else {}
        if not isinstance(raw, dict):
            raw = {}
        values = {}
        for key in ("switch_count", "last_maintenance_count"):
            value = raw.get(key)
            values[key] = (int(value) if not isinstance(value, bool)
                           and isinstance(value, (int, float)) and math.isfinite(value)
                           and 0 <= value <= 1e9 and int(value) == value else None)
        count, last = values.values()
        heads.append({**values, "since_service": count - last
                      if count is not None and last is not None and count >= last else None})
    return heads


class CannotConnect(Exception):
    """No usable HTTP endpoint."""


class InvalidAuth(CannotConnect):
    """An existing printer credential is required."""


class Unsupported(CannotConnect):
    """Moonraker was found without usable history."""


def normalize_host(value: str) -> str:
    """Accept one private IPv4 address, without credentials or paths."""
    host = str(ipaddress.IPv4Address(value.strip()))
    ip = ipaddress.IPv4Address(host)
    if not any(ip in net for net in (
        ipaddress.IPv4Network("10.0.0.0/8"),
        ipaddress.IPv4Network("172.16.0.0/12"),
        ipaddress.IPv4Network("192.168.0.0/16"),
    )):
        raise ValueError("A private LAN IPv4 address is required")
    return host


def parse_hours(data: dict) -> float:
    """This is retained job history, never a claimed factory lifetime counter."""
    try:
        seconds = data["result"]["job_totals"]["total_print_time"]
    except (KeyError, TypeError) as err:
        raise Unsupported("history_missing") from err
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise Unsupported("history_invalid")
    if not math.isfinite(seconds) or not 0 <= seconds <= 3.6e12:
        raise Unsupported("history_invalid")
    return seconds / 3600


class U1Api:
    """Bounded history GETs and a read-only four-head subscription on one IP."""

    def __init__(self, session, host: str, port: int, api_key: str = ""):
        self.session = session
        self.host = normalize_host(host)
        if port not in (80, 7125):
            raise ValueError("Unsupported port")
        self.port = port
        self.api_key = api_key

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    async def _get(self, route):
        if route not in ("/server/info", "/server/history/totals", "/printer/objects/list"):
            raise ValueError("Read-only endpoint required")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            async with asyncio.timeout(4):
                async with self.session.get(
                    self.url + route, headers=headers, allow_redirects=False
                ) as response:
                    if response.status in (401, 403):
                        raise InvalidAuth("invalid_auth")
                    if response.status != 200:
                        raise CannotConnect("cannot_connect")
                    chunks = []
                    size = 0
                    async for chunk in response.content.iter_chunked(65536):
                        size += len(chunk)
                        if size > 1024 * 1024:
                            raise Unsupported("response_too_large")
                        chunks.append(chunk)
                    data = json.loads(b"".join(chunks))
                    if not isinstance(data, dict):
                        raise Unsupported("invalid_response")
                    return data
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise CannotConnect("cannot_connect") from err
        except (ValueError, UnicodeError) as err:
            raise Unsupported("invalid_response") from err

    async def async_probe(self):
        """Verify the API component; do not infer hardware identity from IP."""
        data = await self._get("/server/info")
        info = data.get("result")
        if not isinstance(info, dict) or not isinstance(info.get("components"), list):
            raise Unsupported("not_moonraker")
        if "history" not in info["components"]:
            raise Unsupported("history_missing")
        hours = await self.async_hours()
        return {"port": self.port, "hours": hours,
                "moonraker_version": str(info.get("moonraker_version", "unknown"))}

    async def async_hours(self):
        return parse_hours(await self._get("/server/history/totals"))

    async def async_heads(self):
        """Same list + subscription handshake as U1Deck; close after one full snapshot.

        No inferred API route, G-code, camera or maintenance reset commands.
        Polling snapshots avoids merging stale fields across reconnects.
        """
        listing = await self._get("/printer/objects/list")
        result = listing.get("result")
        available = result.get("objects") if isinstance(result, dict) else None
        if not isinstance(available, list):
            raise Unsupported("objects_missing")
        objects = {name: None for name in HEADS if name in available}
        if not objects:
            raise Unsupported("heads_missing")
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        try:
            async with asyncio.timeout(6):
                async with self.session.ws_connect(
                    self.url.replace("http://", "ws://", 1) + "/websocket",
                    headers=headers, max_msg_size=1024 * 1024,
                ) as ws:
                    await ws.send_json({"jsonrpc": "2.0", "id": 1,
                                        "method": "printer.objects.subscribe",
                                        "params": {"objects": objects}})
                    for _ in range(32):
                        message = await ws.receive_json()
                        if message.get("id") != 1:
                            continue
                        status = message.get("result", {}).get("status")
                        if "error" in message or not isinstance(status, dict):
                            raise Unsupported("heads_missing")
                        return parse_heads(status)
                    raise Unsupported("heads_missing")
        except aiohttp.WSServerHandshakeError as err:
            if err.status in (401, 403):
                raise InvalidAuth("invalid_auth") from err
            raise CannotConnect("cannot_connect") from err
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise CannotConnect("cannot_connect") from err
        except (ValueError, TypeError, AttributeError) as err:
            raise Unsupported("invalid_response") from err


async def async_discover(session, host: str, api_key: str = ""):
    """Try the web proxy and the documented conventional Moonraker port."""
    host = normalize_host(host)
    auth_error = None
    unsupported = None
    for port in (80, 7125):
        try:
            return await U1Api(session, host, port, api_key).async_probe()
        except InvalidAuth as err:
            auth_error = err
        except Unsupported as err:
            unsupported = err
        except CannotConnect:
            continue
    if auth_error:
        raise auth_error
    if unsupported:
        raise unsupported
    raise CannotConnect("cannot_connect")
