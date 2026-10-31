# U1 Care 0.4.2

Restore the U1 Care logo alongside the printer name. The 0.4.0 custom-name banner had replaced the image along with the old heading. Existing U1 Care dashboards receive a repair only if their banner still matches that exact generated text. The previous dashboard configuration is backed up before this edit. Customized headers and other dashboards, including LEMYO Hub, are left untouched. Maintenance storage, commissioning dates, events and counter references are unchanged.

## HACS update detection

HACS provides the update entity; U1 Care does not add a competing updater or change HACS settings. Its GitHub releases are stable, versioned tags with matching integration manifests. In HACS 2.0.5, custom repositories are automatically refreshed every 48 hours, with queued repository work processed periodically. The refresh notifies update entity listeners. This is periodic detection, not an immediate push from GitHub. The entity's update availability appears in Home Assistant's updates interface; this does not imply a separate mobile or persistent notification.

Upstream implementation: [scheduled refresh and listener notification](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/base.py), [release discovery](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/repositories/base.py), [update entity](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/update.py). Manual **Update information** also refreshes the update entity, but it is not proof that the periodic refresh has run.

Install the release through HACS and restart Home Assistant, retaining the existing integration. No removal or re-addition is needed.
