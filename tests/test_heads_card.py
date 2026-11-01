from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import pytest
from homeassistant.helpers.template import Template
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from custom_components.u1_companion.heads_card import heads_card, async_register_assets
from custom_components.u1_companion.auto_dashboard import async_upgrade_heads_card, _dashboard_collection
from test_auto_dashboard import start_ui, add_demo


@pytest.mark.asyncio
async def test_native_card_four_drawings_counts_and_complete_total(hass):
    entities = [f'sensor.test_t{i}' for i in range(1, 5)]
    for entity, count in zip(entities, [266, 150, 223, 443]):
        hass.states.async_set(entity, count)
    hass.states.async_set('sensor.test_total', 1082)
    card = heads_card(entities, 'sensor.test_total')
    template = Template(card['content'], hass)
    rendered = template.async_render()
    assert rendered.count('<img ') == 1
    assert all(f'T{i} :' in rendered for i in range(1, 5))
    assert '1 082 changements' in rendered and '443' in rendered
    assert 'Référence pogo conservée' not in rendered
    hass.states.async_set('sensor.test_total', 2000)
    assert 'Référence pogo conservée : 2 000' in template.async_render()
    hass.states.async_set(entities[2], 'unavailable')
    rendered = template.async_render()
    assert 'Lecture incomplète' in rendered and '### — changements' in rendered


@pytest.mark.asyncio
async def test_assets_registered_once_across_parallel_setups_and_reinstalls():
    hass = NS(data={}, http=NS(async_register_static_paths=AsyncMock(), register_view=MagicMock()))
    await asyncio.gather(async_register_assets(hass), async_register_assets(hass))
    await async_register_assets(hass)
    hass.http.async_register_static_paths.assert_awaited_once()
    config = hass.http.async_register_static_paths.call_args.args[0][0]
    assert config.url_path == '/u1-care-assets'
    from pathlib import Path
    assert '<svg' in (Path(config.path) / 'toolhead.svg').read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize('old_kind', ['list', 'drawings'])
async def test_upgrade_exact_counter_list_and_u1care_copy_preserves_hub(hass, old_kind):
    await start_ui(hass)
    entry = await add_demo(hass)
    path = entry.options['dashboard_path']
    dashboard = hass.data[LOVELACE_DATA].dashboards[path]
    registry = er.async_get(hass)
    heads = [registry.async_get_entity_id('sensor', 'u1_companion', f'{entry.entry_id}_head_{i}_switch_count') for i in range(1, 5)]
    total = registry.async_get_entity_id('sensor', 'u1_companion', f'{entry.entry_id}_toolhead_swaps')
    old = {'type': 'entities', 'title': 'Compteurs des quatre têtes', 'entities': [
        {'entity': total, 'name': 'Cumul pogo · T1–T4'},
        *[{'entity': entity, 'name': f'T{i} · changements'} for i, entity in enumerate(heads, 1)]]}
    if old_kind == 'drawings':
        old = heads_card(heads, total, live=False)
    config = await dashboard.async_load(False)
    config['views'][0]['sections'][1]['cards'][-1] = old
    await dashboard.async_save(config)
    collection = _dashboard_collection(hass)
    for other in ['dashboard-u1care', 'lemyo-hub']:
        await collection.async_create_item({'url_path': other, 'title': other,
            'show_in_sidebar': True, 'require_admin': False, 'mode': 'storage'})
        await hass.data[LOVELACE_DATA].dashboards[other].async_save(config)
    before = deepcopy(entry.runtime_data.state)
    await async_upgrade_heads_card(hass, entry)
    for target in [path, 'dashboard-u1care']:
        updated = await hass.data[LOVELACE_DATA].dashboards[target].async_load(False)
        assert updated['views'][0]['sections'][1]['cards'][-1]['content'].count('<img ') == 1
        assert updated['views'][1:] == config['views'][1:]
    assert await hass.data[LOVELACE_DATA].dashboards['lemyo-hub'].async_load(False) == config
    assert entry.runtime_data.state == before
    backups = await Store(hass, 1, f'u1_companion.{entry.entry_id}.dashboard_before_050').async_load()
    assert backups[path] == config and backups['dashboard-u1care'] == config
    await async_upgrade_heads_card(hass, entry)
    assert await Store(hass, 1, f'u1_companion.{entry.entry_id}.dashboard_before_050').async_load() == backups
