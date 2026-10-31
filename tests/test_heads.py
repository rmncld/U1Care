"""Real U1Deck field/transport contract and non-destructive counter continuity."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.u1_companion import model
from custom_components.u1_companion.api import HEADS, U1Api, Unsupported, CannotConnect, parse_heads
from test_api import Response

CAT = json.loads((Path(__file__).parents[1] / 'custom_components/u1_companion/catalog.json').read_text(encoding='utf-8'))


def heads(counts=(266, 42, 18, 9)):
    return parse_heads({name: {'switch_count': n, 'last_maintenance_count': 0}
                        for name, n in zip(HEADS, counts)})


def test_sum_deltas_restart_and_manual_migration_preserve_events():
    old = model.reference_date(model.fresh(CAT), '2026-10-30', '2026-11-01', CAT)
    old['machine']['swaps'] = 1000
    task = next(t for t in old['tasks'] if t['id'] == 'pogo-contacts')
    old = model.complete(old, task['id'], [True] * len(task['steps']), 'keep', '2026-11-01', '2026-11-01', CAT)
    before = deepcopy(old)
    first = model.apply_heads(old, heads())
    assert old == before
    assert first['machine']['swaps'] == 1000  # Preserve larger manual reference.
    assert first['history'] == before['history'] and first['tasks'] == before['tasks']
    assert model.apply_heads(first, heads()) == first  # No repeated sums.
    restarted = json.loads(json.dumps(first))
    next_state = model.apply_heads(restarted, heads((268, 43, 18, 10)))
    assert next_state['machine']['swaps'] == 1004
    assert next_state['history'] == before['history']
    assert model.validate(next_state, CAT) == next_state


def test_first_sample_is_sum_not_max_or_since_maintenance():
    result = model.apply_heads(model.fresh(CAT), heads())
    assert result['machine']['swaps'] == 335


def test_sanitized_real_u1deck_capture():
    raw = json.loads((Path(__file__).parent / 'fixtures/u1deck-heads.json').read_text())
    parsed = parse_heads(raw)
    assert [h['switch_count'] for h in parsed] == [266, 150, 223, 442]
    assert [h['since_service'] for h in parsed] == [266, 150, 223, 442]
    assert model.apply_heads(model.fresh(CAT), parsed)['machine']['swaps'] == 1081


def test_partial_invalid_and_reset_never_advance_baseline():
    state = model.apply_heads(model.fresh(CAT), heads())
    original = deepcopy(state)
    partial = heads()
    partial[2]['switch_count'] = None
    with pytest.raises(ValueError):
        model.apply_heads(state, partial)
    with pytest.raises(ValueError, match='head_counter_reset'):
        model.apply_heads(state, heads((1, 42, 18, 9)))
    assert state == original
    resumed = model.apply_heads(state, heads((1, 42, 18, 9)), accept_reset=True)
    assert resumed['machine']['swaps'] == 335
    assert model.apply_heads(resumed, heads((2, 43, 18, 9)))['machine']['swaps'] == 337


@pytest.mark.parametrize('value', [None, True, -1, 1.5, '12', float('nan'), float('inf')])
def test_invalid_head_counter_is_unknown(value):
    result = parse_heads({'extruder': {'switch_count': value, 'last_maintenance_count': 0}})
    assert result[0]['switch_count'] is None and result[0]['since_service'] is None
    assert all(h['switch_count'] is None for h in result[1:])


def test_last_maintenance_counter_is_separate():
    result = parse_heads({'extruder': {'switch_count': 266, 'last_maintenance_count': 200}})
    assert result[0]['switch_count'] == 266 and result[0]['since_service'] == 66
    assert parse_heads({'extruder': {'switch_count': 1, 'last_maintenance_count': 3}})[0]['since_service'] is None


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def send_json(self, message):
        self.sent.append(message)

    async def receive_json(self):
        return next(self.messages)


class Session:
    def __init__(self, messages, available=HEADS):
        self.socket = Socket(messages)
        self.available = available
        self.ws_options = None

    def get(self, url, **kwargs):
        assert url == 'http://192.168.1.50:7125/printer/objects/list'
        return Response(200, {'result': {'objects': list(self.available)}})

    def ws_connect(self, url, **kwargs):
        assert url == 'ws://192.168.1.50:7125/websocket'
        self.ws_options = kwargs
        return self.socket


@pytest.mark.asyncio
async def test_same_u1deck_list_and_subscribe_handshake_closes_socket():
    raw = {name: {'switch_count': n, 'last_maintenance_count': 0} for name, n in zip(HEADS, [266, 42, 18, 9])}
    session = Session([{'method': 'notify_status_update', 'params': [{}]}, {'id': 1, 'result': {'status': raw}}])
    result = await U1Api(session, '192.168.1.50', 7125, 'secret').async_heads()
    assert result == heads()
    assert session.socket.closed
    assert session.ws_options['headers'] == {'X-Api-Key': 'secret'}
    assert session.socket.sent == [{'jsonrpc': '2.0', 'id': 1, 'method': 'printer.objects.subscribe',
                                    'params': {'objects': dict.fromkeys(HEADS)}}]


@pytest.mark.asyncio
async def test_partial_subscription_and_protocol_error():
    session = Session([{'id': 1, 'result': {'status': {'extruder': {'switch_count': 10}}}}], available=['extruder'])
    result = await U1Api(session, '192.168.1.50', 7125).async_heads()
    assert result[0]['switch_count'] == 10 and result[1]['switch_count'] is None
    session = Session([{'id': 1, 'error': {'message': 'not ready'}}])
    with pytest.raises(Unsupported):
        await U1Api(session, '192.168.1.50', 7125).async_heads()
    assert session.socket.closed


@pytest.mark.asyncio
async def test_new_setup_name_date_no_demo_and_independent_offline_counters(hass):
    found = {'port': 7125, 'hours': 2.0, 'moonraker_version': 'test'}
    with patch('custom_components.u1_companion.config_flow.async_discover', return_value=found), patch(
        'custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0), patch(
        'custom_components.u1_companion.api.U1Api.async_heads', return_value=heads(), side_effect=None):
        form = await hass.config_entries.flow.async_init('u1_companion', context={'source': 'user'})
        fields = {str(k) for k in form['data_schema'].schema}
        assert fields == {'host', 'name', 'start_date'}
        result = await hass.config_entries.flow.async_configure(form['flow_id'], {
            'host': '192.168.1.50', 'name': 'Atelier', 'start_date': '2026-10-30'})
        await hass.async_block_till_done()
        entry = result['result']
        c = entry.runtime_data
        assert entry.title == 'Atelier' and c.state['machine']['name'] == 'Atelier'
        assert c.state['machine']['startDate'] == '2026-10-30'
        assert c.data['swaps'] == 335
        assert len(hass.states.async_all()) == 15
        with patch('custom_components.u1_companion.api.U1Api.async_heads', side_effect=CannotConnect()):
            await c.async_refresh()
            assert c.data['swaps'] is None and c.data['hours'] == 2.0
            assert c.state['machine']['swaps'] == 335
            await c.async_complete('pogo-contacts', [True] * len(next(t for t in c.catalog['tasks'] if t['id'] == 'pogo-contacts')['steps']), '', c.today())
            assert c.state['history'][-1]['swaps'] is None
        await c.async_refresh()
        assert c.data['swaps'] == 335
        with patch('custom_components.u1_companion.api.U1Api.async_hours', side_effect=CannotConnect()):
            await c.async_refresh()
            assert c.data['hours'] is None and c.data['swaps'] == 335


@pytest.mark.asyncio
async def test_v036_entry_migration_preserves_store_options_and_unique_ids(hass):
    from types import MappingProxyType
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.storage import Store
    from homeassistant.helpers import entity_registry as er
    old = model.reference_date(model.fresh(CAT), '2026-10-30', '2026-11-01', CAT)
    old['machine'].update(name='Mon atelier', swaps=1000)
    task = next(t for t in old['tasks'] if t['id'] == 'pogo-contacts')
    old = model.complete(old, task['id'], [True] * len(task['steps']), 'conserver', '2026-10-31', '2026-10-31', CAT)
    entry = ConfigEntry(version=1, minor_version=1, domain='u1_companion',
        title='U1 Care · 192.168.1.50', data={'host': '192.168.1.50', 'port': 7125},
        options={'dashboard_initialized': True, 'dashboard_path': 'u1-care-existing'},
        source='user', unique_id=None, discovery_keys=MappingProxyType({}), subentries_data=None)
    registry = er.async_get(hass)
    registered = registry.async_get_or_create('sensor', 'u1_companion', entry.entry_id + '_pogo-contacts',
                                             suggested_object_id='my_existing_pogo', config_entry=entry)
    await Store(hass, 1, 'u1_companion.' + entry.entry_id).async_save(old)
    with patch('custom_components.u1_companion.api.U1Api.async_hours', return_value=2.0), patch(
        'custom_components.u1_companion.api.U1Api.async_heads', return_value=heads(), side_effect=None):
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.version == 2 and entry.title == 'Mon atelier'
        assert entry.options['dashboard_path'] == 'u1-care-existing'
        assert entry.runtime_data.state['history'] == old['history']
        assert entry.runtime_data.state['tasks'] == old['tasks']
        assert entry.runtime_data.data['swaps'] == 1000
        assert registry.async_get_entity_id('sensor', 'u1_companion', entry.entry_id + '_pogo-contacts') == registered.entity_id
