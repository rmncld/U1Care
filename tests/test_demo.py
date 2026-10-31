from conftest import legacy_demo
from unittest.mock import patch
import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from custom_components.u1_companion.const import DOMAIN


@pytest.mark.asyncio
async def test_demo_without_network_persists_and_stays_separate(hass):
    with patch('custom_components.u1_companion.config_flow.async_discover', side_effect=AssertionError('No demo discovery')), patch('custom_components.u1_companion.api.U1Api.async_hours', side_effect=AssertionError('No demo polling')):
        result = await legacy_demo(hass)
        entry = result['result']
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED
        c = entry.runtime_data
        assert c.api is None and c.data['demo'] is True
        assert c.data['hours'] == 1200 and c.data['connected'] is False
        assert 'DÉMONSTRATION' in entry.title
        assert len(hass.states.async_all()) == 15
        assert {'ok', 'soon', 'due'} <= {t['level'] for t in c.data['tasks'].values()}
        task = c.catalog['tasks'][0]
        await c.async_complete(task['id'], [True] * len(task['steps']), 'Essai démo', c.today())
        backup = c.state
        assert len(backup['history']) == 1
        c.demo = False
        with pytest.raises(ValueError, match='Simulated'):
            await c.async_import(backup)
        c.demo = True
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(entry.runtime_data.state['history']) == 1
        result = await hass.config_entries.flow.async_init(DOMAIN, context={'source': 'reconfigure', 'entry_id': entry.entry_id})
        assert result['type'] == 'abort' and result['reason'] == 'demo_separate'
