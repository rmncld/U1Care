"""Both retained HACS entries and complete HA removal can be installed again."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState

DOMAIN = 'u1_companion'
FOUND = {'port': 7125, 'hours': 2.0, 'moonraker_version': 'test'}


async def add(hass, **data):
    return await hass.config_entries.flow.async_init(DOMAIN, context={'source': 'user'},
        data={'host': '192.168.1.50', 'name': 'Atelier', 'start_date': '2026-10-30', **data})


@pytest.mark.asyncio
async def test_hacs_reinstall_reconnects_retained_entry_without_erasing_records(hass):
    with patch('custom_components.u1_companion.config_flow.async_discover', return_value=FOUND) as discover, patch(
        'custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0):
        result = await add(hass)
        entry = result['result']
        await hass.async_block_till_done()
        task = entry.runtime_data.catalog['tasks'][0]
        await entry.runtime_data.async_complete(task['id'], [True] * len(task['steps']), 'À garder', entry.runtime_data.today())
        stored = deepcopy(entry.runtime_data.state)
        entities = {s.entity_id for s in hass.states.async_all()}
        hass.config_entries.async_update_entry(entry, data={**entry.data, 'api_key': 'existing-key'})
        assert await hass.config_entries.async_unload(entry.entry_id)
        form = await add(hass, name='Nom par défaut à ignorer', start_date='2026-01-01')
        assert form['step_id'] == 'existing'
        refused = await hass.config_entries.flow.async_configure(form['flow_id'], {'confirm': False})
        assert refused['errors']['base'] == 'confirm_required'
        repaired = await hass.config_entries.flow.async_configure(form['flow_id'], {'confirm': True})
        await hass.async_block_till_done()
        assert repaired['type'] == 'abort' and repaired['reason'] == 'reconfigure_successful'
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ConfigEntryState.LOADED
        assert entry.runtime_data.state == stored
        assert entry.title == 'Atelier' and entry.data['api_key'] == 'existing-key'
        assert discover.call_args.args[2] == 'existing-key'
        assert {s.entity_id for s in hass.states.async_all()} == entities


@pytest.mark.asyncio
async def test_full_ha_remove_and_add_again_no_duplicate_dead_end(hass):
    with patch('custom_components.u1_companion.config_flow.async_discover', return_value=FOUND), patch(
        'custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0):
        first = await add(hass)
        await hass.async_block_till_done()
        old_id = first['result'].entry_id
        removed = await hass.config_entries.async_remove(old_id)
        assert not removed['require_restart']
        assert hass.config_entries.async_entries(DOMAIN) == []
        second = await add(hass)
        await hass.async_block_till_done()
        assert second['type'] == 'create_entry'
        assert second['result'].entry_id != old_id
        assert second['result'].state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
