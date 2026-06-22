---
name: sagemaker-migration-plan
display_name: SageMaker Migration Plan
description: "Create a comprehensive migration plan for customers moving to AWS SageMaker. Use when someone says 'create migration plan', 'migration planning', 'help migrate to SageMaker', or needs a structured plan for moving from another ML platform (Iguazio, Caspian, Databricks, Kubeflow, etc.) to SageMaker AI or SageMaker Unified Studio."
icon: "🔄"
trigger: create migration plan
inputs:
  - name: customer_name
    description: "Customer or company name (e.g., Seagate, Motive Technologies)"
    type: string
    required: true
  - name: source_platform
    description: "Current ML platform being migrated from (e.g., Iguazio, Caspian, Databricks, Kubeflow, on-prem)"
    type: string
    required: true
  - name: target_services
    description: "Target AWS services (e.g., SageMaker AI, SageMaker Unified Studio, SageMaker Pipelines)"
    type: string
    required: true
  - name: workload_input
    description: "Either a file path to a DOCX/TXT file describing workloads and requirements, OR a free-text description. MINIMUM REQUIRED for financial metrics: (1) Number of models, (2) Data volume per training job (in TB), (3) Retraining frequency (daily/weekly/monthly), (4) Inference pattern (real-time endpoints vs. batch scoring), (5) ML frameworks/model types (e.g., XGBoost, PyTorch, logistic regression). If any of these 5 data points are missing, the skill MUST ask the user before proceeding to the financial metrics step."
    type: string
    required: true
  - name: team_size
    description: "Number of data scientists, ML engineers, or platform users who will be migrated"
    type: string
    required: true
  - name: timeline
    description: "Desired timeline, go-live date, or phase duration constraints"
    type: string
    required: true
  - name: risk_factors
    description: "Known risks or constraints (e.g., regulatory, data residency, downtime windows, compliance)"
    type: string
    default: "None specified"
tools: [web_search, url_fetch, file_read, file_read_docx, file_write, file_edit, run_python, run_javascript, open_in_session_tab, fdfind]
depends-on: [canvas_docx, canvas_pptx]
---

## Overview

This skill creates a structured, research-backed migration plan for customers migrating from an existing ML/AI platform to AWS SageMaker services. It produces three deliverables: a Markdown summary, a detailed Word document (DOCX), and an executive PowerPoint deck (PPTX). The workflow follows the AWS Migration framework (Planning → Preparation → Go-Live → Stabilization) adapted to ML platform migrations.

## Workflow

### Step 1: Parse Workload Input
- **Mode**: `agentic`
- **Tool**: `file_read_docx` or `file_read` (if file path provided)
- **Input**: `{{workload_input}}` — determine if this is a file path or free-text
- **Output**: Structured workload description with use cases, data pipelines, model types, and infrastructure requirements
- **Validate**: ALL 5 minimum financial metrics inputs are present (see checklist below)
- **On failure**: If the file path doesn't exist or is empty, ask the user for a text description. If any of the 5 minimum inputs are missing, ask the user BEFORE proceeding.

Check if `{{workload_input}}` looks like a file path (ends in .docx, .txt, .md, or contains path separators). If yes, read the file. If no, treat it as free-text input. Extract:
- Use cases / ML workloads
- Data pipeline components (feature stores, ETL, data sources)
- Model training patterns (frameworks, scale, frequency)
- Inference patterns (batch vs. real-time, latency requirements, endpoint count)
- Current infrastructure (compute, storage, orchestration)

#### Minimum Required Checklist for Financial Metrics

After parsing, verify that ALL 5 of these data points are known. If any are missing, ask the user before proceeding to Step 2b (Financial Metrics):

| # | Data Point | Why It's Needed | Example Values |
|---|-----------|-----------------|----------------|
| 1 | **Number of models** | Drives total training compute volume | 10, 50, 400 |
| 2 | **Data volume per training job** | Determines instance type + training duration | 100 MB, 1 TB, 10 TB per job |
| 3 | **Retraining frequency** | Multiplier on monthly compute cost | Daily, weekly, monthly, quarterly |
| 4 | **Inference pattern** | Real-time = 24/7 cost; batch = burst cost | Real-time endpoints, batch scoring, both |
| 5 | **ML frameworks / model types** | Maps to CPU vs. GPU instance selection | XGBoost, PyTorch, TensorFlow, logistic regression, neural nets |

