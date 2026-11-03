# Lab 3 – Model Build

**Persona:** Data Scientist

Use the **Amazon SageMaker AI (SMAI)** platform tools — training, JumpStart, and the Model Registry — to experiment with and build both traditional ML and LLM models, with governance (experiment tracking, lineage, and model registry) built in.

## Contents
- `lab3a_traditional_ml_experimenation.ipynb` – Traditional ML with **SMAI**. Trains a binary classifier on the UCI Bank Marketing dataset to predict term-deposit subscriptions using managed SMAI training.
- `lab-3b-fine-tuning.ipynb` – Fine-tune **Llama 3.2 3B** for text summarization with **SMAI** JumpStart, tracking parameters, metrics, and base-to-fine-tuned lineage for auditability and reproducibility.
- `lab-3c-model-evaluation-registration.ipynb` – Evaluate the fine-tuned model against the base model, create model cards with governance metadata, and register versions in the **SageMaker Model Registry** with approval workflows.
- `lab-3d-serverless-fine-tuning.ipynb` – **Optional, run after 3C.** The same summarization fine-tune using **serverless model customization**: no instance type, no GPU capacity handling, and training, registration, and MLflow tracking in one call. Depends only on Lab 2A, writes to its own model package group, and creates no endpoint — so running or skipping it leaves Labs 4 and 5 unchanged.
- `metrics.py` – Shared evaluation metric helpers.

## Outcome
Trained and evaluated models registered in the Model Registry, ready for automated deployment in Lab 4.
