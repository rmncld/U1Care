import json

import pytest

from custom_components.u1_companion.api import (CannotConnect, InvalidAuth, Unsupported,
    U1Api, async_discover, normalize_host, parse_hours)


class Content:
    def __init__(self, body):
        self.body = body

    async def iter_chunked(self, _size):
        yield self.body


class Response:
    def __init__(self, status, body):
        self.status = status
        self.content = Content(body if isinstance(body, bytes) else json.dumps(body).encode())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Session:
    def __init__(self, responder):
        self.calls = []
        self.responder = responder

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responder(url)


def success(url):
    if url.endswith("/info"):
        return Response(200, {"result": {"components": ["history"], "moonraker_version": "test"}})
    return Response(200, {"result": {"job_totals": {"total_print_time": 7200}}})


@pytest.mark.asyncio
async def test_ip_only_detection_and_get_only():
    session = Session(lambda url: Response(404, {}) if ":80/" in url else success(url))
    result = await async_discover(session, "192.168.1.50")
    assert result["port"] == 7125 and result["hours"] == 2
    assert len(session.calls) == 3
    assert all(c[1]["allow_redirects"] is False for c in session.calls)
    assert all(c[0].endswith(("/info", "/totals")) for c in session.calls)


@pytest.mark.asyncio
async def test_auth_key_conditional_and_bounded_hosts():
    session = Session(lambda _: Response(401, {}))
    with pytest.raises(InvalidAuth):
        await async_discover(session, "192.168.1.50")
    session = Session(success)
    await async_discover(session, "192.168.1.50", "existing-secret")
    assert all(c[1]["headers"]["X-Api-Key"] == "existing-secret" for c in session.calls)
    with pytest.raises(ValueError):
        await U1Api(session, "192.168.1.50", 80)._get("/printer/gcode/script")


@pytest.mark.parametrize("host", ["8.8.8.8", "127.0.0.1", "169.254.1.2", "http://192.168.1.50", "192.168.1.50:7125", "example.com", "::1"])
def test_invalid_host(host):
    with pytest.raises(ValueError):
        normalize_host(host)


@pytest.mark.parametrize("value", [True, None, -1, "3600", float("inf"), float("nan")])
def test_invalid_totals(value):
    with pytest.raises(Unsupported):
        parse_hours({"result": {"job_totals": {"total_print_time": value}}})


@pytest.mark.asyncio
async def test_invalid_protocol_responses():
    for response, expected in [(Response(302, {}), CannotConnect),
        (Response(200, b"<html>Fluidd</html>"), Unsupported),
        (Response(200, b"x" * (1024 * 1024 + 1)), Unsupported),
        (Response(200, {"result": {"components": []}}), Unsupported)]:
        with pytest.raises(expected):
            await U1Api(Session(lambda _: response), "192.168.1.50", 80).async_probe()
