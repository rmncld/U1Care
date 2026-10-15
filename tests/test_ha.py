"""Real HA flow manager, platforms, state machine and persistent Store."""

from unittest.mock import AsyncMock, patch
import json

import pytest

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState

from custom_components.u1_companion.api import CannotConnect, InvalidAuth
from custom_components.u1_companion.const import DOMAIN
from custom_components.u1_companion.api import Unsupported

FOUND = {"port": 7125, "hours": 2.0, "moonraker_version": "simulated-u1"}


@pytest.mark.asyncio
async def test_real_setup_ip_only_entities_and_duplicate(hass):
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] == "form"
        assert len(result["data_schema"].schema) == 1
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.50"})
        assert result["type"] == "create_entry"
        entry = result["result"]
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED
        assert entry.runtime_data.state["machine"]["startDate"] is None
        entities = [e for e in hass.states.async_all() if "u1_care" in e.entity_id]
        assert len(entities) == 10
        assert any(e.state == "2.0" for e in entities)
        assert any(e.state == "INCONNU" for e in entities)
        duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.50"})
        assert duplicate["type"] == "abort" and duplicate["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_real_forms_offline_persistence_and_import(hass):
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.51"})
        entry = result["result"]
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        today = coordinator.today()
        options = await hass.config_entries.options.async_init(entry.entry_id)
        assert options["type"] == "menu"
        options = await hass.config_entries.options.async_configure(options["flow_id"], {"next_step_id": "maintenance"})
        options = await hass.config_entries.options.async_configure(options["flow_id"], {"task_id": "carbon-rods"})
        assert options["step_id"] == "complete"
        bad = {"completed_day": today, "step_1": False, "step_2": True, "step_3": True, "note": "test"}
        refused = await hass.config_entries.options.async_configure(options["flow_id"], bad)
        assert refused["errors"]["base"] == "check_all_steps"
        accepted = await hass.config_entries.options.async_configure(options["flow_id"], {**bad, "step_1": True})
        assert accepted["type"] == "create_entry"
        assert len(coordinator.state["history"]) == 1
        assert coordinator.state["tasks"][0]["lastDate"] is None
        with patch("custom_components.u1_companion.api.U1Api.async_hours", side_effect=CannotConnect()):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert coordinator.data["connected"] is False
            assert coordinator.data["hours"] is None
            assert coordinator.data["tasks"]["carbon-rods"]["level"] == "ok"
            backup = json.loads(json.dumps(coordinator.state))
            await coordinator.async_import(backup)
            assert len(coordinator.state["history"]) == 1
            assert coordinator.state["connection"]["url"] == ""
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            assert len(entry.runtime_data.state["history"]) == 1
            assert entry.runtime_data.data["tasks"]["carbon-rods"]["level"] == "ok"


@pytest.mark.asyncio
async def test_real_auth_step_and_cannot_connect(hass):
    with patch("custom_components.u1_companion.config_flow.async_discover", side_effect=InvalidAuth()):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.52"})
        assert result["step_id"] == "auth"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": "wrong"})
        assert result["errors"]["base"] == "invalid_auth"
    with patch("custom_components.u1_companion.config_flow.async_discover", side_effect=CannotConnect()):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.53"})
        assert result["step_id"] == "user" and result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_real_reference_counters_signal_store_failure_and_diagnostics(hass):
    from custom_components.u1_companion.diagnostics import async_get_config_entry_diagnostics
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.54"})
        entry = result["result"]
        await hass.async_block_till_done()
        c = entry.runtime_data
        async def menu(step):
            f = await hass.config_entries.options.async_init(entry.entry_id)
            return await hass.config_entries.options.async_configure(f["flow_id"], {"next_step_id": step})
        reference = await menu("reference")
        saved = await hass.config_entries.options.async_configure(reference["flow_id"], {"start_date": c.today()})
        assert saved["type"] == "create_entry"
        assert c.data["tasks"]["carbon-rods"]["level"] == "ok"
        signal = await menu("signal")
        await hass.config_entries.options.async_configure(signal["flow_id"], {"active": True})
        assert c.data["overall"]["level"] == "due"
        counters = await menu("counters")
        await hass.config_entries.options.async_configure(counters["flow_id"], {"hours": 20, "swaps": 98000})
        assert c.state["connection"]["enabled"] is False
        await c.async_refresh()
        assert c.data["hours"] == 20
        assert c.data["tasks"]["pogo-contacts"]["level"] == "soon"
        before = json.loads(json.dumps(c.state))
        with patch.object(c.store, "async_save", side_effect=OSError("simulated disk failure")):
            with pytest.raises(OSError):
                await c.async_reference("2026-01-01")
        assert c.state == before
        with pytest.raises(ValueError):
            await c.async_import({"schemaVersion": 99})
        assert c.state == before
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert "192.168.1.54" not in json.dumps(diagnostics)
        assert "api_key" not in json.dumps(diagnostics)
        resume = await menu("resume")
        await hass.config_entries.options.async_configure(resume["flow_id"], {"confirm": True})
        assert c.state["connection"]["enabled"] is True
        assert c.data["hours"] == 2


@pytest.mark.asyncio
async def test_real_reconfigure_keeps_entry_events_and_entities(hass):
    from homeassistant.config_entries import SOURCE_RECONFIGURE
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.55"})
        entry = result["result"]
        await hass.async_block_till_done()
        c = entry.runtime_data
        await c.async_complete("xyz-calibration", [True, True], "keep me", c.today())
        entity_ids = {s.entity_id for s in hass.states.async_all()}
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.56"})
        assert result["type"] == "abort" and result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert entry.data["host"] == "192.168.1.56"
        assert entry.title == "U1 Care · 192.168.1.56"
        assert entry.runtime_data.state["history"][0]["note"] == "keep me"
        assert {s.entity_id for s in hass.states.async_all()} == entity_ids


@pytest.mark.asyncio
async def test_real_auth_recovery_invalid_host_and_unsupported(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "not-an-ip"})
    assert result["errors"]["host"] == "invalid_host"
    with patch("custom_components.u1_companion.config_flow.async_discover", side_effect=Unsupported()):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.57"})
        assert result["errors"]["base"] == "unsupported"
    with patch("custom_components.u1_companion.config_flow.async_discover", side_effect=InvalidAuth()):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.57"})
        assert result["step_id"] == "auth"
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND) as discover, patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": "local-printer-key"})
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert discover.call_args.args[2] == "local-printer-key"


