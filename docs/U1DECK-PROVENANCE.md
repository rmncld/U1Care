# Counter source verification

Verified 2026-11-01 against the user's functional local U1Deck 0.6.0 workspace. The public [U1Deck repository](https://github.com/rmncld/U1Deck) was inspected first and contains the historical proposal rather than the functional implementation. No counter endpoint was inferred from that proposal.

The local implementation lists objects with GET /printer/objects/list, then subscribes via /websocket using JSON-RPC printer.objects.subscribe. U1 Care reproduces this handshake for extruder, extruder1, extruder2 and extruder3, closing the socket after the initial full status. It reads switch_count and last_maintenance_count, as U1Deck's model and diagnostics do. Since-service is switch_count minus last_maintenance_count only when both exist and the result is nonnegative.

| Inspected source | SHA-256 |
| --- | --- |
| `src/moonraker.mjs` | `5eb30ee39b413309068590cf3a2ea08459358f77c4fd82f8b45e025651c442a6` |
| `src/model.mjs` | `fe9ba03cc5e06da5fcc03d74f65637a8996b1189aaf3fc9b9cd7c6c3f2f1578f` |
| `src/diagnostics.mjs` | `079de06cc4c1f6f7f47040cba4d2a8e460b8954cc1f09282b08989891c6273bb` |

The fixture tests/fixtures/u1deck-heads.json retains only those eight numeric fields from the real local u1-websocket capture dated 2026-10-31 (firmware 2.0.0). Network addresses, device identity, jobs, credentials and other raw discovery records are excluded. The four counts sum to 1081. Remaining reset and partial-data cases use synthetic inputs.

U1 Care polls once per 60 seconds rather than maintaining U1Deck's continuous display subscription. Counter history uses persisted full snapshots and positive deltas; it never counts active-tool transitions or sums repeated snapshots.
