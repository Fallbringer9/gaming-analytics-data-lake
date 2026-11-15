# Gaming Analytics Data Lake

J’ai réalisé ce projet dans une démarche pédagogique pour approfondir mes connaissances en data engineering et développer ma capacité à travailler en collaboration avec un agent Codex.

Data lake AWS pour analyser des transactions de jeu synthétiques. La V1 traite des lots CSV, conserve la dernière version valide de chaque transaction et expose des indicateurs financiers par joueur et par jour dans Athena.

## Architecture V1

```text
CSV synthétiques
    │
    ▼
S3 Bronze ──► AWS Glue 5.0 / PySpark ──► Silver Iceberg sur S3
                        │                         │
                        ▼                         ▼
                   Quarantaine S3          Agrégats SQL dans Athena
                                                  │
                                                  ▼
                                           Gold Iceberg sur S3 ──► Requêtes Athena
```

| Couche | Rôle |
| --- | --- |
| Bronze | CSV bruts de référence des joueurs et lots de transactions, conservés séparément. |
| Quarantaine | Rapports JSON Lines par lot et par exécution, avec les valeurs reçues, le fichier source et les motifs de rejet. |
| Silver | Table Iceberg `gaming_analytics_silver.transactions`. Le `MERGE` utilise `transaction_id` et applique une mise à jour lorsque `updated_at` est plus récent. |
| Gold | Table Iceberg `gaming_analytics_gold.player_daily_finance`, avec une ligne par joueur et par jour UTC de création de la transaction. |
| Athena | Groupe de travail dédié, résultats chiffrés dans S3 et limite de 100 Mio scannés par requête. |

### Règles métier

- Les dépôts et retraits au statut `completed` alimentent le flux net, calculé comme **dépôts validés − retraits validés**.
- Les dépôts au statut `failed` alimentent le compteur d’échecs.
- Glue contrôle l’identifiant de transaction, le joueur, le montant positif au format `DECIMAL(18, 2)`, les horodatages avec fuseau, le type et le statut. La V1 accepte les types `deposit` et `withdrawal` et les statuts `completed` et `failed`.
- Une mise à jour rejetée laisse la dernière version valide dans Silver.

## Arborescence

| Dossier | Contenu |
| --- | --- |
| [`data/`](data/) | CSV synthétiques de départ. |
| [`infra/`](infra/README.md) | Modules Terraform pour S3, IAM, Glue et Athena. |
| [`sql/gold/`](sql/gold/) | Création, rafraîchissement et consultation de la table Gold. |
| [`src/`](src/) et [`tests/`](tests/) | Calcul de référence Python et tests locaux. |

## Reproduire la démonstration

### 1. Vérifier les tests locaux

Avec Python 3.13 et `uv`, depuis la racine du dépôt.

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Glue fournit PySpark et `awsglue` lors de l’exécution du job sur AWS.

### 2. Déployer l’infrastructure

Préparer la CLI AWS, Terraform et un profil AWS autorisé à gérer les ressources du projet. Pour un nouvel environnement, exécuter les commandes ci-dessous et examiner le plan avant de l’appliquer. Pour reprendre un déploiement existant, utiliser son état Terraform. Le [guide d’infrastructure](infra/README.md) décrit la configuration locale et les modules.

```bash
export AWS_PROFILE=mon-profil-aws
export AWS_REGION=eu-west-3

terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra plan
terraform -chdir=infra apply
```

### 3. Charger Bronze et exécuter Glue

Ces commandes chargent le lot initial dans un nouveau bucket Bronze. Sur un bucket déjà alimenté, conserver les fichiers chargés en utilisant un nouvel identifiant pour chaque nouveau lot.

```bash
bronze_bucket="$(terraform -chdir=infra output -raw bronze_bucket_name)"
glue_job="$(terraform -chdir=infra output -raw glue_job_name)"

aws s3api put-object --bucket "$bronze_bucket" --body data/players.csv \
  --key bronze/players/batch_id=001/players.csv --if-none-match '*' \
  --server-side-encryption AES256 --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws s3api put-object --bucket "$bronze_bucket" --body data/transactions.csv \
  --key bronze/transactions/batch_id=001/transactions.csv --if-none-match '*' \
  --server-side-encryption AES256 --profile "$AWS_PROFILE" --region "$AWS_REGION"

run_id="$(aws glue start-job-run --job-name "$glue_job" \
  --arguments '{"--batch_id":"001","--players_batch":"001"}' \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query JobRunId --output text)"

aws glue get-job-run --job-name "$glue_job" --run-id "$run_id" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query JobRun.JobRunState --output text
```

Relancer la dernière commande jusqu’à ce que le job indique `SUCCEEDED`. En cas d’échec, consulter le détail de l’exécution dans Glue avant de continuer. La table Silver contient alors six transactions sur un déploiement neuf. Les éventuels rejets se trouvent dans `quarantine/transactions/glue/batch_id=<lot>/run_id=<exécution>/` sur Bronze.

