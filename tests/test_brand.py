import struct
from pathlib import Path
import pytest
from homeassistant.loader import async_get_integration
from homeassistant.components.brands import _read_brand_file
from homeassistant.components.brands.const import ALLOWED_IMAGES


@pytest.mark.asyncio
async def test_local_brand_is_detected_and_serves_all_theme_variants(hass):
    integration = await async_get_integration(hass, 'u1_companion')
    assert integration.has_branding
    folder = Path(__file__).parents[1] / 'custom_components/u1_companion/brand'
    for image in ALLOWED_IMAGES:
        data = _read_brand_file(folder, image)
        assert data.startswith(b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', data[16:24])
        assert width == height and width in (256, 512)
    assert struct.unpack('>II', _read_brand_file(folder, 'icon@2x.png')[16:24]) == (512, 512)


@pytest.mark.asyncio
async def test_logo_repair_keeps_name_records_custom_headers_and_other_dashboards(hass):
    from copy import deepcopy
    from unittest.mock import patch
    from homeassistant.components.lovelace.const import LOVELACE_DATA
    from homeassistant.helpers.storage import Store
    from test_auto_dashboard import start_ui, _dashboard_collection
    from custom_components.u1_companion.dashboard_config import BANNER_LOGO
    from custom_components.u1_companion.auto_dashboard import async_restore_logo
    await start_ui(hass)
    with patch('custom_components.u1_companion.config_flow.async_discover', return_value={
        'port': 7125, 'hours': 2.0, 'moonraker_version': 'test'}), patch(
        'custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0):
        result = await hass.config_entries.flow.async_init('u1_companion', context={'source': 'user'},
            data={'host': '192.168.1.50', 'name': 'Atelier', 'start_date': '2026-10-30'})
        await hass.async_block_till_done()
        entry = result['result']
        path = entry.options['dashboard_path']
        dashboard = hass.data[LOVELACE_DATA].dashboards[path]
        config = await dashboard.async_load(False)
        banner = config['views'][0]['sections'][0]['cards'][0]
        assert banner['content'].startswith(BANNER_LOGO)
        assert 'printer_name' in banner['content']
        banner['content'] = banner['content'].removeprefix(BANNER_LOGO + '\n\n')
        old = deepcopy(config)
        maintenance = deepcopy(entry.runtime_data.state)
        await dashboard.async_save(old)
        options = dict(entry.options)
        options.pop('banner_logo_version', None)
        hass.config_entries.async_update_entry(entry, options=options)
        await async_restore_logo(hass, entry)
        repaired = await dashboard.async_load(False)
        assert repaired['views'][0]['sections'][0]['cards'][0]['content'] == BANNER_LOGO + '\n\n' + banner['content']
        assert repaired['views'][0]['sections'][1:] == old['views'][0]['sections'][1:]
        assert repaired['views'][1:] == old['views'][1:]
        assert entry.runtime_data.state == maintenance
        assert await Store(hass, 1, f'u1_companion.{entry.entry_id}.dashboard_before_042').async_load() == old
        repaired['views'][0]['sections'][0]['cards'][0]['content'] = 'Mon bandeau personnalisé'
        await dashboard.async_save(repaired)
        hass.config_entries.async_update_entry(entry, options=options)
        await async_restore_logo(hass, entry)
        assert await dashboard.async_load(False) == repaired
        collection = _dashboard_collection(hass)
        await collection.async_create_item({'url_path': 'lemyo-hub', 'title': 'LEMYO Hub',
            'show_in_sidebar': True, 'require_admin': False, 'mode': 'storage'})
        hub = hass.data[LOVELACE_DATA].dashboards['lemyo-hub']
        await hub.async_save(old)
        hass.config_entries.async_update_entry(entry, options={**options, 'dashboard_path': 'lemyo-hub'})
        await async_restore_logo(hass, entry)
        assert await hub.async_load(False) == old
        assert entry.runtime_data.state == maintenance
