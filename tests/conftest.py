"""Tests against installed HA Core, isolated configuration and simulated U1."""

import sys
from pathlib import Path
from unittest.mock import patch
from types import MappingProxyType

import aiohttp
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def legacy_demo(hass):
    """Load an existing v0.3.6 entry; new user flows cannot create demos."""
    from homeassistant.config_entries import ConfigEntry
    entry = ConfigEntry(version=1, minor_version=1, domain='u1_companion',
        title='U1 Care — DÉMONSTRATION', data={'demo': True}, options={},
        source='user', unique_id=None, discovery_keys=MappingProxyType({}), subentries_data=None)
    await hass.config_entries.async_add(entry)
    return {'result': entry}


@pytest_asyncio.fixture
async def hass(tmp_path):
    from homeassistant.core import HomeAssistant
    from homeassistant.config_entries import ConfigEntries
    from homeassistant import loader
    from homeassistant.helpers import frame, device_registry, entity_registry

    instance = HomeAssistant(str(tmp_path))
    frame.async_setup(instance)
    loader.async_setup(instance)
    instance.config_entries = ConfigEntries(instance, {})
    if hasattr(device_registry, "async_setup"):
        device_registry.async_setup(instance)
    await device_registry.async_load(instance)
    await entity_registry.async_load(instance)
    await instance.config_entries.async_initialize()
    # Host networking is not bootstrapped in this headless Core test harness.
    # Only its HTTP-session provider is substituted; flows/platforms/store are real.
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver())) as session:
        with patch("custom_components.u1_companion.config_flow.async_get_clientsession", return_value=session), patch(
            "custom_components.u1_companion.coordinator.async_get_clientsession", return_value=session), patch(
            "custom_components.u1_companion.api.U1Api.async_heads",
            side_effect=__import__('custom_components.u1_companion.api', fromlist=['Unsupported']).Unsupported('heads_missing')):
            yield instance
    await instance.async_stop(force=True)
    instance.import_executor.shutdown(wait=True)