### 4. Rafraîchir et consulter Gold

Dans l’éditeur Athena, choisir le groupe de travail renvoyé par `terraform -chdir=infra output -raw gold_athena_workgroup`.

1. Exécuter [la création de table](sql/gold/create_player_daily_finance.sql), en remplaçant `${gold_bucket}` par la sortie de `terraform -chdir=infra output -raw gold_bucket_name`.
2. Exécuter [le rafraîchissement Gold](sql/gold/refresh_player_daily_finance.sql).
3. Exécuter [la requête de consultation](sql/gold/select_player_daily_finance.sql).

### 5. Vérifier l’incrémental et la quarantaine

Pour rejouer la démonstration, créer deux CSV d’une seule transaction avec l’en-tête suivant.

```csv
transaction_id,player_id,transaction_type,amount,status,created_at,updated_at
```

| Lot de transactions | Ligne à placer dans le CSV |
| --- | --- |
| `test-quarantine-001` | `T003,P001,deposit,abc,completed,2026-11-03T11:00:00Z,2026-11-03T12:00:00Z` |
| `002` | `T003,P001,deposit,50.00,completed,2026-11-03T11:00:00Z,2026-11-03T13:00:00Z` |

Déposer chaque fichier sous `bronze/transactions/batch_id=<lot>/`, puis lancer Glue avec le `--batch_id` correspondant. Attendre la fin de chaque exécution avant la suivante. Exécuter d’abord le lot invalide, puis le lot valide, puis rejouer le lot valide. Rafraîchir Gold après chaque contrôle.

| Contrôle | Flux net P001 | Dépôts échoués P001 | Vérification |
| --- | ---: | ---: | --- |
| Lot initial `001` | 70,00 | 1 | Six transactions Silver. |
| Lot invalide | 70,00 | 1 | Un rejet `invalid_amount`, même snapshot Silver. |
| Lot valide `002` | 120,00 | 0 | Mise à jour de `T003`, six transactions Silver. |
| Rejeu de `002` | 120,00 | 0 | Six transactions uniques et mêmes lignes Gold. |

Le flux net de `P002` reste à −15,00. La table Gold contient deux lignes pour le 3 novembre 2026.

## Corrections issues de la revue V1

| Problème observé | Correction |
| --- | --- |
| Une date `created_at` mal formée pouvait entrer dans Silver et faire échouer Gold. | Glue place en quarantaine les dates de création absentes ou invalides avec `invalid_created_at`. |
| Un type ou un statut inconnu pouvait passer dans Silver et fausser les KPI. | Les valeurs hors du contrat V1 sont rejetées avec `invalid_transaction_type` ou `invalid_status`. |
| Deux versions différentes pouvaient partager le même identifiant et le même horodatage, notamment entre deux lots. | Glue compare les valeurs métier typées. Les versions contradictoires sont isolées avec `conflicting_transaction_version`. Une répétition équivalente correspond à un rejeu. |

Le [lot synthétique de régression](tests/fixtures/glue_validation_regression.csv)
peut être chargé sous `bronze/transactions/batch_id=test-validation-v1/` après le
lot `002`. Il doit produire six rejets et conserver les six transactions Silver
ainsi que les KPI Gold de la démonstration.

## Sécurité et périmètre

- Les buckets bloquent l’accès public. Silver et Gold imposent HTTPS et configurent explicitement le chiffrement SSE-S3. Le rôle Glue limite ses accès aux préfixes nécessaires et à la table Silver.
- Les identifiants restent dans le profil AWS local. La configuration locale du fournisseur, les états Terraform et les plans sont ignorés par Git.
- Le chargement et le rafraîchissement se lancent manuellement. Gold relit Silver à chaque rafraîchissement. Les tests de référence utilisent de petits lots synthétiques.
- La V2 prévoit un agent Bedrock qui sélectionne des requêtes Athena prédéfinies et paramétrées. Le backend contrôle leur exécution. Une interface JavaScript légère affichera les résultats en tableau et en graphique.

## Catalogue SQL V2

Les requêtes sont des `SELECT` versionnés sur la table Gold. Les valeurs se
transmettent dans l’ordre des `?` avec les paramètres d’exécution Athena.
Les dates sont en UTC, au format `AAAA-MM-JJ`. Le début est inclus et la fin exclue.

| Requête | Paramètres dans l’ordre |
| --- | --- |
| [`get_player_finance`](sql/agent/get_player_finance.sql) | Joueur, début, fin |
| [`get_net_flow_by_player`](sql/agent/get_net_flow_by_player.sql) | Début, fin |
| [`get_finance_overview`](sql/agent/get_finance_overview.sql) | Début, fin |
| [`get_daily_finance_trend`](sql/agent/get_daily_finance_trend.sql) | Début, fin, joueur facultatif (transmettre `NULL` dans Athena pour tous les joueurs) |
| [`get_failed_deposits`](sql/agent/get_failed_deposits.sql) | Début, fin |
| [`get_top_depositors`](sql/agent/get_top_depositors.sql) | Début, fin, nombre de joueurs (1 à 100) |
| [`get_max_deposit`](sql/agent/get_max_deposit.sql) | Début, fin |
| [`get_large_deposits`](sql/agent/get_large_deposits.sql) | Début, fin |

