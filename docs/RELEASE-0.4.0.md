# U1 Care 0.4.0

- Read each U1 toolhead's `switch_count` and `last_maintenance_count` using the working U1Deck Moonraker subscription protocol. Five new sensors expose T1–T4 and the cumulative pogo reference.
- Use a custom printer name in setup, device information and the dashboard banner. The commissioning date is offered during addition; unknown dates may stay empty.
- Remove demo creation from normal setup. Existing demo entries remain isolated and readable.
- Preserve v0.3.6 entry IDs, entity unique IDs, maintenance dates, events, manual counter references and dashboard customizations. No integration removal is needed.
- Append counters to an existing managed U1 Care dashboard once, with a backup before the change. Other dashboards are untouched.

## Update with HACS

In HACS, open **U1 Care**, refresh repository information if necessary and install **0.4.0**, then restart Home Assistant. Keep the existing integration: deleting it removes its maintenance data. An existing installation keeps its commissioning date. Use **Reconfigure** to set the printer name; changing the IP preserves the same entity IDs.

The new counters normally appear within one polling interval (60 seconds). T1–T4 are firmware lifetime readings. The cumulative pogo sensor starts with their sum, preserving a larger existing manual reference, then adds only positive deltas. Identical readings and restarts do not add counts. `last_maintenance_count` is exposed separately; it is never subtracted from the lifetime sum or treated as a U1 Care service event.

If any head reading is missing, the cumulative automatic reading is unavailable; partial totals are never published as complete. Previously saved dates and events remain available. A decreasing head counter pauses the cumulative reading. After checking the printer, use **Configure → Resume automatic readings** to accept the new baseline. The accumulated value is retained; changes during a reset cannot be reconstructed. Manual fallback remains available and suspends automatic cumulative readings until resumed.

The initial name for a migrated installation comes from its saved machine name, otherwise **Mon U1**. Existing user-named entities remain named as before. Existing U1 Care dashboards receive a **Compteurs U1** view if the new readings are absent; custom cards remain. A full pre-update dashboard copy is saved in the integration's `dashboard_before_040` store. Deleted dashboards are not recreated. The normal dashboard export includes all readings for a manual layout update.

## Validation scope

The parser is checked against a sanitized real U1Deck capture from firmware 2.0.0 (T1–T4: 266 / 150 / 223 / 442, sum 1081). Tests cover the subscription handshake, incomplete data, counter reset, persistence, v0.3.6 migration, setup and Lovelace updates. The GitHub workflow runs against Home Assistant 2026.8.2 and 2026.10.1 before publishing a release. No printer movement or firmware write is involved. This does not claim an on-device installation of this new Home Assistant version.
