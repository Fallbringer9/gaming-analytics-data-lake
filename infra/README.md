# Infrastructure AWS

```text
infra/
├── main.tf                 # Assemble les modules
├── versions.tf             # Déclare le fournisseur AWS
├── outputs.tf              # Expose les sorties utiles
├── moved.tf                # Migre les adresses des ressources existantes
└── modules/
    ├── bronze/             # CSV bruts
    │   ├── main.tf
    │   ├── outputs.tf
    │   └── versions.tf
    ├── silver/             # Stockage Iceberg
    │   ├── main.tf         # Bucket privé, chiffrement au repos et HTTPS obligatoire
    │   ├── outputs.tf      # Emplacement du warehouse
    │   └── versions.tf
    ├── glue-iam/           # Rôle d’exécution et accès Bronze/Silver
    └── glue-job/           # Job PySpark, catalogue, journaux et droits associés
        ├── main.tf
        ├── permissions.tf
        ├── transactions.py
        ├── variables.tf
        ├── outputs.tf
        └── versions.tf
```

## Authentification locale

Terraform utilise un profil AWS configuré sur la machine. Les identifiants restent
dans la configuration AWS locale. Le fichier facultatif `infra/providers.tf`,
le fichier d’état et les plans Terraform sont ignorés par Git.
Le fichier `.terraform.lock.hcl` est destiné à être versionné.

Depuis la racine du dépôt, dans un clone sans `infra/providers.tf`, sélectionne
ton profil AWS et la région du projet avant de vérifier la configuration.

```bash
export AWS_PROFILE=mon-profil-aws
export AWS_REGION=eu-west-3
terraform -chdir=infra init
terraform -chdir=infra validate
terraform -chdir=infra plan
```

Le déploiement existant utilise un état local dans `infra/terraform.tfstate`.
Pour le gérer depuis une autre machine, il faut disposer de cet état avant de
lancer un déploiement.

## Warehouse Iceberg Silver

Récupérer l’emplacement S3 à fournir à Glue depuis la racine du dépôt.

```bash
terraform -chdir=infra output -raw silver_warehouse_uri
```

## Rôle d’exécution Glue

Le rôle donne à Glue un accès en lecture aux préfixes `bronze/players/` et
`bronze/transactions/`, ainsi qu’un accès en lecture et en écriture à
`warehouse/` dans Silver. La politique du job ajoute des accès limités à la table
du catalogue, au script, aux journaux et aux préfixes de sortie du job. La suppression
S3 est limitée aux fichiers temporaires. Les rapports de quarantaine sont écrits
en JSON Lines avec chiffrement AES-256.

```bash
terraform -chdir=infra output -raw glue_execution_role_arn
```

## Job Bronze vers Silver

Le job prend un `--batch_id` explicite. Le lot de référence des joueurs se
sélectionne avec `--players_batch` et vaut `001` par défaut. Les lignes rejetées
sont conservées sous `quarantine/transactions/glue/`, par lot et par exécution.
Les transactions valides alimentent `gaming_analytics_silver.transactions`.
L’écriture Iceberg retient la version la plus récente. Les montants Silver utilisent
un décimal de 18 chiffres, dont deux après la virgule.

```bash
terraform -chdir=infra output -raw glue_job_name
```
