"""Portable editable dashboard, resolved from this entry's registered entities."""
import json
from pathlib import Path
from homeassistant.helpers import entity_registry as er

BANNER_LOGO = ('<img src="https://raw.githubusercontent.com/rmncld/U1Care/'
               'f0dd689460920410762660dd5ac9122232dc142c/assets/u1-care-mark.svg" '
               'width="48" alt="Logo U1 Care">')

KEYS = {'guides': 'linear-shafts', 'carbon': 'carbon-rods', 'z': 'lead-screws',
        'belts': 'timing-belts', 'coupling': 'steel-coupling', 'pogo': 'pogo-contacts',
        'xyz': 'xyz-calibration', 'hours': 'history_hours', 'overall': 'maintenance_overall',
        'swaps': 'toolhead_swaps', **{f'head{i}': f'head_{i}_switch_count' for i in range(1, 5)}}


async def async_dashboard_config(hass, entry, path=None):
    def read():
        return Path(__file__).with_name('dashboard-template.json').read_text(encoding='utf-8')
    text = await hass.async_add_executor_job(read)
    registry = er.async_get(hass)
    for key, suffix in KEYS.items():
        entity_id = registry.async_get_entity_id('sensor', 'u1_companion', f'{entry.entry_id}_{suffix}')
        if entity_id is None:
            raise ValueError('An enabled maintenance entity is missing: ' + key)
        text = text.replace('__ENTITY_' + key + '__', entity_id)
    text = text.replace('__DASHBOARD_PATH__', path or f'u1-care-{entry.entry_id[:8].lower()}')
    if not entry.data.get('demo'):
        text = text.replace('**DÉMONSTRATION** · Dates et compteurs fictifs · Aucune U1 connectée',
                            'Suivi local · Intervalles officiels · Votre imprimante')
        text = text.replace('Heures · simulation', 'Heures de l’historique')
    config = json.loads(text)
    from .heads_card import heads_card
    head_entities = [registry.async_get_entity_id('sensor', 'u1_companion',
                    f'{entry.entry_id}_head_{i}_switch_count') for i in range(1, 5)]
    total = registry.async_get_entity_id('sensor', 'u1_companion', f'{entry.entry_id}_toolhead_swaps')
    config['views'][0]['sections'][1]['cards'][-1] = heads_card(head_entities, total)
    if not entry.data.get('demo'):
        swaps = registry.async_get_entity_id('sensor', 'u1_companion', f'{entry.entry_id}_toolhead_swaps')
        config['views'][0]['sections'][0]['cards'][0]['content'] = (
            BANNER_LOGO + "\n\n## {{ state_attr('" + swaps + "', 'printer_name') | e }}"
            + '\nSuivi local · Intervalles officiels · Votre imprimante')
    return config