**If missing, ask concisely in one message:**
> "To estimate the financial metrics, I need a few more details:
> 1. How many models will be migrated?
> 2. How much data does each model process per training job? (e.g., 500 GB, 10 TB)
> 3. How often are models retrained? (daily/weekly/monthly)
> 4. Is inference real-time or batch scoring?
> 5. What ML frameworks/model types? (e.g., XGBoost, PyTorch, linear regression)"

**Nice-to-have inputs** (improve accuracy but not blocking):
- Current infrastructure details (number of VMs, instance specs)
- Current platform licensing cost (for ROI comparison)
- Training job duration (if known)
- Total unique data storage volume

### Step 2: Research Source-to-Target Service Mapping
- **Mode**: `agentic`
- **Tool**: `web_search`, `url_fetch`
- **Input**: `{{source_platform}}` and `{{target_services}}`
- **Output**: Service mapping table and migration best practices
- **Validate**: At least 3 relevant AWS documentation sources found
- **On failure**: Fall back to general SageMaker migration guidance

Research the specific migration path:
1. Search for AWS documentation on migrating from `{{source_platform}}` to `{{target_services}}`
2. Identify service-by-service mapping (e.g., Iguazio Feature Store → SageMaker Feature Store, MLRun Pipelines → SageMaker Pipelines)
3. Look for migration guides, blog posts, and reference architectures
4. Note any known limitations or gaps in the target platform for this specific migration
5. Check for AWS Migration framework or Professional Services patterns relevant to this migration

### Step 2b: Research Financial Metrics & AWS Pricing
- **Mode**: `agentic`
- **Tool**: `web_search`, `url_fetch`
- **Input**: Workload details from Step 1 (instance types, training frequency, team size, inference patterns) + `{{target_services}}`
- **Output**: Detailed cost breakdown table with monthly and annual estimates using AWS public pricing
- **Validate**: Pricing data sourced from official AWS pricing pages; monthly + annual totals calculated
- **On failure**: Use general SageMaker pricing estimates with clear "estimate" disclaimers

Research AWS public pricing to build a financial model for the migration:

1. **Search AWS pricing pages** for each target service:
   - SageMaker Training: https://aws.amazon.com/sagemaker/pricing/ (training job instance pricing, Managed Spot discount ~60-90%)
   - SageMaker Studio: notebook instance pricing (per-user costs)
   - SageMaker Endpoints: real-time inference instance pricing (if applicable)
   - S3 Storage: https://aws.amazon.com/s3/pricing/ (storage + requests)
   - AWS Glue: https://aws.amazon.com/glue/pricing/ (if ETL needed)
   - Data Transfer: cross-AZ and internet egress costs

2. **Build a cost model** based on workload details:
   - **Training costs**: Map instance types to workload requirements (CPU for XGBoost → ml.m5.xlarge–4xlarge; GPU for PyTorch/deep learning → ml.p3.2xlarge or ml.g5.xlarge). Calculate: (instance $/hr) × (training hours/month) × (Spot discount factor, typically 0.3 for 70% savings).
   - **Notebook/IDE costs**: SageMaker Studio per-user notebook instances × team_size × hours/day × working days/month
   - **Inference costs** (if applicable): Endpoint instance pricing × hours/month (or Serverless Inference pricing if intermittent)
   - **Storage costs**: Training data volume × S3 Standard $/GB/month + model artifacts
   - **Supporting services**: KMS, CloudWatch, CloudTrail, VPC endpoints

3. **Calculate monthly and annual totals**:
   - Itemized monthly cost per service
   - Annual cost (monthly × 12)
   - Comparison vs. current platform costs (if available from workload input)
   - Potential Savings Plans or Reserved Instance discounts for sustained usage

4. **Format as a Financial Metrics section** with:
   - Cost breakdown table (Service | Instance Type | Usage Pattern | Monthly Cost | Annual Cost)
   - Total monthly and annual running costs
   - Cost optimization recommendations (Managed Spot, auto-scaling, Savings Plans)
   - ROI summary: current spend vs. projected SageMaker spend

**Pricing sources** (always cite):
- https://aws.amazon.com/sagemaker/pricing/
- https://aws.amazon.com/s3/pricing/
- https://aws.amazon.com/glue/pricing/
- https://aws.amazon.com/kms/pricing/
- https://aws.amazon.com/cloudwatch/pricing/

