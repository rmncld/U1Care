"""Tests against installed HA Core, isolated configuration and simulated U1."""

import sys
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
    device_registry.async_setup(instance)
    await device_registry.async_load(instance)
    await entity_registry.async_load(instance)
    await instance.config_entries.async_initialize()
    # Host networking is not bootstrapped in this headless Core test harness.
    # Only its HTTP-session provider is substituted; flows/platforms/store are real.
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver())) as session:
        with patch("custom_components.u1_companion.config_flow.async_get_clientsession", return_value=session), patch(
            "custom_components.u1_companion.coordinator.async_get_clientsession", return_value=session):
            yield instance
    await instance.async_stop(force=True)
    instance.import_executor.shutdown(wait=True)
