# U1 Care 0.5.0

## Reinstall without the “already configured” dead end

Removing the code in HACS and removing a printer entry in Home Assistant are different operations. HACS removal can leave the printer entry registered. Previously, adding that IP again simply aborted as “already configured”.

The add-printer flow now detects that retained entry and offers **Reconnect the existing installation**. After confirmation and a successful real connection check, it reloads that same entry. Its name, commissioning date, maintenance events, counters, entity IDs and credentials are retained. A failed connection never creates a duplicate entry. If the printer entry was fully removed in Home Assistant, adding the IP creates a new installation normally; removal of an integration still deletes its maintenance store, so use HACS updates or reconnection when keeping its history. Export diagnostics or make a Home Assistant backup before intentionally removing the printer entry.

## Four toolheads, individual counts and total

A native Markdown card replaces the standard counter list. It shows four mechanical toolheads, T1 through T4, with each head's changes below its drawing and the total below all four. The vector drawing comes from the working U1Deck `toolheadShape` implementation. Illustrations are neutral: they do not invent live filament colors or mounted-head state. Drawings are served locally from packaged assets, with no extra frontend plugin, external image dependency or PC bridge.

The visible total is the sum of the four current head readings. If a reading is missing, its value and the total are shown as unavailable instead of using a partial sum. If an older manually established pogo reference differs from the raw sum, that preserved reference is labeled separately. This does not change the maintenance baseline.

Existing automatic U1 Care dashboards and the known `dashboard-u1care` copy are updated only when a counter card exactly matches the shipped list for this printer. Customized cards are preserved. Before editing, the original configuration is saved in the integration's `dashboard_before_050` store. LEMYO Hub is not scanned or edited. Other cards, dates and events remain unchanged. The dashboard export includes the new card for other custom layouts.

Update in HACS and restart Home Assistant. Keep the existing printer entry to retain its service history.
