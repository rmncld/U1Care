"""Native Markdown card: local U1Deck illustration and live HA counters."""

ASSET_URL = '/u1-care-assets/toolhead.svg'


def heads_card(head_entities, total_entity, *, live=True):
    if live:
        return rack_card(head_entities, total_entity)
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
        'card_mod': {'style': {
            '.': 'ha-card { background: #10161d; color: #eef2f5; border: 1px solid #28323c; border-top: 3px solid #a3e635; border-radius: 20px; box-shadow: none; text-align: center; }',
            'ha-markdown$': 'table { width: 100%; table-layout: fixed; border-collapse: collapse; } th { padding: 0 0 10px; font-size: 14px; color: #c2ccd5; border: 0; } td { padding: 6px 0 10px; border: 0; font-size: 12px; color: #9daebd; } td strong { font-size: 23px; font-weight: 650; color: #f4f8fb; } h2 { font-size: 22px; font-weight: 650; } h3 { border-top: 1px solid #28323c; padding-top: 20px; margin-bottom: 5px; font-size: 26px; color: #a3e635; }'}}}


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
            from .rack_image import RackImageView
            http.register_view(RackImageView())
            await http.async_register_static_paths([StaticPathConfig(
                '/u1-care-assets', str(Path(__file__).with_name('assets')), True)])
            hass.data['u1_care_assets_registered'] = True


def rack_card(head_entities, total_entity):
    """One front-view scene, no table and no colored mount indicator."""
    legacy = heads_card(head_entities, total_entity, live=False)
    args, descriptions = [], []
    for i, entity in enumerate(head_entities, 1):
        color = "{{ (state_attr('" + entity + "', 'color') or '#9ca3af') | replace('#', '') }}"
        mounted = "{{ '1' if state_attr('" + entity + "', 'mounted') == true else '0' if state_attr('" + entity + "', 'mounted') == false else 'u' }}"
        count = "{{ states('" + entity + "') | int if is_number(states('" + entity + "')) else '-' }}"
        source = ("{% set p = state_attr('" + entity + "', 'present') %}{% set c = state_attr('" + entity + "', 'color_source') %}"
                  + "{{ 'a' if p == false else 'p' if p != true else 'r' if c == 'rfid' else 'j' if c == 'job' else 'u' }}")
        args.extend([f'c{i}={color}', f'm{i}={mounted}', f'n{i}={count}', f's{i}={source}'])
        descriptions.append(f'T{i} : {count} changements')
    image = '<img src="/u1-care-assets/rack.svg?' + '&amp;'.join(args) + '" width="100%" alt="Support U1, vue de face. ' + '. '.join(descriptions) + '">'
    content = legacy['content']
    start, end = content.index('<table'), content.index('</table>') + len('</table>')
    legacy['content'] = (content[:start] + image + content[end:]).replace('U1 Care heads v1', 'U1 Care heads v3')
    return legacy
