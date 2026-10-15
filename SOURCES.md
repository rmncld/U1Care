# Sources et portée

Le catalogue `custom_components/u1_companion/catalog.json` est identique à celui de Companion 0.2.0, version **2026.10.15.1**. Aucun nouvel intervalle n’a été créé pour cette intégration.

- [Guide officiel U1](https://wiki.snapmaker.com/en/snapmaker_u1/troubleshooting/Core_Components_Maintenance_Guide) : fréquences mensuelles, trimestrielles, plage de 4 à 6 mois pour les contacts et calibration XYZ conditionnelle ; source consultée le 15/10/2026, mise à jour affichée le 21/09/2026.
- [FAQ officielle U1](https://wiki.snapmaker.com/en/FAQ/u1) : rappel des contacts tous les 100 000 changements de tête et pile Klipper / Moonraker / Fluidd.
- [Code officiel Snapmaker Moonraker](https://github.com/Snapmaker/u1-moonraker/blob/main/moonraker/components/history.py) : les heures viennent du total de l’historique, qui peut être réinitialisé.
- [API officielle du dépôt Snapmaker](https://github.com/Snapmaker/u1-moonraker/blob/main/docs/web_api.md) : routes de lecture et mécanismes d’accès.
- [Flux de configuration Home Assistant](https://developers.home-assistant.io/docs/core/integration/config_flow/) : ajout depuis l’interface, reconfiguration et schémas de formulaires.
- [Flux d’options Home Assistant](https://developers.home-assistant.io/docs/core/integration/options_flow/) : formulaires de maintenance, sans YAML.
- [Actualisation des entités](https://developers.home-assistant.io/docs/integration_fetching_data/) : coordinateur unique et actualisation partagée.
- [Stockage Home Assistant 2026.10.1](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/helpers/storage.py) : stockage local des événements.

Les ports 80 et 7125 sont des accès candidats vérifiés à l’ajout, pas une garantie d’exposition sur tout firmware. L’intégration ne déduit pas une identité matérielle ou un numéro de série de la seule présence de Moonraker. Les identifiants d’entités utilisent l’identifiant persistant de l’entrée Home Assistant, qui survit à un changement d’IP.

SOON utilise un préavis applicatif de 7 jours, sauf pour la plage officielle pogo : SOON à 4 mois, DUE à 6 mois. Le préavis cycles de 5 000 est applicatif. Le premier seuil connu atteint remonte l’entretien. Aucune conversion arbitraire des mois en heures n’est faite.

L’intégration mesure les mois calendaires dans le fuseau horaire configuré dans Home Assistant. Les entretiens consignés par date seule sont sauvegardés avec cette précision ; une opération antidatée ne reçoit pas les compteurs actuels. Aucun accès réseau n’est utilisé pour les calculs ou la validation d’une intervention.