@pytest.mark.asyncio
async def test_real_history_reset_requires_explicit_resume(hass):
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=100.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.58"})
        entry = result["result"]
        await hass.async_block_till_done()
        c = entry.runtime_data
        task = c.state["tasks"][0]
        await c.async_complete(task["id"], [True] * len(task["steps"]), "before reset", c.today())
        with patch("custom_components.u1_companion.api.U1Api.async_hours", return_value=1.0):
            await c.async_refresh()
            assert c.data["hours"] is None and c.error == "history_reset"
            assert c.state["machine"]["hours"] == 100
            menu = await hass.config_entries.options.async_init(entry.entry_id)
            form = await hass.config_entries.options.async_configure(menu["flow_id"], {"next_step_id": "resume"})
            rejected = await hass.config_entries.options.async_configure(form["flow_id"], {"confirm": False})
            assert rejected["errors"]["base"] == "confirm_required"
            await hass.config_entries.options.async_configure(form["flow_id"], {"confirm": True})
            assert c.data["hours"] == 1
            assert c.state["history"][0]["hours"] == 100
            assert c.state["tasks"][0]["lastHours"] is None
            assert c.state["tasks"][0]["previousHistoryLastHours"] == 100
            assert c.data["tasks"][task["id"]]["level"] == "ok"


@pytest.mark.asyncio
async def test_real_corrupt_store_not_replaced(hass):
    with patch("custom_components.u1_companion.config_flow.async_discover", return_value=FOUND), patch(
        "custom_components.u1_companion.api.U1Api.async_hours", return_value=2.0):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}, data={"host": "192.168.1.59"})
        entry = result["result"]
        await hass.async_block_till_done()
        store = entry.runtime_data.store
        await store.async_save({"schemaVersion": 99, "marker": "preserve-corrupt-file"})
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        stored = await store.async_load()
        assert stored == {"schemaVersion": 99, "marker": "preserve-corrupt-file"}

