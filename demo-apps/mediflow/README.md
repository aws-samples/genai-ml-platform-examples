# MediFlow AI

A self-improving AI medical receptionist that learns from its own interactions. Built on [Amazon Bedrock](https://aws.amazon.com/bedrock/) and the [Strands Agents SDK](https://github.com/strands-agents/sdk-python).

## The Concept

Most AI agents are static — they do what they're told, the same way, every time. MediFlow demonstrates a different approach: an agent that **observes its own behavior**, detects patterns, and generates new automation skills without human programming.

```
                    ┌──────────────────────────────────┐
                    │         RECEPTIONIST AGENT        │
                    │  Appointments · Billing · Comms   │
                    └──────────────────┬───────────────┘
                                       │ logs every tool call
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-IMPROVEMENT PIPELINE                     │
│                                                                 │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌────────┐ │
│  │  DETECT   │───▶│  EXTRACT  │───▶│ GENERATE  │───▶│ MEMORY │ │
│  │ Patterns  │    │  Context  │    │  Skills   │    │Patterns│ │
│  └───────────┘    └───────────┘    └───────────┘    └────────┘ │
│   deterministic       LLM              LLM          deterministic│
└──────────────────────────────┬──────────────────────────────────┘
                               │ produces
                               ▼
              ┌─────────────────────────────────┐
              │        GENERATED SKILLS         │
              │  Batch actions the agent can    │
              │  now execute autonomously       │
              └─────────────────────────────────┘
```

**Example:** The agent notices it sends the same SMS reminder 3 days before every appointment. The pipeline detects this pattern, extracts the logic ("3 days before, SMS, include appointment details"), and generates a batch skill that can send all upcoming reminders in one action — with human approval before execution.

## How It Works

### Analysis Pipeline

| Stage | Type | What It Does |
|-------|------|-------------|
| 1. Pattern Detection | Deterministic | Mines tool call logs and UI activity for recurring action sequences |
| 2. Context Extraction | LLM (Bedrock) | Pulls evidence, extracts intent, conditional logic, and scheduling hints |
| 3. Skill Generation | LLM (Bedrock) | Produces executable skill definitions with batch selection logic |
| 4. Memory Detection | Deterministic | Identifies patient behavioral patterns (e.g., "always reschedules Mondays") |

### Architecture

```
┌────────────┐       ┌──────────────┐       ┌─────────────────┐
│   React    │◀─SSE─▶│   FastAPI    │◀─────▶│  Strands Agent  │
│  Frontend  │       │   Server     │       │  (Claude on     │
│            │       │              │       │   Bedrock)      │
└────────────┘       └──────┬───────┘       └────────┬────────┘
                            │                        │
                     ┌──────▼───────┐         ┌──────▼────────┐
                     │   SQLite     │         │  22 Tools     │
                     │  (local DB)  │         │  Calendar     │
                     │              │         │  Billing      │
                     └──────────────┘         │  Comms        │
                                              │  Patient      │
                                              │  Practice     │
                                              │  Workflow     │
                                              └───────────────┘
```

### Skill Execution Flow

Generated skills go through an approval gate before execution:

```
Pipeline produces skill
        │
        ▼
┌───────────────┐     ┌──────────────┐     ┌───────────────┐
│  PENDING      │────▶│   APPROVED   │────▶│   EXECUTING   │
│  (human       │     │  (batch      │     │  (agent runs  │
│   review)     │     │   resolved)  │     │   each item)  │
└───────────────┘     └──────────────┘     └───────┬───────┘
                                                   │
                                            ┌──────▼──────┐
                                            │  COMPLETE   │
                                            │  (results   │
                                            │   logged)   │
                                            └─────────────┘
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend development only)
- AWS account with [Amazon Bedrock](https://aws.amazon.com/bedrock/) access
- Claude Sonnet model enabled in your Bedrock region

## Quick Start

```bash
cd mediflow

# Install dependencies and seed the database
./scripts/setup.sh

# Start the application
uvicorn backend.main:app --reload
```

Open http://localhost:8000

### Running the Analysis Pipeline

The pipeline analyzes the seeded interaction logs and generates skills:

```bash
curl -X POST http://localhost:8000/api/analysis/run
```

Or directly via Python:

```python
from backend.analysis.orchestrator import run_analysis
result = run_analysis()
print(f"Detected {result['patterns_detected']} patterns, generated {result['skills_generated']} skills")
```

### Docker

```bash
docker compose up --build
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_DEFAULT_REGION` | `us-east-1` | Your Bedrock-enabled region |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Inference profile for agent + pipeline |
| `DATABASE_PATH` | `data/receptionist.db` | SQLite database path |
| `PORT` | `8000` | Server port |

> **Inference profiles:** Bedrock requires [cross-region inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) for newer models. Use the prefix matching your region: `us.` (Americas), `eu.` (Europe), `apac.` (Asia-Pacific).

## Cost Estimate

This application calls Amazon Bedrock for LLM inference. All other components run locally at no cost.

| Activity | Estimated Token Usage | Approximate Cost |
|----------|----------------------|-----------------|
| Single chat interaction | ~2K input + ~500 output | ~$0.01 |
| Full pipeline run (analyzes ~50 conversations) | ~150K input + ~30K output | $2–3 |
| Skill execution (per batch item) | ~1K input + ~300 output | ~$0.005 |
| Typical demo session (30 min exploring) | — | $3–5 total |

**Pricing basis:** Claude Sonnet 4 on Bedrock ($3/M input tokens, $15/M output tokens as of May 2025). Actual costs vary by region and model version. See [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) for current rates.

> **Important:** The analysis pipeline is the primary cost driver. Each full run processes all seeded conversations through two LLM stages. The seeded sample data produces ~10–15 skills per run. Repeated pipeline runs during development will accumulate token charges.

## Project Structure

```
mediflow/
├── backend/
│   ├── agent/              # Agent setup, system prompts, skill executor
│   ├── analysis/           # 4-stage self-improvement pipeline
│   ├── api/                # FastAPI route handlers
│   ├── tools/              # 22 tool functions (calendar, patient, billing, comms)
│   ├── services/           # Business logic, database access, pricing
│   ├── seed/               # Sample data fixtures
│   └── main.py             # Application entrypoint
├── frontend/               # React source (Vite + Tailwind), builds to frontend/dist/
├── scripts/
│   ├── setup.sh            # Install dependencies + seed database
│   ├── build-frontend.sh   # Build React app
│   └── reset.sh            # Reset database to clean state
├── tests/                  # Unit tests
├── data/                   # SQLite database (created at runtime)
├── .env.example            # Environment template
├── pyproject.toml          # Python dependencies
├── Dockerfile              # Container build
└── docker-compose.yml      # Docker Compose config
```

## Key Concepts

1. **Tool-call introspection** — The agent logs every tool invocation with full parameters, enabling post-hoc analysis of behavior patterns.

2. **Deterministic + LLM hybrid pipeline** — Pattern detection and memory extraction are deterministic (fast, cheap, reproducible). Context extraction and skill generation use LLMs (flexible, creative).

3. **Batch skill generation** — Skills aren't just "do X once"; they include batch selection hints ("find all appointments in the next 3 days without reminders") so the agent can operate on sets of records.

4. **Human-in-the-loop approval** — Generated skills require explicit approval before execution, maintaining human oversight of autonomous actions.

5. **Patient memory** — The system detects behavioral patterns per patient (scheduling preferences, communication style, payment habits) and stores them as queryable memories the agent uses in future interactions.

## Tools (22 total)

| Module | Tools |
|--------|-------|
| Calendar | check_availability, book_appointment, reschedule_appointment, cancel_appointment, list_upcoming_appointments, get_appointment_details |
| Patient | search_patients, get_patient, get_patient_history, update_patient_notes |
| Billing | get_outstanding_invoices, get_invoice_details, record_payment, send_payment_reminder |
| Comms | send_appointment_reminder, send_message, get_comms_history |
| Practice | get_practice_info, get_doctor_info |
| Workflow | get_pending_workflows, approve_workflow_items, execute_workflow |

## Sample Data

The included seed data represents a fictional medical practice with:
- 15 patients with varied appointment histories
- 5 practitioners across different specialties
- 50+ conversation logs demonstrating receptionist interactions
- Billing records, communications, and scheduling data

All data is synthetic. No real patient information is included.

## Security

- All LLM calls go through Amazon Bedrock (data stays within your AWS account)
- No external API calls beyond Bedrock
- SQLite database is local-only with no network exposure
- Environment variables for all sensitive configuration
- Generated skills require explicit human approval before execution
- No real medical data — all seed data is clearly fictional

## Built With

- [Strands Agents SDK](https://github.com/strands-agents/sdk-python) — Open-source agent framework from AWS
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Foundation model access
- [FastAPI](https://fastapi.tiangolo.com/) — Python web framework
- [React](https://react.dev/) + [Tailwind CSS](https://tailwindcss.com/) — Frontend
- SQLite — Local database

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT-0 License. See [LICENSE](LICENSE).
