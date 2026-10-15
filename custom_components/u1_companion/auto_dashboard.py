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
        return path


async def async_initialize_dashboard(hass, entry):
    try:
        await async_ensure_dashboard(hass, entry)
    except Exception:  # UI setup must not hide the printer or its maintenance.
        _LOGGER.exception('U1 Care dashboard could not be initialized; existing dashboards were preserved')
