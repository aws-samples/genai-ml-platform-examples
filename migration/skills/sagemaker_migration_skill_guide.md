# 🔄 SageMaker Migration Plan — Skill User Guide

> **Trigger phrase:** `create migration plan`
> **Installed at:** `~/.quickwork/profiles/<profile>/skills/sagemaker-migration-plan/SKILL.md`

---

## What It Does

Generates a **comprehensive, research-backed migration plan** for customers moving from any ML platform to Amazon SageMaker AI. Produces **three deliverables** in one run:

| Output | Format | Purpose |
|--------|--------|---------|
| Quick Reference | Markdown (.md) | Fast review, internal sharing |
| Detailed Plan | Word (.docx) | Customer-ready, AWS branded |
| Executive Deck | PowerPoint (.pptx) | Leadership presentations |

---

## Inputs

### Required Fields

| Input | What to Provide | Example |
|-------|----------------|---------|
| **Customer Name** | Company name | "SWIFT", "Seagate" |
| **Source Platform** | Current ML platform | "SAS VDMML", "Iguazio", "Databricks", "C3 AI" |
| **Target Services** | AWS target | "SageMaker AI", "SageMaker Unified Studio" |
| **Workload Input** | Description OR path to a .docx/.txt file | See minimum requirements below |
| **Team Size** | Number of users to migrate | "200 data scientists + 2 ML engineers" |
| **Timeline** | Target duration or go-live date | "12 weeks", "Q3 2026 go-live" |

### Optional

| Input | Default |
|-------|---------|
| **Risk Factors** | "None specified" |

---

## ⚠️ Minimum Required for Financial Metrics

The skill will **ask you** if any of these 5 data points are missing from the workload input:

| # | Data Point | Why It's Needed | Example |
|---|-----------|-----------------|---------|
| 1 | **Number of models** | Drives compute volume | 50, 400 |
| 2 | **Data volume per training job** | Determines instance size + duration | 500 GB, 10 TB |
| 3 | **Retraining frequency** | Monthly vs. weekly = cost multiplier | Monthly, weekly |
| 4 | **Inference pattern** | Real-time (24/7) vs. batch (burst) | Batch scoring daily |
| 5 | **ML frameworks / model types** | CPU vs. GPU instance selection | XGBoost, PyTorch |

### Nice-to-Have (Improves Accuracy)

- Current infrastructure (number of VMs, specs)
- Current platform licensing cost
- Known training job duration
- Total unique data storage volume

---

## How to Use

### Option 1: Quick Text Input

```
Create migration plan

Customer: Acme Corp
Source: Databricks on-prem
Target: SageMaker AI
Workloads: 50 models (XGBoost + PyTorch), 1 TB per job, 
           retrained weekly, real-time inference
Team: 30 data scientists, 5 ML engineers
Timeline: 10 weeks
Risks: HIPAA compliance, data residency (US only)
```

### Option 2: Document Input

```
Create migration plan

Customer: Acme Corp
Source: SAS VDMML
Target: SageMaker AI
Workloads: /Users/me/Documents/acme_requirements.docx
Team: 200
Timeline: 16 weeks
Risks: Financial regulatory compliance (SEC, SOX)
```

---

## What the Skill Does (Workflow)

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  1. Parse   │───▶│  2. Research │───▶│ 2b. Pricing   │
│  Workload   │    │  AWS Docs    │    │  Research     │
└─────────────┘    └──────────────┘    └───────┬───────┘
                                               │
       ┌───────────────────────────────────────┘
       ▼
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ 3. Generate │───▶│  4. Create   │───▶│  5. Create    │
│  Markdown   │    │    DOCX      │    │    PPTX       │
└─────────────┘    └──────────────┘    └───────────────┘
```

1. **Parse** — Reads workload input, validates 5 minimum data points
2. **Research** — Searches AWS docs for source→target migration path
3. **Pricing** — Fetches AWS public pricing, builds cost model
4. **Generate** — Writes Markdown plan with all sections
5. **DOCX** — Converts to branded Word document
6. **PPTX** — Creates 10-slide executive deck

---

## Plan Sections

Every migration plan includes:

- ✅ Executive Summary
- ✅ Current State Assessment (workload inventory, team, pain points)
- ✅ Target Architecture (service mapping table, security)
- ✅ Migration Phases (4-phase: Planning → Preparation → Go-Live → Stabilization)
- ✅ Risk Assessment (risk matrix with mitigations)
- ✅ **Financial Metrics** (monthly + annual costs, ROI comparison)
- ✅ Success Criteria (measurable outcomes)
- ✅ Next Steps & Action Items

---

## Installation

Copy the `SKILL.md` file to your Amazon Quick skills folder:

```bash
mkdir -p ~/.quickwork/profiles/<profile>/skills/sagemaker-migration-plan/
cp sagemaker-migration-plan_SKILL.md \
   ~/.quickwork/profiles/<profile>/skills/sagemaker-migration-plan/SKILL.md
```

Restart Amazon Quick — the skill auto-loads.

---

## SharePoint Location

The latest version is available at:
**[SageMaker AI Platform > Shared Documents > GTM](https://amazon.sharepoint.com/sites/SageMakerAIPlatform/Shared%20Documents/GTM/sagemaker-migration-plan_SKILL.md)**

---

*Last updated: June 22, 2026*
