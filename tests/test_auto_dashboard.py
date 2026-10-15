"""Exercise the actual Lovelace collection, storage, panels and edit APIs."""
import json
import pytest
from unittest.mock import patch
from homeassistant.core import CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.config_entries import SOURCE_USER
from homeassistant.components import lovelace, frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA
from custom_components.u1_companion.const import DOMAIN
from custom_components.u1_companion.auto_dashboard import async_ensure_dashboard, _dashboard_collection


async def start_ui(hass):
    assert await lovelace.async_setup(hass, lovelace.CONFIG_SCHEMA({}))
    hass.state = CoreState.running


async def add_demo(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={'source': SOURCE_USER}, data={'demo': True})
    await hass.async_block_till_done()
    return result['result']


@pytest.mark.asyncio
async def test_automatic_creation_edit_restart_and_user_deletion(hass):
    await start_ui(hass)
    entry = await add_demo(hass)
    path = entry.options['dashboard_path']
    dashboard = hass.data[LOVELACE_DATA].dashboards[path]
    config = await dashboard.async_load(False)
    assert len(config['views']) == 8
    assert frontend.async_panel_exists(hass, path)
    collection = _dashboard_collection(hass)
    item = next(i for i in collection.async_items() if i['url_path'] == path)
    assert item['mode'] == 'storage' and item['show_in_sidebar']
    # Use the same storage edit API as the native dashboard editor.
    config['views'][0]['title'] = 'Mon atelier personnalisé'
    await dashboard.async_save(config)
    await collection.async_update_item(item['id'], {'title': 'Ma U1'})
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (await dashboard.async_load(False))['views'][0]['title'] == 'Mon atelier personnalisé'
    assert dashboard.config['title'] == 'Ma U1'
    assert len([i for i in collection.async_items() if i['url_path'] == path]) == 1
    # Flush metadata, then rebuild Lovelace from its actual saved files.
    await collection.store.async_save(collection._data_to_save())
    hass.data[frontend.DATA_PANELS] = {}
    assert await lovelace.async_setup(hass, lovelace.CONFIG_SCHEMA({}))
    dashboard = hass.data[LOVELACE_DATA].dashboards[path]
    collection = _dashboard_collection(hass)
    assert (await dashboard.async_load(False))['views'][0]['title'] == 'Mon atelier personnalisé'
    assert dashboard.config['title'] == 'Ma U1'
    # User deletion remains authoritative, including on the next reload.
    await collection.async_delete_item(item['id'])
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert path not in hass.data[LOVELACE_DATA].dashboards


@pytest.mark.asyncio
async def test_two_printers_separate_and_existing_dashboard_adopted(hass):
    # Existing entries receive dashboards on the next startup too.
    entry = await add_demo(hass)
    await start_ui(hass)
    from custom_components.u1_companion.dashboard_config import async_dashboard_config
    collection = _dashboard_collection(hass)
    await collection.async_create_item({'url_path': 'u1-care', 'title': 'Déjà personnalisé',
        'show_in_sidebar': True, 'require_admin': False, 'mode': 'storage'})
    original = await async_dashboard_config(hass, entry, 'u1-care')
    original['views'][0]['title'] = 'À conserver'
    # Older compact dashboards only referenced entities inside template strings.
    for view in original['views'][1:]:
        del view['sections'][0]['cards'][1]
    await hass.data[LOVELACE_DATA].dashboards['u1-care'].async_save(original)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert entry.options['dashboard_path'] == 'u1-care'
    assert await async_ensure_dashboard(hass, entry) == 'u1-care'
    assert (await hass.data[LOVELACE_DATA].dashboards['u1-care'].async_load(False)) == original
    second = await add_demo(hass)
    second_path = second.options['dashboard_path']
    assert second_path != 'u1-care'
    second_config = await hass.data[LOVELACE_DATA].dashboards[second_path].async_load(False)
    assert second_config != original
    assert json.dumps(second_config, ensure_ascii=False).count('DÉMONSTRATION') > 0
    assert len(collection.async_items()) >= 2


@pytest.mark.asyncio
async def test_interrupted_first_save_can_retry_without_duplicates(hass):
    entry = await add_demo(hass)
    await start_ui(hass)
    from homeassistant.components.lovelace.dashboard import LovelaceStorage
    with patch.object(LovelaceStorage, 'async_save', side_effect=OSError('disk')):
        with pytest.raises(OSError):
            await async_ensure_dashboard(hass, entry)
    assert not entry.options.get('dashboard_initialized')
    path = await async_ensure_dashboard(hass, entry)
    items = _dashboard_collection(hass).async_items()
    assert len([i for i in items if i['url_path'] == path]) == 1
    assert len((await hass.data[LOVELACE_DATA].dashboards[path].async_load(False))['views']) == 8