Note: Prices vary by region. Default to us-east-1 unless data residency requires a specific region (e.g., eu-west-1 for EMEA customers). Always note "pricing as of [date], subject to change" in the output.

### Step 3: Generate Markdown Migration Plan
- **Mode**: `agentic`
- **Tool**: `file_write`
- **Input**: All gathered context from Steps 1-2, plus `{{customer_name}}`, `{{team_size}}`, `{{timeline}}`, `{{risk_factors}}`
- **Output**: `artifacts/{{customer_name}}_migration_plan.md`
- **Validate**: Document contains all required sections
- **On failure**: Regenerate missing sections

Write a comprehensive Markdown migration plan with these sections:

```
# Migration Plan: {{customer_name}}
## Source: {{source_platform}} → Target: {{target_services}}

### Executive Summary
- One-paragraph overview of the migration scope, timeline, and expected outcomes

### Current State Assessment
- Source platform architecture
- Workload inventory (from Step 1)
- Team structure and skill gaps
- Dependencies and integrations

### Target Architecture
- AWS service mapping table (source component → AWS equivalent)
- Architecture diagram description (components and data flow)
- Security and networking considerations
- IAM and access patterns

### Migration Phases
#### Phase 1: Planning (Weeks 1-2)
- Discovery workshops, architecture validation, POC scope

#### Phase 2: Preparation (Weeks 3-6)
- Environment setup, IaC templates, pilot migration of 1-2 workloads
- Team training and enablement

#### Phase 3: Go-Live (Weeks 7-10)
- Batch migration of remaining workloads
- Parallel run period with validation
- Cutover criteria and rollback plan

#### Phase 4: Stabilization (Weeks 11-12)
- Monitoring, optimization, decommission source platform
- Knowledge transfer and documentation

### Risk Assessment
- Risk matrix with likelihood, impact, and mitigation
- Include {{risk_factors}} as identified risks

### Financial Metrics
- Detailed cost breakdown using AWS public pricing
- Monthly and annual running cost estimates
- Service-by-service itemization with instance types and usage patterns
- Cost optimization opportunities (Managed Spot, Savings Plans, auto-scaling)
- ROI comparison: current platform cost vs. projected SageMaker cost

#### Cost Breakdown Table
| Service | Instance/SKU | Usage Pattern | Monthly Cost | Annual Cost |
|---------|-------------|---------------|-------------|-------------|
| SageMaker Training | ml.m5.4xlarge (Spot) | X hrs/month | $X | $X |
| SageMaker Training | ml.p3.2xlarge (Spot) | X hrs/month | $X | $X |
| SageMaker Studio | ml.t3.medium | X users × Y hrs/day | $X | $X |
| SageMaker Endpoints | (if applicable) | X endpoints × Y hrs | $X | $X |
| S3 Storage | Standard | X TB | $X | $X |
| AWS KMS | CMK + requests | Flat | $X | $X |
| CloudWatch | Metrics + Logs | Usage-based | $X | $X |
| **Total** | | | **$X** | **$X** |

*Source: AWS Public Pricing (region), as of [date]*

### Success Criteria
- Measurable outcomes (latency, cost, availability, team adoption)

### Resource Requirements
- AWS services and estimated costs (see Financial Metrics above for detailed breakdown)
- Team allocation ({{team_size}} users)
- Training needs

### Next Steps & Action Items
- Immediate actions with owners and dates
```

Adjust phase durations based on `{{timeline}}`. For larger teams (>20 users), extend Preparation and Go-Live phases. For platform shutdowns (like Caspian), compress Planning and emphasize parallel-run periods.

### Step 4: Create DOCX Migration Plan
- **Mode**: `deterministic`
- **Tool**: `use_skill("canvas_docx")`, `run_python`
- **Input**: Markdown content from Step 3
- **Output**: `artifacts/{{customer_name}}_migration_plan.docx`
- **Validate**: DOCX file exists and opens correctly
- **On failure**: Retry document generation; if persistent, deliver Markdown only

