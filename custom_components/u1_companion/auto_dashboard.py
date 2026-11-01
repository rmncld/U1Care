"""Create one ordinary editable Lovelace dashboard, never overwrite user work."""
import asyncio
import inspect
import json
import logging
import re

from homeassistant.exceptions import HomeAssistantError
from .dashboard_config import async_dashboard_config

_LOGGER = logging.getLogger(__name__)


def _dashboard_collection(hass):
    """Use HA's live collection, not a second stale copy of its storage.

    HA has no public create-dashboard helper. This compatibility adapter resolves
    the collection bound to its registered command; it never invokes a WebSocket
    handler or impersonates a user. Covered against both supported Core versions.
    """
    registration = hass.data.get('websocket_api', {}).get('lovelace/dashboards/create')
    if registration is None:
        raise HomeAssistantError('Lovelace dashboard registration is unavailable')
    owner = getattr(inspect.unwrap(registration[0]), '__self__', None)
    collection = getattr(owner, 'storage_collection', None)
    if collection is None or not callable(getattr(collection, 'async_create_item', None)):
        raise HomeAssistantError('Unsupported Home Assistant dashboard API')
    return collection


async def async_ensure_dashboard(hass, entry):
    """Initialize only once; user deletion, edits and metadata stay authoritative."""
    if entry.options.get('dashboard_initialized'):
        await async_upgrade_counters(hass, entry)
        await async_restore_logo(hass, entry)
        await async_upgrade_heads_card(hass, entry)
        return entry.options.get('dashboard_path')
    from homeassistant.components.lovelace.const import LOVELACE_DATA, ConfigNotFound
    if LOVELACE_DATA not in hass.data:
        return None  # A headless Core installation has no dashboards.
    lock = hass.data.setdefault('u1_care_dashboard_lock', asyncio.Lock())
    async with lock:
        if entry.options.get('dashboard_initialized'):
            return entry.options.get('dashboard_path')
        collection = _dashboard_collection(hass)
        data = hass.data[LOVELACE_DATA]
        path = f'u1-care-{entry.entry_id.lower()}'
        config = await async_dashboard_config(hass, entry, path)
        # Adopt an existing manually imported U1 Care dashboard for this entry.
        # Never touch unrelated dashboards or another printer's dashboard.
        references = {c['sections'][0]['cards'][1]['tap_action']['target']['entity_id']
                      for c in config['views'][1:]}
        for existing_path, dashboard in list(data.dashboards.items()):
            if not existing_path or not existing_path.startswith('u1-care'):
                continue
            try:
                existing = await dashboard.async_load(False)
            except ConfigNotFound:
                continue
            text = json.dumps(existing)
            if all(re.search(r'(?<![\w])' + re.escape(entity) + r'(?![\w])', text)
                   for entity in references):
                path = existing_path
                break
        else:
            if path not in data.dashboards:
                await collection.async_create_item({
                    'url_path': path, 'title': entry.title,
                    'icon': 'mdi:printer-3d', 'show_in_sidebar': True,
                    'require_admin': False, 'mode': 'storage'})
            dashboard = data.dashboards[path]
            try:
                await dashboard.async_load(False)
            except ConfigNotFound:
                # Retry an interrupted first save without replacing any config.
                await dashboard.async_save(config)
        hass.config_entries.async_update_entry(entry, options={
            **entry.options, 'dashboard_initialized': True, 'dashboard_path': path})
        await async_upgrade_counters(hass, entry)
        await async_restore_logo(hass, entry)
        await async_upgrade_heads_card(hass, entry)
        return path


async def async_upgrade_heads_card(hass, entry):
    """Replace only the shipped counter list, including the known U1Care copy.

    No scans or writes to Hub dashboards, no replacement of customized cards.
    """
    from copy import deepcopy
    from homeassistant.components.lovelace.const import LOVELACE_DATA, ConfigNotFound
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.storage import Store
    from .heads_card import heads_card
    from .const import DOMAIN, STORAGE_VERSION
    data = hass.data.get(LOVELACE_DATA)
    if data is None:
        return
    registry = er.async_get(hass)
    heads = [registry.async_get_entity_id('sensor', DOMAIN, f'{entry.entry_id}_head_{i}_switch_count') for i in range(1, 5)]
    total = registry.async_get_entity_id('sensor', DOMAIN, f'{entry.entry_id}_toolhead_swaps')
    if not total or any(e is None for e in heads):
        return
    old = {'type': 'entities', 'title': 'Compteurs des quatre têtes', 'entities': [
        {'entity': total, 'name': 'Cumul pogo · T1–T4'},
        *[{'entity': entity, 'name': f'T{i} · changements'} for i, entity in enumerate(heads, 1)]]}
    targets = {entry.options.get('dashboard_path', ''), 'dashboard-u1care'}
    for path in targets:
        if not (path.startswith('u1-care') or path == 'dashboard-u1care') or path not in data.dashboards:
            continue
        dashboard = data.dashboards[path]
        try:
            existing = await dashboard.async_load(False)
        except ConfigNotFound:
            continue
        updated = deepcopy(existing)
        def replace(cards):
            for i, card in enumerate(cards):
                if card == old or card == heads_card(heads, total, live=False):
                    cards[i] = heads_card(heads, total)
                elif isinstance(card, dict) and isinstance(card.get('cards'), list):
                    replace(card['cards'])
        for view in updated.get('views', []):
            replace(view.get('cards', []))
            for section in view.get('sections', []):
                replace(section.get('cards', []))
        if updated != existing:
            backup = Store(hass, STORAGE_VERSION, f'{DOMAIN}.{entry.entry_id}.dashboard_before_050')
            saved = await backup.async_load() or {}
            if path not in saved:
                await backup.async_save({**saved, path: existing})
            await dashboard.async_save(updated)


