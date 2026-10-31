# U1 Care 0.4.1

The pogo contacts card now shows both remaining days and remaining toolhead changes, for example **OK · 180 j restants · 98919 changements restants**. Previously it displayed only the deadline with the highest severity, hiding the change count when both deadlines were OK.

The sensor exposes both deadlines, so existing overview cards, procedure pages and entity details update automatically. Missing readings are explicitly shown as unknown. Overdue days or changes are identified as exceeded. The existing warning and due thresholds are unchanged.

This is a display correction. It does not migrate or reset storage, change the commissioning date, record maintenance, alter counter baselines or edit any dashboards. LEMYO Hub is untouched. Existing dates and maintenance events are retained.

Update U1 Care in HACS and restart Home Assistant, keeping the existing integration. No removal, re-addition or dashboard replacement is needed.

Validation covers both visible deadlines, all severity combinations, missing readings, overdue values, unchanged input data and a native Home Assistant maintenance/restart round trip. The full suite and HACS validation run before release publication.
