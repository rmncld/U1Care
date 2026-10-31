from conftest import legacy_demo
from unittest.mock import patch
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.exceptions import HomeAssistantError
from custom_components.u1_companion.const import DOMAIN


@pytest.mark.asyncio
async def test_dashboard_validation_targets_one_item_and_persists(hass):
    result = await legacy_demo(hass)
    await hass.async_block_till_done()
    entry = result['result']
    c = entry.runtime_data
    entity = next(s for s in hass.states.async_all() if s.attributes.get('frequency') == 'Mensuel')
    before = {t['id']: t['lastDate'] for t in c.state['tasks']}
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, 'complete_maintenance', {'entity_id': entity.entity_id, 'confirmed': False}, blocking=True)
    assert c.state['history'] == []
    await hass.services.async_call(DOMAIN, 'complete_maintenance', {'entity_id': entity.entity_id, 'confirmed': True}, blocking=True)
    await hass.async_block_till_done()
    event = c.state['history'][0]
    assert event['date'][:10] == c.today()
    assert hass.states.get(entity.entity_id).attributes['event_count'] == 1
    assert sum(t['lastDate'] != before[t['id']] for t in c.state['tasks']) == 1
    with patch.object(c.store, 'async_save', side_effect=OSError('disk')):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(DOMAIN, 'complete_maintenance', {'entity_id': entity.entity_id, 'confirmed': True}, blocking=True)
    assert len(c.state['history']) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.runtime_data.state['history']) == 1


@pytest.mark.asyncio
async def test_portable_dashboard_uses_registered_entities_and_user_path(hass):
    from custom_components.u1_companion.dashboard_config import async_dashboard_config
    import json
    result = await legacy_demo(hass)
    await hass.async_block_till_done()
    entry = result['result']
    config = await async_dashboard_config(hass, entry)
    text = json.dumps(config)
    assert '__ENTITY_' not in text and '__DASHBOARD_PATH__' not in text
    assert 'demonstration_' in text
    assert len(config['views']) == 8
    assert all(v['subview'] for v in config['views'][1:])
    for view in config['views'][1:]:
        action = view['sections'][0]['cards'][1]['tap_action']
        assert action['perform_action'] == DOMAIN + '.complete_maintenance'
        assert action['confirmation']['text']
        assert hass.states.get(action['target']['entity_id']) is not None
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    form = await hass.config_entries.options.async_configure(flow['flow_id'], {'next_step_id': 'dashboard'})
    assert form['step_id'] == 'dashboard'
