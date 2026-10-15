# U1 Care

**Le suivi d’entretien de la Snapmaker U1, dans Home Assistant et sur Stream Deck.**

U1 Care permet de savoir quel entretien prévoir, de retrouver sa procédure et de garder une trace de ce qui a été fait. Les périodicités disponibles viennent de la documentation Snapmaker : il n’y a pas à saisir chaque intervalle à la main.

Chaque entretien a sa propre date de réalisation et sa prochaine échéance. Valider les courroies, par exemple, ne remet pas à zéro les guidages ou les contacts des têtes.

## Dans Home Assistant

Après l’ajout de la U1, un tableau de bord se crée automatiquement dans la barre latérale. Il rassemble les jours ou les cycles restants, l’état des entretiens et les liens vers leurs procédures.

- **OK** : le suivi est à jour.
- **SOON** : l’entretien approche.
- **DUE** : l’échéance est atteinte ou dépassée.
- **INCONNU** : une date ou un compteur manque pour calculer l’échéance.
- **SI BESOIN** : l’intervention dépend d’une situation particulière.

Les cases restent compactes. Le lien **Voir la procédure** ouvre le détail, la référence officielle et le bouton **Valider l’entretien effectué**. La validation met à jour uniquement l’entretien concerné et reste enregistrée après un redémarrage de Home Assistant.

Le tableau de bord peut ensuite être modifié avec l’éditeur habituel de Home Assistant. Les mises à jour d’U1 Care préservent ses personnalisations. [En savoir plus sur le tableau de bord](DASHBOARD.md).

![Tableau de bord U1 Care : états, décomptes et accès aux procédures](docs/images/u1-care-dashboard.png)

*Ces captures montrent le mode démonstration : les dates et les compteurs sont fictifs.*

<details>
<summary>Voir quelques pages de procédure</summary>

### Guidages et roulements

![Procédure des guidages et roulements](docs/images/u1-care-procedure-guidages.png)

### Vis et écrous Z

![Procédure des vis et écrous Z](docs/images/u1-care-procedure-vis-z.png)

### Calibration XYZ

![Procédure de calibration XYZ](docs/images/u1-care-procedure-calibration-xyz.png)

</details>

### Installation avec HACS

**Home Assistant 2026.8.2 minimum.**

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rmncld&repository=U1Care&category=integration)

1. Ouvrir le lien HACS, ajouter le dépôt personnalisé et télécharger **U1 Care**.
2. Redémarrer Home Assistant.
3. Aller dans **Paramètres → Appareils et services → Ajouter une intégration → U1 Care**.
4. Renseigner l’adresse IP locale de la U1.

Si le lien ne fonctionne pas, ajouter `https://github.com/rmncld/U1Care` dans **HACS → menu ⋮ → Dépôts personnalisés**, catégorie **Intégration**.

La connexion se fait directement depuis Home Assistant. Aucun ordinateur supplémentaire n’a besoin de rester allumé. Si l’accès de l’imprimante exige une clé API, U1 Care la demande dans un second écran.

Un **mode démonstration** permet de découvrir le tableau de bord sans posséder de U1 ni renseigner d’adresse IP réelle.

Pour une installation manuelle, copier le dossier `custom_components/u1_companion` dans `/config/custom_components/`, puis redémarrer Home Assistant.

### Dates et suivi

Une date d’entretien déjà réalisé ne peut pas être devinée à partir de l’adresse IP. Si elle manque, l’état reste **INCONNU**. Il est possible de renseigner une date de mise en service une seule fois dans **Configurer → Date de mise en service**. Les entretiens enregistrés ensuite conservent leur propre date.

Le préavis **SOON** est un réglage de l’application, fixé par défaut à sept jours. Il ne remplace pas la périodicité indiquée par Snapmaker.

### Mises à jour et sauvegardes

Les mises à jour se téléchargent depuis HACS. Elles conservent le suivi existant ; il suffit de redémarrer Home Assistant lorsque cela est demandé. Ne pas supprimer l’intégration pour la mettre à jour.

