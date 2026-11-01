from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import json

import pytest
from homeassistant.helpers.template import Template

from custom_components.u1_companion.api import HEADS, HEAD_OBJECTS, parse_heads, U1Api
from custom_components.u1_companion.rack_image import render_rack, RackImageView
from custom_components.u1_companion.heads_card import heads_card
from custom_components.u1_companion import model
from test_heads import Session


def telemetry():
    status = {name: {'switch_count': count, 'last_maintenance_count': 0,
        'state': 'PARKED', 'active_pin': False} for name, count in zip(HEADS, [266, 150, 223, 443])}
    status.update({f'filament_motion_sensor e{i}_filament': {'filament_detected': True} for i in range(4)})
    status['filament_detect'] = {'info': [{'VENDOR': 'TEST', 'RGB_1': 0x080a0d},
        {'VENDOR': 'TEST', 'RGB_1': 0xffffff}, {'VENDOR': 'TEST', 'RGB_1': 0x1234ab}, {'VENDOR': 'NONE'}]}
    status['print_task_config'] = {'filament_color_rgba': ['ff0000ff', 'ff0000ff', 'ff0000ff', '00aa22ff']}
    status['extruder1'].update(state='ACTIVE', active_pin=True)
    return status


def test_rfid_priority_job_fallback_and_physical_mount():
    heads = parse_heads(telemetry())
    assert [h['color'] for h in heads] == ['#080a0d', '#ffffff', '#1234ab', '#00aa22']
    assert [h['color_source'] for h in heads] == ['rfid', 'rfid', 'rfid', 'job']
    assert [h['mounted'] for h in heads] == [False, True, False, False]


@pytest.mark.parametrize('present', [False, None])
def test_no_stale_filament_color_without_confirmed_presence(present):
    status = telemetry()
    status['filament_motion_sensor e0_filament']['filament_detected'] = present
    head = parse_heads(status)[0]
    assert head['color'] is None and head['color_source'] == 'unknown'


def test_mount_missing_conflicting_or_parked_never_inferred_from_selected_extruder():
    status = telemetry()
    status['toolhead'] = {'extruder': 'extruder3'}
    status['extruder1'].pop('active_pin')
    assert parse_heads(status)[1]['mounted'] is None
    status['extruder1']['active_pin'] = True
    status['extruder3'].update(state='ACTIVE', active_pin=True)
    assert all(h['mounted'] is None for h in parse_heads(status))
    status['extruder1']['state'] = 'PARKED'
    assert parse_heads(status)[1]['mounted'] is False
    assert all(h['mounted'] is None and h['color'] is None for h in parse_heads({}))


def test_appearance_does_not_change_cumulative_references_dates_or_events():
    catalog = json.loads((Path(__file__).parents[1] / 'custom_components/u1_companion/catalog.json').read_text())
    status = telemetry()
    first = model.apply_heads(model.fresh(catalog), parse_heads(status))
    first = model.reference_date(first, '2026-10-30', '2026-11-01', catalog)
    saved = deepcopy(first)
    status['filament_detect']['info'][0]['RGB_1'] = 0xabcdef
    status['extruder1'].update(state='PARKED', active_pin=False)
    assert model.apply_heads(first, parse_heads(status)) == saved


@pytest.mark.asyncio
async def test_subscription_only_announced_u1deck_appearance_objects():
    status = telemetry()
    session = Session([{'id': 1, 'result': {'status': status}}], available=HEAD_OBJECTS)
    assert await U1Api(session, '192.168.1.50', 7125).async_heads() == parse_heads(status)
    assert session.socket.sent[0]['params']['objects'] == dict.fromkeys(HEAD_OBJECTS)


@pytest.mark.parametrize('color,mounted', [('ffffff', '1'), ('080a0d', '0'), ('00aa22', '0')])
def test_bounded_svg_color_and_mount_outline(color, mounted):
    result = render_rack({'c1': color, 'm1': mounted, 'n1': '266', 's1': 'r'})
    assert '#' + color in result and '266' in result
    assert '#22d3ee' not in result and '<table' not in result
    assert ('Montée' in result) == (mounted == '1')


@pytest.mark.parametrize('color,mounted', [('<script>', '0'), ('#abcdef', '0'), ('ffffff', '2'), ('abcdef00', '0')])
def test_svg_rejects_unbounded_input(color, mounted):
    with pytest.raises(ValueError):
        render_rack({'c1': color, 'm1': mounted})


@pytest.mark.asyncio
async def test_live_card_appearance_and_offline_fallback(hass):
    entities = [f'sensor.appearance_t{i}' for i in range(1, 5)]
    for entity, head in zip(entities, parse_heads(telemetry())):
        hass.states.async_set(entity, head['switch_count'], head)
    hass.states.async_set('sensor.appearance_total', 1082)
    template = Template(heads_card(entities, 'sensor.appearance_total')['content'], hass)
    rendered = template.async_render()
    assert 'c1=080a0d&amp;m1=0' in rendered
    assert 'c2=ffffff&amp;m2=1' in rendered
    assert 's1=r' in rendered and 's4=j' in rendered
    assert '<table' not in rendered
    for entity in entities:
        hass.states.async_set(entity, 'unavailable', parse_heads({})[0])
    rendered = template.async_render()
    assert 'm2=1' not in rendered and 'c1=9ca3af' in rendered
    assert 'm1=u' in rendered and 'Lecture incomplète' in rendered
