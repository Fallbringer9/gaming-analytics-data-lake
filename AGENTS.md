# Gaming Analytics Data Lake

## Développement

- Utiliser `uv` et Python 3.13 pour le développement local. Placer le code Python dans `src/gaming_analytics_data_lake/` et les tests dans `tests/`.
- Avancer une étape à la fois. Expliquer les commandes et faire valider les choix de conception avant de les appliquer.
- Attendre la validation de l’utilisateur avant de commencer Terraform ou AWS Glue.

## Données et règles métier

- Utiliser des données synthétiques. Relier `players` et `transactions` par `player_id`.
- Calculer le flux net en soustrayant les retraits validés des dépôts validés. Inclure uniquement les transactions au statut `completed`.

## Accès AWS

- Pour les commandes AWS locales, utiliser le profil `admin-bootstrap` et la région `eu-west-3`. Passer explicitement `--profile admin-bootstrap --region eu-west-3` aux commandes AWS CLI.
- Garder les identifiants, les clés et les jetons AWS hors du dépôt et des sorties partagées.

## Tests et qualité du code

- À chaque changement de comportement, ajouter ou mettre à jour les tests correspondants. Pour une correction de bug, ajouter un test qui reproduit le problème. Les tests unitaires doivent fonctionner sans réseau ni accès AWS.
- À chaque étape de développement, lancer `uv run pytest`, `uv run ruff check .` et `uv run ruff format --check .`.
- Indiquer les résultats des trois commandes. Corriger les échecs liés au changement avant de présenter l’étape comme terminée et signaler les vérifications qui n’ont pas pu être lancées.