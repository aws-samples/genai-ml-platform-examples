# Lab 2 – Data Prep

**Persona:** Data Engineer

Prepare data for downstream model building using several approaches so you can pick the right tool for the workload. This lab covers two datasets:

- **Bank Marketing dataset** (UCI) — tabular dataset (~41K records, 20 features), used by Lab 3A (traditional ML with XGBoost)
- **Databricks Dolly 15K** — instruction-following dataset filtered for summarization, used by Lab 3B (LLM fine-tuning)

All options produce outputs in **Amazon S3**. For the Bank Marketing dataset, a shared Iceberg registration step persists the data into **S3 Table Buckets** and **Athena Iceberg tables** for downstream analytics, drift monitoring (Lab 5), and QuickSight dashboards.

## Data preparation options

| Lab | Dataset | Option | Best For |
|-----|---------|--------|----------|
| **2A** | Dolly 15K (Summarization) | In-line processing | Quick text dataset prep — filter, validate, split, and upload directly from notebook |
| **2B** | Bank Marketing | SageMaker Processing Job (scikit-learn) | Fully managed container — no cluster admin |
| **2C** | Bank Marketing | EMR Serverless | Serverless Spark — auto-scales, no capacity planning |
| **2D** | Bank Marketing | EMR on EC2 | Managed clusters — large/long-running jobs |
| **2E** | Bank Marketing | Canvas (Low-code/No-code) | Visual prep — GUI-based, no coding required |
| **2F** | Bank Marketing | Iceberg registration (shared step) | Required final step — runs after **any** of 2B–2E to land the data in Iceberg |

> **2B–2E are alternatives** (pick one approach to produce the Bank Marketing CSVs). **2F is not an alternative** — it is the common follow-on step for Bank Marketing dataset that every path runs to register those CSVs into Iceberg.

## Workflow

### Lab 2A — Dolly dataset (LLM fine-tuning prep)

1. **Load** the Databricks Dolly 15K dataset
2. **Filter** for the summarization category
3. **Validate** — remove empty or too-short records
4. **Split** into training (70%) and evaluation (30%) sets
5. **Create prompt template** (`template.json`) for instruction tuning
6. **Upload to S3** — `train.jsonl`, `test.jsonl`, and `template.json`

### Lab 2B–2E — Bank Marketing dataset (traditional ML prep)

1. **Run one of Lab 2B–2E** — produces `train.csv` and `test.csv` in S3
2. **Run the Iceberg registration notebook** — registers the CSVs into:
   - S3 Table Bucket (managed Iceberg, auto-compaction)
   - Default Glue Catalog Iceberg tables (Athena, QuickSight, Lab 5)
3. **Capture snapshot IDs** — used by Lab 3 and Lab 5 for baseline pinning

```
Lab 2B/2C/2D/2E  →  train.csv + test.csv in S3
        ↓
lab-2f-iceberg-registration.ipynb
        ↓
S3 Table Bucket + Athena Iceberg tables (with snapshot IDs)
        ↓
Lab 3 (model build) / Lab 5 (drift monitoring) / QuickSight
```

### Lab 2F — Iceberg registration (shared step)

Lab 2F (`lab-2f-iceberg-registration.ipynb`) is the **single shared step that every Bank Marketing path (2B–2E) finishes with**. Whichever tool you used to produce `train.csv` / `test.csv`, you then run 2F exactly once to publish that data into the Iceberg layer the rest of the workshop consumes. It does **not** prepare data itself — it reads the CSVs and writes them into pre-provisioned tables.

What it does:

1. **Reads** the processed `train.csv` / `test.csv` from the shared S3 paths produced by 2B–2E
2. **Writes** them into the Iceberg tables (`training_data`, `evaluation_data`) in both the S3 Table Bucket and the default Glue catalog — these tables are pre-provisioned by the `5-data-prep.yaml` CloudFormation stack, so 2F only writes data
3. **Captures snapshot IDs** that Lab 3 and Lab 5 pin as frozen baselines (`FOR VERSION AS OF`)

Run order: **one of 2B–2E → then 2F**. Lab 3 and Lab 5 read the Athena/Iceberg tables that 2F populates, so 2F is required regardless of which prep option you chose.

> **Coming from Lab 2E (Canvas)?** Canvas exports a header-included CSV, so 2F includes an optional, clearly-labeled normalization cell near the top that reshapes the Canvas export into the headerless, target-first layout the rest of the notebook expects. Participants arriving from 2B/2C/2D skip that cell.

## Outputs

### Lab 2A outputs (consumed by Lab 3B — LLM fine-tuning)

- `s3://<DataBucketName>/<ProfileName>/dolly_dataset/train.jsonl` — Training examples
- `s3://<DataBucketName>/<ProfileName>/dolly_dataset/test.jsonl` — Evaluation examples
- `s3://<DataBucketName>/<ProfileName>/dolly_dataset/template.json` — Prompt template for instruction tuning

### Lab 2B–2E outputs (consumed by Lab 3A — traditional ML)

**CSV (regular S3):**
- `s3://<default-bucket>/bank-marketing-lab/data/train/train.csv` — Training data (CSV, no header, target-first)
- `s3://<default-bucket>/bank-marketing-lab/data/test/test.csv` — Test data (CSV, no header, target-first)

**S3 Table Bucket (managed Iceberg):**
- Bucket: `bank-marketing-monitoring-<account-id>`
- Namespace: `bank_marketing`
- Tables: `training_data`, `evaluation_data`

**Default Catalog Iceberg (Athena / QuickSight / Lab 5):**
- Database: `bank_marketing`
- Tables: `training_data`, `evaluation_data`
- Queryable via: `SELECT * FROM bank_marketing.training_data LIMIT 10;`
- Supports time travel: `FOR VERSION AS OF <snapshot_id>`

## Notebooks

| File | Description |
|------|-------------|
| `lab-2a-fine-tuning-data-prep-processing-job.ipynb` | Dolly summarization dataset preparation |
| `lab-2b-traditional-ml-data-prep-processing-job.ipynb` | Bank Marketing dataset preparation (SageMaker Processing Job) |
| `lab-2c-emr-serverless-data-prep.ipynb` | Bank Marketing dataset preparation (EMR Serverless Spark) |
| `lab-2d-emr-on-ec2-data-prep.ipynb` | Bank Marketing dataset preparation (EMR on EC2 Spark) |
| Lab 2E (Canvas) | Visual, no-code prep in SageMaker Canvas — see the Lab 2E workshop instructions (console-based, no notebook) |
| `lab-2f-iceberg-registration.ipynb` | **Shared final step**: register the processed CSVs from any of 2B–2E into the S3 Table Bucket + Athena Iceberg tables (run once, after your chosen prep option) |

## Prerequisites

- Completed Lab 1 (environment setup)
- Access to the workshop S3 bucket (DataBucketName from CloudFormation outputs)
- SageMaker Studio JupyterLab space running

### Lab 2F prerequisites

- Completed one of Lab 2B–2E (produces `train.csv` and `test.csv` in S3)
- Iceberg infrastructure pre-provisioned (Glue database, Iceberg tables, S3 Table Bucket, IAM permissions, Lake Formation grants, S3 Tables → Glue Data Catalog integration)