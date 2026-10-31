"""Both pogo deadlines must remain visible without changing stored maintenance."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.u1_companion import model
from custom_components.u1_companion.sensor import _display
from custom_components.u1_companion.api import HEADS, parse_heads

CAT = json.loads((Path(__file__).parents[1] / 'custom_components/u1_companion/catalog.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('start,swaps,today,expected', [
    ('2026-10-30', 1081, '2026-11-01', 'OK · 180 j restants · 98919 changements restants'),
    ('2026-10-30', 96000, '2026-11-01', 'SOON · 180 j restants · 4000 changements restants'),
    ('2026-10-30', 100000, '2026-11-01', 'DUE · 180 j restants · 0 changements restants'),
    ('2026-10-30', 100002, '2026-11-01', 'DUE · 180 j restants · 2 changements dépassés'),
    ('2026-10-30', 1081, '2027-03-01', 'SOON · 60 j restants · 98919 changements restants'),
    ('2026-10-30', 1081, '2027-04-30', 'DUE · 0 j restants · 98919 changements restants'),
    ('2026-10-30', 1081, '2027-05-01', 'DUE · 1 j de retard · 98919 changements restants'),
    ('2026-10-30', None, '2026-11-01', 'INCONNU · 180 j restants · changements inconnus'),
    (None, 1081, '2026-11-01', 'INCONNU · date inconnue · 98919 changements restants'),
    (None, None, '2026-11-01', 'INCONNU · date inconnue · changements inconnus'),
])
def test_pogo_both_deadlines_visible_and_input_unchanged(start, swaps, today, expected):
    state = model.fresh(CAT)
    state['machine'].update(startDate=start, swaps=swaps)
    original = deepcopy(state)
    status = model.snapshot(state, today)['tasks']['pogo-contacts']
    assert _display(status) == expected
    assert state == original


def test_other_maintenance_display_unchanged():
    state = model.reference_date(model.fresh(CAT), '2026-10-30', '2026-11-01', CAT)
    assert _display(model.snapshot(state, '2026-11-01')['tasks']['linear-shafts']) == 'OK · 29 j'


@pytest.mark.asyncio
async def test_native_pogo_state_and_restart_preserve_dates_and_events(hass):
    found = {'port': 7125, 'hours': 2.0, 'moonraker_version': 'test'}
    heads = parse_heads({name: {'switch_count': count, 'last_maintenance_count': 0}
                         for name, count in zip(HEADS, [266, 150, 223, 442])})
    with patch('custom_components.u1_companion.config_flow.async_discover', return_value=found), patch(
        'custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0), patch(
        'custom_components.u1_companion.api.U1Api.async_heads', return_value=heads, side_effect=None):
        result = await hass.config_entries.flow.async_init('u1_companion', context={'source': 'user'},
            data={'host': '192.168.1.50', 'name': 'Atelier', 'start_date': '2026-10-30'})
        await hass.async_block_till_done()
        entry = result['result']
        coordinator = entry.runtime_data
        pogo_entity = next(e for e in hass.states.async_all() if e.attributes.get('frequency', '').startswith('4 à 6 mois'))
        assert 'j restants' in pogo_entity.state and '98919 changements restants' in pogo_entity.state
        task = next(t for t in coordinator.catalog['tasks'] if t['id'] == 'pogo-contacts')
        await coordinator.async_complete('pogo-contacts', [True] * len(task['steps']), 'Nettoyage réel', coordinator.today())
        await hass.async_block_till_done()
        assert '100000 changements restants' in hass.states.get(pogo_entity.entity_id).state
        saved = deepcopy(coordinator.state)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.state == saved
        assert entry.runtime_data.state['machine']['startDate'] == '2026-10-30'
        assert '100000 changements restants' in hass.states.get(pogo_entity.entity_id).state