Le suivi est inclus dans les sauvegardes Home Assistant. Une copie peut aussi être récupérée avec **Télécharger les diagnostics** dans le menu de l’intégration. La partie `maintenance_backup` contient les entretiens et leurs notes, sans l’adresse réseau ni la clé API. Elle peut être restaurée via **Configurer → Importer un ancien suivi**.

Pour changer d’adresse IP ou de clé API, utiliser **Reconfigurer** dans le menu de l’intégration. Les entretiens sont conservés.

## Sur Stream Deck

Le plugin **U1 Care 0.2.3** permet de garder les rappels à portée de main pendant l’utilisation de l’imprimante.

Chaque touche peut afficher un entretien précis, une catégorie ou l’état général. Son symbole, son texte et son décompte suivent le choix fait dans le sélecteur de la touche. Les couleurs reprennent celles du tableau de bord : vert lime, orange et rouge.

Un appui sur une touche d’entretien ouvre directement sa procédure dans le navigateur, avec la checklist, le lien officiel et la validation. Par exemple, la touche **Courroies** ouvre **Courroies XY**. Les touches de catégorie ouvrent leurs procédures disponibles ; la touche **État général** affiche le bilan.

### Installation et utilisation

1. Ouvrir le fichier d’installation U1 Care portant l’extension `.streamDeckPlugin` avec l’application Stream Deck.
2. Ajouter l’action **U1 Care → Suivi de maintenance** sur une touche.
3. Choisir l’entretien à afficher dans le sélecteur **Afficher sur cette touche**.
4. Appuyer sur la touche pour ouvrir sa procédure et consigner l’entretien après l’avoir effectué.

L’application Stream Deck doit rester ouverte pour accéder au suivi local du plugin. Appuyer sur une touche ne valide pas automatiquement un entretien.

### Home Assistant et Stream Deck

Les deux versions utilisent le même catalogue d’entretien, mais gardent actuellement **des suivis séparés**. Une validation dans Home Assistant ne met donc pas automatiquement à jour le plugin Stream Deck, et inversement. Les touches du plugin ouvrent leur suivi local, pas le tableau de bord Home Assistant.

Pour reprendre un suivi Stream Deck dans Home Assistant, exporter son fichier JSON, puis utiliser **Configurer → Importer un ancien suivi** dans l’intégration. Cet import est facultatif et ne modifie pas la connexion de l’imprimante.

## Entretiens disponibles

| Entretien | Fréquence du catalogue |
| --- | --- |
| Guidages et roulements | Mensuel |
| Tiges carbone X | Mensuel |
| Vis et écrous Z | Trimestriel |
| Goupilles et billes | Trimestriel |
| Courroies XY | Mensuel et selon les alertes de l’écran |
| Contacts pogo | 4 à 6 mois ; rappel machine à 100 000 changements de tête |
| Calibration XYZ | Selon les conditions indiquées par Snapmaker : remplacement, choc ou décalage, notamment |

Les procédures résumées donnent accès aux guides officiels et à leurs illustrations. Pour une intervention, suivre les précautions et les instructions complètes de Snapmaker. [Consulter les sources du catalogue](SOURCES.md).

## Lecture des heures de la U1

La lecture automatique dépend de l’accès Moonraker proposé par le firmware de l’imprimante. U1 Care vérifie sa disponibilité avant d’utiliser les données. Dans Home Assistant, les ports HTTP 80 et 7125 sont essayés automatiquement ; les heures sont ensuite actualisées toutes les 60 secondes.

Les heures correspondent à l’historique d’impression conservé par Moonraker, hors impression en cours. Elles peuvent être incomplètes si cet historique a été effacé. L’intégration n’envoie aucune commande de mouvement ni de G-code à l’imprimante.

Les firmwares sans accès compatible, les ports personnalisés et les connexions exclusivement HTTPS ne sont pas pris en charge par cette version de l’intégration. La saisie manuelle reste disponible en secours. Les cycles de changement de tête ne sont pas lus automatiquement ; leur compteur peut être renseigné depuis l’écran de la U1.

Les dates des entretiens restent accessibles même lorsque l’imprimante est éteinte. Une perte de connexion ou une baisse de l’historique est signalée sans remettre le suivi à zéro.

---

U1 Care est un projet indépendant, sans affiliation avec Snapmaker, Home Assistant ou Elgato.
