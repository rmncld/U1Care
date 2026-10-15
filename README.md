# U1 Care pour Home Assistant · 0.3.6

**Logo U1 Care inclus localement** dans la fiche d’intégration, sans configuration.

**Nouveau : tableau de bord automatique.** Après l’ajout d’une U1 (ou Démonstration), son tableau de bord apparaît dans la barre latérale sans import. Il reste modifiable avec l’éditeur Home Assistant ; les mises à jour préservent les personnalisations. Les entrées existantes en bénéficient au redémarrage après mise à jour. [Détails et limites](DASHBOARD.md).

Une intégration autonome : **Ajouter une intégration → U1 Care → IP de la U1**.

La connexion est directe entre Home Assistant et l’imprimante. Aucun PC à maintenir allumé, pont Companion, YAML, MQTT ou intervalle d’entretien à saisir.

## Installer depuis HACS

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rmncld&repository=u1-companion-home-assistant&category=integration)

1. Cliquer sur **Ouvrir dans HACS**, confirmer le dépôt personnalisé puis télécharger **U1 Care**.
2. Redémarrer Home Assistant pour charger les fichiers installés.
3. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration → U1 Care**.
4. Entrer l’IP locale de la U1, par exemple `192.168.1.50`.

Si le lien ne s’ouvre pas : **HACS → menu ⋮ → Dépôts personnalisés**, ajouter `https://github.com/rmncld/u1-companion-home-assistant`, catégorie **Intégration**, puis télécharger U1 Care.

Home Assistant minimum : **2026.8.2** ; tests sur **2026.8.2** et **2026.10.1**. Le nom visible est **U1 Care**. L’identifiant interne `u1_companion` et l’URL GitHub sont conservés pour préserver les installations et liens existants. L’intégration est indépendante de Snapmaker et de Home Assistant. Elle est distribuée comme dépôt personnalisé HACS ; elle n’est pas annoncée comme incluse au catalogue HACS par défaut.

### Mise à jour

HACS suit le dépôt et propose les versions publiées. Une mise à jour des fichiers ne réinitialise pas le stockage des entretiens dans Home Assistant. Après mise à jour, redémarrer Home Assistant si HACS le demande.

### Installation manuelle de secours

Copier `custom_components/u1_companion` dans `/config/custom_components/`, puis redémarrer Home Assistant. Si la version 0.3.0 est déjà installée, sauvegarder Home Assistant et ajouter le dépôt dans HACS ; le domaine `u1_companion`, l’entrée existante et les identifiants sont conservés. Ne pas supprimer l’entrée d’intégration pour faire la mise à jour.

## Voir les informations

L’ajout crée un appareil et **dix entités** :

- sept entretiens, avec un état lisible tel que `OK · 26 j`, `SOON · 2000 cy`, `DUE · -5 j`, `INCONNU` ou `SI BESOIN` ;
- le bilan de maintenance général ;
- les heures de l’historique Moonraker ;
- la connexion U1.

Cliquer sur l’appareil dans la fiche de l’intégration pour voir les entités. Elles peuvent être ajoutées à votre tableau de bord avec les outils habituels de Home Assistant, sans YAML. Chaque entretien expose sa source, sa procédure résumée, sa date précédente, sa prochaine échéance, ses décomptes et le nombre d’événements enregistrés.

## Après un entretien

Dans la fiche de l’intégration, cliquer sur **Configurer → Consigner un entretien réalisé**. Choisir l’entretien, lire les étapes et le lien officiel, puis cocher les étapes effectuées et valider sa date réelle. Seul cet entretien est mis à jour. Les événements sont conservés dans le stockage de Home Assistant.

L’IP ne permet pas de connaître une date d’entretien non exposée par la U1. Ces références restent **INCONNU**, plutôt que d’utiliser artificiellement la date d’installation de l’intégration. Si la date de mise en service est connue, elle peut être renseignée une seule fois dans **Configurer → Date de mise en service** ; c’est facultatif. Les dates des entretiens déjà consignés gardent la priorité.

Les six opérations mécaniques et la calibration XYZ viennent du catalogue officiel déjà vérifié dans Companion. Les périodes sont intégrées. Une calibration conditionnelle peut être signalée via Configurer, puis consignée après réalisation.

## Connexion et heures

L’intégration essaie automatiquement les ports HTTP 80 et 7125 sur l’IP saisie. Elle vérifie le composant `history` et le champ `job_totals.total_print_time`, puis lit les heures toutes les 60 secondes. Elle n’envoie aucun G-code ni commande à la machine.

Si Moonraker exige une clé API, un second écran demande **la clé existante de l’imprimante**, uniquement dans ce cas. L’IP seule ne permet pas de contourner une authentification. Les firmwares qui n’exposent pas ces routes, les ports personnalisés, HTTPS seul et les autres mécanismes de connexion ne sont pas pris en charge par cette version.

Les heures correspondent à l’historique conservé, hors impression en cours ; ce n’est pas une attestation de compteur à vie. Une perte de connexion rend les heures indisponibles. Les dates de maintenance locales restent accessibles quand la U1 est éteinte. Une baisse de l’historique est signalée, sans écraser l’ancien compteur ; une reprise explicite est disponible dans Configurer.

Les cycles de tête ne sont pas récupérés automatiquement : aucun champ n’a été confirmé. La partie cycles du suivi pogo reste inconnue si son compteur n’est pas renseigné. Le calendrier pogo demeure visible et le rappel de l’écran U1 reste la référence pour les changements de tête. La saisie des compteurs de secours est facultative ; aucun intervalle n’est demandé.

Pour changer d’IP ou de clé, utiliser **Reconfigurer** dans le menu de l’intégration existante : les identifiants d’entités et les entretiens sont conservés.

## Sauvegardes et reprise du suivi Stream Deck

Le plugin Stream Deck 0.2.0 reste inchangé. Cette nouvelle intégration utilise son propre stockage Home Assistant : elle ne synchronise pas automatiquement deux historiques indépendants.

Pour reprendre les événements existants : exporter le JSON depuis Companion 0.2.0, puis utiliser **Configurer → Importer un ancien suivi**. Cet import facultatif préserve les événements et les références officielles, sans modifier l’IP ou les clés de l’intégration. Une copie du suivi précédent est sauvegardée avant import. Les tâches personnelles historiques sont conservées dans les données importées et le bilan général ; les sept capteurs dédiés correspondent au catalogue officiel.

Le stockage est inclus dans les sauvegardes habituelles de Home Assistant. **Télécharger les diagnostics** dans le menu de l’intégration permet aussi d’obtenir `maintenance_backup`, réimportable dans ce même formulaire. Ce fichier contient le suivi et ses notes ; il exclut l’adresse réseau et la clé API. Supprimer l’intégration supprime son stockage local : conserver une sauvegarde si nécessaire.

## Preuves et limites

Voir [les sources](SOURCES.md). Les validations du dépôt sont disponibles dans l’onglet Actions. Les essais utilisent le vrai moteur Home Assistant Core et une U1 simulée. Aucune U1 physique, instance Home Assistant de l’utilisateur ou interface graphique Home Assistant OS n’a été connectée.

