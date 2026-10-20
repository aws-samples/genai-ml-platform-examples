# Lab 4 – Model Deploy

**Persona:** ML Engineer

Integrate with CI/CD tools to automate model build and deployment onto **Amazon SageMaker AI (SMAI)** endpoints, then validate the deployed endpoint.

## What you'll do
- Wire up CI/CD (GitHub Actions) to automate the build → register → deploy flow.
- Deploy an approved model from the **SMAI** Model Registry to a real-time endpoint.
- Validate the endpoint with sample payloads.

## Contents
- `lab4x-endpoint-testing.ipynb` – Test a deployed **SMAI** endpoint (in `InService` status) with sample requests.

## Related assets
- `../seed-code/classification/` – MLOps seed repositories for model build and model deploy, including the event-driven automation blueprint. See `../seed-code/classification/model_build/README.md` for full setup.

> **Mono-repo note**: the build and deploy repos are shared across every model
> created from this project template — each one lands in its own
> `models/<model-name>/` folder rather than a fresh pair of repos. See the
> "Mono-repo layout" section in `../seed-code/classification/model_build/README.md`.
