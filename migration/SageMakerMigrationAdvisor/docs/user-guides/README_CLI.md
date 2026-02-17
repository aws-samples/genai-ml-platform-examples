# 🧠 SageMaker Platform Migration Advisor

An agentic AI advisory application that streamlines platform modernization by first interpreting the current-state architecture directly from diagrams or descriptive inputs, proactively asking clarifying questions to resolve ambiguities and ensure accuracy. It then designs a modern, layered target architecture with clear explanations of each component and its role, while delivering a concise comparison of costs and a summary of key technical and operational improvements. The application produces a pragmatic migration roadmap, complemented by a detailed total cost of ownership (TCO) analysis, and provides step-by-step guidance for executing a phased migration to the SageMaker platform—enabling teams to move from assessment to execution with confidence, clarity, and measurable business impact. 

## 🚀 Features
- Understand current state architecture from diagrams or descriptive text input
- Ask clarifying questions for ambiguities to better understand current state architecture
- Generate modernized layered architecture with detailed explanation
- Create cost comparison and key improvements summary
- Produce Migration Roadmap
- Create detailed TCO analysis
- Generate stepwise guidance for phased migration to SageMaker platform 

## 📦 Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_cli.txt
python sagemaker_migration_advisor_cli.py