# Tableau de bord U1 Care

La version 0.3.4 ajoute la validation d’un entretien depuis sa page de procédure, après confirmation que toutes les étapes ont été effectuées aujourd’hui. Seul l’entretien ciblé est enregistré. Aucun ordre n’est envoyé à l’imprimante. Pour une intervention passée, utiliser le formulaire Configurer habituel et sa date réelle.

Pour distribuer la présentation : ouvrir **U1 Care → Configurer → Modèle de tableau de bord**. Copier le contenu généré, créer un tableau de bord vide avec l’URL indiquée et coller le contenu dans son éditeur de configuration brute. Les identifiants sont résolus depuis le registre de cette installation : aucune saisie des entités, des heures ou des intervalles n’est demandée. Les dates inconnues ne sont pas inventées.

Le modèle reste entièrement modifiable avec l’éditeur Home Assistant. La génération n’écrit et ne remplace aucun tableau de bord existant. Le choix du tableau de bord par défaut appartient à chaque utilisateur dans ses paramètres de profil. L’intégration ne modifie pas les préférences personnelles des autres comptes.

Les fonctions utilisent des cartes natives. La charte sombre et les couleurs conditionnelles utilisent **card-mod** lorsqu’il est installé ; sans cette extension, les cartes gardent les fonctions et le thème Home Assistant. Le logo est chargé depuis le dépôt GitHub ; les entretiens et leur validation restent locaux.

Le modèle suit l’entrée sélectionnée : démonstration et imprimante réelle restent séparées. Un appareil de démonstration est clairement signalé. Les mises à jour de U1 Care ne réécrivent pas les personnalisations du tableau de bord.