Pour vérifier le 3 novembre 2026, utiliser le groupe de travail
`gaming-analytics-gold` et les dates `'2026-11-03'` et `'2026-11-04'`.
La première requête, avec `'P001'` en premier paramètre, renvoie un flux net de
120,00. La seconde renvoie 120,00 pour `P001` et −15,00 pour `P002`.

Le cas d’usage valide les dates et l’identifiant du joueur. L’adaptateur Athena
charge les fichiers SQL depuis un dossier configuré côté serveur et appelle Athena
avec les valeurs validées. Les décimaux sont conservés sous forme de texte
dans les résultats pour garder leur précision.

### Architecture de l’agent

`agent/domain/` porte le catalogue, ses règles de validation et ses modèles.
Le cas d’usage `AnalyticsAgent.ask` dépend des ports `ToolSelector` et
`QueryExecutor`. Les adaptateurs Bedrock et Athena implémentent ces ports.
Le point d’entrée assemble les adaptateurs avec leurs clients AWS respectifs.

### Dépôts individuels Gold

Les deux outils de dépôts individuels interrogent
`gaming_analytics_gold.completed_deposits`, qui contient uniquement les dépôts
validés. Dans le groupe de travail Gold, exécuter
[la création de table](sql/gold/create_completed_deposits.sql) en remplaçant
`${gold_bucket}` par le nom du bucket, puis
[le rafraîchissement](sql/gold/refresh_completed_deposits.sql) après chaque mise
à jour de Silver. Rafraîchir aussi la table des KPI journaliers.

`get_large_deposits` renvoie les 100 montants les plus élevés parmi les dépôts
validés strictement supérieurs à **10 000** sur la période. Un montant exactement
égal à 10 000 est exclu. Cette requête n'accepte pas de seuil fourni par le modèle.

### Régions AWS de la V2

- `ATHENA_REGION` correspond à la région des données et du groupe de travail,
  `eu-west-3` pour le déploiement actuel.
- `BEDROCK_REGION` sera configurée indépendamment lors du raccordement de
  Bedrock. Vérifier la disponibilité du modèle ou du profil d’inférence, les
  permissions IAM et les restrictions de région applicables avant le premier
  appel. Pour un profil interrégional, vérifier aussi ses régions de destination.

### Tester l’agent Claude

Depuis la racine du dépôt, avec un profil AWS autorisé à interroger Gold
et à invoquer le profil d’inférence européen de Claude Haiku 4.5.

```bash
export AWS_PROFILE=mon-profil-aws
export ATHENA_REGION=eu-west-3
export BEDROCK_REGION=eu-north-1
export BEDROCK_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0

uv run --extra agent python -m gaming_analytics_data_lake.agent \
  "Quel est le flux net par joueur le 3 novembre 2026 ?"
```

Bedrock reçoit la question et les descriptions des outils disponibles. Python
valide l’outil et ses paramètres avant de lancer le SQL. La commande renvoie
en JSON le nom de la requête, les paramètres et les lignes Athena.

Stockholm est la région d’appel du profil européen. L’inférence peut être
traitée dans l’une de ses régions de destination. Athena et les tables Gold
restent à Paris.

- Pour `Converse`, accorder `bedrock:InvokeModel` sur l’ARN du profil source
  et sur les ARN des modèles de toutes ses destinations. Vérifier aussi les
  restrictions régionales de l’organisation si elles s’appliquent.
- Vérifier séparément l’accès Anthropic au niveau du compte. Le profil Haiku 5.5
  était actif et autorisé dans la simulation IAM, mais son invocation a été
  refusée pour le compte de test. Haiku 4.5 a réussi les deux parcours.
- Le profil utilisé localement doit aussi avoir accès au groupe de travail
  Athena, au catalogue Gold et au préfixe S3 de résultats.

Références AWS concernant [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html),
[les profils d’inférence géographiques](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)
et [l’accès aux modèles](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

### Scénario de bout en bout V2

Le [lot synthétique E2E](data/scenarios/transactions_e2e.csv) contient 15 dépôts
de 40 à 25 000, datés du 4 au 10 novembre 2026. Il inclut des dépôts validés de
9 999,99, 10 000 et 10 000,01 ainsi qu’un dépôt échoué au-dessus de 10 000.

Pour reproduire le scénario, charger ce CSV sous
`bronze/transactions/batch_id=test-agent-e2e-015/`, lancer Glue avec ce lot et
le référentiel joueurs `001`, puis rafraîchir les deux tables Gold. Dans l’agent,
interroger la période du 4 au 10 novembre 2026 inclus. L’outil des gros dépôts
doit retourner 10 000,01 et les autres dépôts validés au-dessus du seuil.