async def async_restore_logo(hass, entry):
    """Repair only the exact shipped 0.4.0/0.4.1 banner on its own dashboard."""
    if entry.data.get('demo') or entry.options.get('banner_logo_version') == 1:
        return
    from copy import deepcopy
    from homeassistant.components.lovelace.const import LOVELACE_DATA, ConfigNotFound
    from homeassistant.helpers.storage import Store
    from .dashboard_config import BANNER_LOGO
    from .const import DOMAIN, STORAGE_VERSION
    path = entry.options.get('dashboard_path', '')
    data = hass.data.get(LOVELACE_DATA)
    if not path.startswith('u1-care') or data is None or path not in data.dashboards:
        return
    dashboard = data.dashboards[path]
    try:
        existing = await dashboard.async_load(False)
    except ConfigNotFound:
        return
    fresh = await async_dashboard_config(hass, entry, path)
    banner = fresh['views'][0]['sections'][0]['cards'][0]['content']
    old_banner = banner.removeprefix(BANNER_LOGO + '\n\n')
    updated = deepcopy(existing)
    for view in updated.get('views', []):
        for section in view.get('sections', []):
            for card in section.get('cards', []):
                if card.get('type') == 'markdown' and card.get('content') == old_banner:
                    card['content'] = banner
    if updated != existing:
        backup = Store(hass, STORAGE_VERSION, f'{DOMAIN}.{entry.entry_id}.dashboard_before_042')
        if await backup.async_load() is None:
            await backup.async_save(existing)
        await dashboard.async_save(updated)
    hass.config_entries.async_update_entry(entry, options={**entry.options, 'banner_logo_version': 1})


async def async_upgrade_counters(hass, entry):
    """Append telemetry once to this entry's dashboard; preserve user cards/views.

    Never search or modify other dashboards (including LEMYO Hub). A deleted
    dashboard stays deleted. Keep the full original config before any write.
    """
    if entry.options.get('counter_dashboard_version', 0) >= 1:
        return
    from homeassistant.components.lovelace.const import LOVELACE_DATA, ConfigNotFound
    from homeassistant.helpers.storage import Store
    from .const import DOMAIN, STORAGE_VERSION
    data = hass.data.get(LOVELACE_DATA)
    path = entry.options.get('dashboard_path')
    if data is None or not path:
        return
    dashboard = data.dashboards.get(path)
    if dashboard is None:
        return
    try:
        existing = await dashboard.async_load(False)
    except ConfigNotFound:
        return
    from copy import deepcopy
    config = deepcopy(existing)
    fresh = await async_dashboard_config(hass, entry, path)
    card = fresh['views'][0]['sections'][1]['cards'][-1]
    # Only a dashboard containing this printer's maintenance entities is eligible.
    target = fresh['views'][1]['sections'][0]['cards'][1]['tap_action']['target']['entity_id']
    if target not in json.dumps(existing):
        return
    from homeassistant.helpers import entity_registry as er
    total = er.async_get(hass).async_get_entity_id('sensor', DOMAIN, f'{entry.entry_id}_toolhead_swaps')
    if total not in json.dumps(existing):
        config['views'].append({'title': 'Compteurs U1', 'path': 'compteurs-u1',
                                'icon': 'mdi:swap-horizontal', 'cards': [card]})
    # Replace only the shipped default banner, never a customized header.
    for view in config.get('views', []):
        for section in view.get('sections', []):
            for old_card in section.get('cards', []):
                content = old_card.get('content', '')
                if '## U1 Care\nVotre atelier, prêt pour la prochaine impression.' in content and not entry.data.get('demo'):
                    old_card['content'] = fresh['views'][0]['sections'][0]['cards'][0]['content']
    if config != existing:
        backup = Store(hass, STORAGE_VERSION, f'{DOMAIN}.{entry.entry_id}.dashboard_before_040')
        if await backup.async_load() is None:
            await backup.async_save(existing)
        await dashboard.async_save(config)
    hass.config_entries.async_update_entry(entry, options={
        **entry.options, 'counter_dashboard_version': 1})


async def async_initialize_dashboard(hass, entry):
    try:
        await async_ensure_dashboard(hass, entry)
    except Exception:  # UI setup must not hide the printer or its maintenance.
        _LOGGER.exception('U1 Care dashboard could not be initialized; existing dashboards were preserved')
