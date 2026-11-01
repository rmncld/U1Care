"""Native Markdown card: local U1Deck illustration and live HA counters."""

ASSET_URL = '/u1-care-assets/toolhead.svg'


def heads_card(head_entities, total_entity):
    def count(entity):
        return "{{ ('{:,.0f}'.format(states('" + entity + "') | float).replace(',', ' ')) if is_number(states('" + entity + "')) else '—' }}"
    labels = ''.join(f'<th align="center">T{i}</th>' for i in range(1, 5))
    images = ''.join(f'<td align="center"><img src="{ASSET_URL}" width="72" height="108" alt="Tête T{i}"></td>' for i in range(1, 5))
    values = ''.join(f'<td align="center"><strong>{count(entity)}</strong><br>changements</td>' for entity in head_entities)
    checks = ' and '.join(f"is_number(states('{e}'))" for e in head_entities)
    expression = ' + '.join(f"(states('{e}') | int(0))" for e in head_entities)
    content = ("<!-- U1 Care heads v1 -->\n## Têtes d’impression\n"
        + f'<table width="100%"><thead><tr>{labels}</tr></thead><tbody><tr>{images}</tr><tr>{values}</tr></tbody></table>\n\n'
        + '{% set complete = ' + checks + ' %}{% set total = ' + expression + ' %}\n'
        + "### {{ '{:,.0f}'.format(total).replace(',', ' ') if complete else '—' }} changements\n"
        + 'Total des quatre têtes\n\n'
        + "{% if complete and is_number(states('" + total_entity + "')) and (states('" + total_entity + "') | int) != total %}"
        + 'Référence pogo conservée : ' + count(total_entity) + ' changements{% endif %}'
        + '{% if not complete %}Lecture incomplète · total indisponible{% endif %}')
    return {'type': 'markdown', 'content': content, 'grid_options': {'columns': 'full'},
        'card_mod': {'style': 'ha-card { background: #10161d; color: #eef2f5; border: 1px solid #28323c; border-top: 3px solid #a3e635; border-radius: 20px; box-shadow: none; text-align: center; }'}}


async def async_register_assets(hass):
    """Serve only packaged public drawings; register once across reloads/readds."""
    http = getattr(hass, 'http', None)
    if http is None or hass.data.get('u1_care_assets_registered'):
        return
    from pathlib import Path
    import asyncio
    from homeassistant.components.http import StaticPathConfig
    lock = hass.data.setdefault('u1_care_assets_lock', asyncio.Lock())
    async with lock:
        if not hass.data.get('u1_care_assets_registered'):
            await http.async_register_static_paths([StaticPathConfig(
                '/u1-care-assets', str(Path(__file__).with_name('assets')), True)])
            hass.data['u1_care_assets_registered'] = True
