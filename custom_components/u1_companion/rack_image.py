"""Front-facing U1 docking support, with strictly validated live appearance."""
import re
from aiohttp import web
from homeassistant.components.http import HomeAssistantView


def render_rack(query):
    drawings = []
    for i in range(1, 5):
        color = query.get(f'c{i}', '9ca3af')
        mounted = query.get(f'm{i}', 'u')
        count = query.get(f'n{i}', '-')
        source = query.get(f's{i}', 'u')
        if (not re.fullmatch(r'[a-fA-F0-9]{6}', color) or mounted not in ('0', '1', 'u')
                or source not in ('r', 'j', 'u', 'a', 'p')
                or not (count == '-' or re.fullmatch(r'\d{1,10}', count) and int(count) <= 1000000000)):
            raise ValueError('Invalid appearance')
        x = 85 + (i - 1) * 170
        number = f'{int(count):,}'.replace(',', ' ') if count != '-' else '—'
        position = {'0': 'Au parc', '1': 'Montée', 'u': 'Position inconnue'}[mounted]
        origin = {'r': 'Couleur RFID', 'j': 'Couleur du travail', 'u': 'Couleur inconnue',
                  'a': 'Sans filament', 'p': 'Présence inconnue'}[source]
        drawings.append(f'''
<g aria-label="Tête T{i}">
 <text x="{x}" y="24" class="head-label">T{i}</text>
 <text x="{x}" y="45" class="position">{position}</text>
 <path d="M{x-10} 58Q{x-16} 20 {x-28} 5" fill="none" stroke="#75808b" stroke-width="6"/>
 <path d="M{x+12} 58Q{x+18} 20 {x+27} 4" fill="none" stroke="#{color}" stroke-width="5"/>
 <g transform="translate({x-49},58)">
  <path d="M5 8 88 5 98 15V182L87 196H5L0 184V19Z" fill="url(#shell)" stroke="#56616b"/>
  <rect x="4" y="8" width="87" height="182" rx="12" fill="url(#face)" stroke="#78828b"/>
  <path d="M5 42H91V188H5Z" fill="#16191c"/>
  <path d="M7 45V184M89 45V184" stroke="#dbca49" stroke-width="2"/>
  <rect x="12" y="11" width="70" height="4" rx="2" fill="#{color}" stroke="#939ca5" stroke-width=".5"/>
  <rect x="36" y="22" width="25" height="16" rx="3" fill="#07090b" stroke="#727d88"/>
  <rect x="40" y="26" width="17" height="7" rx="1" fill="#555f68"/>
  <g fill="#d7c68b"><circle cx="43" cy="29" r="1.2"/><circle cx="49" cy="29" r="1.2"/><circle cx="55" cy="29" r="1.2"/></g>
  <g fill="url(#metal)" stroke="#707b86"><rect x="40" y="46" width="20" height="20" rx="3"/><rect x="13" y="145" width="19" height="20" rx="2"/><rect x="69" y="145" width="19" height="20" rx="2"/></g>
  <g fill="#b2bbc3" stroke="#303840" stroke-width="1.5"><circle cx="50" cy="56" r="5"/><circle cx="22.5" cy="155" r="5"/><circle cx="78.5" cy="155" r="5"/></g>
  <g stroke="#3d454c" stroke-width="1.5"><path d="M47 56H53M19.5 155H25.5M75.5 155H81.5"/></g>
  <g fill="#050708" stroke="#49535c"><circle cx="18" cy="94" r="6"/><circle cx="19" cy="174" r="5"/><rect x="14" y="116" width="25" height="10" rx="4"/><rect x="46" y="111" width="23" height="21" rx="4"/></g>
  <path d="M50 139 63 163H37Z" fill="#ead24d" stroke="#8c7b24"/>
  <path d="M45 155H55M47 152H53M49 149V145" fill="none" stroke="#242726" stroke-width="1.5"/>
  <path d="M24 194H78V207H24Z" fill="#242b31" stroke="#5e6a74"/>
  <path d="M35 207H65L62 216H38Z" fill="#101519"/>
 </g>
 <text x="{x}" y="329" class="count">{number}</text>
 <text x="{x}" y="347" class="detail">changements</text>
 <text x="{x}" y="365" class="origin">{origin}</text>
</g>''')
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="378" viewBox="0 0 680 378" role="img"><title>Support des quatre têtes U1, vue de face</title>
<defs><linearGradient id="shell"><stop stop-color="#4c565e"/><stop offset="1" stop-color="#12171c"/></linearGradient><linearGradient id="face" x2="0" y2="1"><stop stop-color="#424b52"/><stop offset="1" stop-color="#101418"/></linearGradient><linearGradient id="metal"><stop stop-color="#edf0f2"/><stop offset=".5" stop-color="#8c969f"/><stop offset="1" stop-color="#d3dbe1"/></linearGradient></defs>
<style>text{font-family:Arial,sans-serif;text-anchor:middle;fill:#eef2f5}.head-label{font-size:17px;font-weight:700}.position{font-size:12px;fill:#bcc6cf}.count{font-size:25px;font-weight:700}.detail{font-size:12px;fill:#bdc7cf}.origin{font-size:10px;fill:#9aa9b5}</style>
<rect x="8" y="126" width="664" height="36" rx="5" fill="#263039" stroke="#4c5965"/>
<path d="M12 274H668V288H12Z" fill="url(#metal)"/><path d="M12 288H668V300H12Z" fill="#414a53"/>
''' + ''.join(drawings) + '</svg>'


class RackImageView(HomeAssistantView):
    url = '/u1-care-assets/rack.svg'
    name = 'u1_care:rack_image'
    requires_auth = False

    async def get(self, request):
        try:
            svg = render_rack(request.query)
        except ValueError as err:
            raise web.HTTPBadRequest() from err
        return web.Response(text=svg, content_type='image/svg+xml', headers={'Cache-Control': 'public, max-age=3600'})