Convert the Markdown plan into a professionally formatted Word document:
- Use AWS branding (Navy #232F3E headings)
- Include a title page with customer name, date, and "AWS Confidential"
- Add table of contents
- Format the service mapping as a proper table
- Apply consistent heading styles (Heading 1, 2, 3)
- Add header/footer using `add_header_footer_to_docx()` with customer name and "AWS Confidential"

### Step 5: Create PPTX Executive Summary Deck
- **Mode**: `deterministic`
- **Tool**: `use_skill("canvas_pptx")`, `run_javascript`
- **Input**: Key content from the migration plan
- **Output**: `artifacts/{{customer_name}}_migration_deck.pptx`
- **Validate**: PPTX file exists with 6-10 slides
- **On failure**: Retry; fall back to pptxgenjs with AWS colors

Create a concise executive deck (6-10 slides) summarizing the migration:
1. Title slide: "Migration Plan: {{customer_name}} — {{source_platform}} → {{target_services}}"
2. Current State & Challenges
3. Target Architecture (service mapping highlights)
4. Migration Approach (4-phase overview)
5. Timeline & Milestones
6. Risk Summary & Mitigations
7. Resource Requirements & Cost Estimate
8. Success Criteria
9. Financial Metrics (monthly & annual cost breakdown table, ROI comparison)
10. Next Steps & Action Items

Use AWS light brand colors: Navy #232F3E, Orange #FF9900, Light Gray #F2F3F3. Use Amazon Ember font. If the 2026 AWS brand template is available in attached_files, use it; otherwise use pptxgenjs with these brand colors.

### Step 6: Present Deliverables
- **Mode**: `deterministic`
- **Tool**: `open_in_session_tab`
- **Input**: All three output files
- **Output**: Files opened for user review
- **Validate**: User can see the outputs
- **On failure**: Provide download links

Open the Markdown summary in a session tab and provide links to all three deliverables:
- `artifacts/{{customer_name}}_migration_plan.md` (quick reference)
- `artifacts/{{customer_name}}_migration_plan.docx` (detailed plan)
- `artifacts/{{customer_name}}_migration_deck.pptx` (executive presentation)

## Output

Three migration plan deliverables:
1. **Markdown Summary** — Quick-reference plan viewable in the session tab
2. **Word Document (DOCX)** — Detailed, formatted migration plan with AWS branding suitable for customer delivery
3. **PowerPoint Deck (PPTX)** — Executive summary presentation for leadership reviews and kickoff meetings

## Lessons Learned

### Do
- Always map source platform services 1:1 to AWS equivalents before writing the plan — this grounds the architecture section in reality
- Adjust phase durations based on team size and urgency (platform shutdowns need compressed timelines)
- Include a parallel-run period in Go-Live phase — customers need confidence before full cutover
- Always research current AWS public pricing for the financial metrics section — do not rely on memorized prices as they change frequently
- Include both monthly and annual costs to help customers compare against their current annual platform licensing/infrastructure spend
- Research the specific source platform's architecture first; generic migration plans lack credibility
- Use the AWS Migration framework (Planning → Preparation → Go-Live → Stabilization) as the standard phasing model

### Don't
- Don't assume all workloads migrate the same way — inference pipelines are typically harder than training
- Don't skip the risk assessment even for "simple" migrations — data residency and compliance issues often surface late
- Don't propose unrealistic timelines — a meaningful ML platform migration takes 8-12 weeks minimum for teams >10 people
- Don't forget team enablement — training is often the bottleneck, not infrastructure
- Don't use stale pricing — always fetch current prices from AWS public pricing pages during execution

### Common Failures
- **File path not found**: User provides a workload description file that doesn't exist → prompt for text input instead
- **No migration docs found**: Some source platforms are niche with no AWS migration guide → build the mapping manually from platform docs
- **Template not available**: AWS brand PPTX template may not be in the session → fall back to pptxgenjs with brand colors
- **Overly long plans**: If workload input is very detailed, the plan can exceed useful length → keep DOCX under 15 pages, focus on actionable items
- **Pricing page unavailable or changed**: AWS pricing pages occasionally restructure → fall back to the SageMaker pricing calculator or note "pricing TBD — verify at aws.amazon.com/sagemaker/pricing/"

### When to Ask the User
- When the workload input is ambiguous and you can't determine key architecture patterns
- When the timeline seems unrealistic given the migration scope — flag this and suggest alternatives
- When there are multiple valid target architectures (e.g., SageMaker AI vs. Unified Studio) and the choice depends on org preferences
- When risk factors suggest compliance/legal review is needed before proceeding
