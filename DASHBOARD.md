# Tableau de bord automatique · U1 Care 0.3.5

Après installation HACS et redémarrage, ajouter une U1 avec son IP ou choisir Démonstration : son tableau de bord apparaît automatiquement dans la barre latérale. Aucun import ni saisie des entités. Les entrées existantes en bénéficient au redémarrage après mise à jour. Un tableau U1 Care contenant déjà les entités de cette entrée est repris sans réécriture.

Le tableau utilise le stockage Lovelace natif. Un administrateur peut modifier ses cartes, ses vues et son titre dans Home Assistant. Les personnalisations sont conservées aux mises à jour et redémarrages. Un tableau supprimé volontairement n’est pas recréé. La suppression de l’intégration ne détruit pas les tableaux personnalisés.

Chaque U1 possède son propre suivi et son tableau. Les démonstrations restent identifiées. Chaque utilisateur choisit son tableau par défaut dans son profil ; l’intégration ne remplace pas les préférences des autres comptes.

Chaque procédure permet de valider l’entretien après confirmation de toutes les étapes effectuées aujourd’hui. Seul cet entretien est enregistré. Pour une intervention passée, utiliser Configurer et sa date réelle. Aucun ordre envoyé à l’imprimante.

Les cartes natives fonctionnent sans autre extension. La charte et les couleurs conditionnelles utilisent card-mod lorsqu’il est installé. Le logo provient de GitHub. Configurer → Exporter le modèle reste disponible en option.

Compatibilité testée : Home Assistant Core 2026.8.2 et 2026.10.1. Home Assistant ne fournit pas de fonction publique de création de tableau de bord à une intégration : un adaptateur isolé retrouve sa collection native depuis l’enregistrement WebSocket. Il n’appelle pas de commande WebSocket et ne simule pas de compte utilisateur. La création, l’édition, le renommage, le rechargement, la suppression volontaire, la reprise et l’isolation des U1 sont testés avec les composants Lovelace réels. Une évolution de cette API interne peut nécessiter une mise à jour ; elle ne doit pas empêcher le suivi d’entretien de fonctionner.
