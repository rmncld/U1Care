# U1 Care 0.6.0

The toolhead card is a single front-facing illustration of the four-head docking support, inspired by the supplied machine reference. It no longer uses a table. T1–T4 remain aligned with individual counts below and the complete total underneath. There is no cyan marker or colored mounted-head outline. Mounted state is indicated only by the text **Montée**, **Au parc** or **Position inconnue**.

Appearance follows the verified U1Deck objects: `filament_detect.info[i].RGB_1` takes priority over `print_task_config.filament_color_rgba[i]`. The fallback is explicitly labeled **Couleur du travail**; it is not presented as an RFID measurement. A color is displayed only when the corresponding `filament_motion_sensor e{i}_filament` confirms filament presence. Missing or absent filament uses neutral rendering and an explicit label. The physical yellow trim of the illustration is separate from the color of the filament tube and identification band.

Mounted state requires a non-parked physical `state` together with `active_pin`. The selected `toolhead.extruder` is not used to infer attachment. Missing or contradictory readings remain unknown. Every snapshot replaces the previous appearance, so a lost connection does not retain a stale color or mounted label as current. Refresh uses the existing 60-second polling interval. No printer movement or configuration commands are sent.

The locally rendered SVG accepts only bounded color, count and state parameters; it never reads printer credentials or maintenance data. Only the exact standard U1 Care card is upgraded, with the existing backup mechanism. Custom cards, dates, maintenance history, counter baselines and LEMYO Hub remain unchanged.

Update through HACS and restart Home Assistant, retaining the existing integration.
