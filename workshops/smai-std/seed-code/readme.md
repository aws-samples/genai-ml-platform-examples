# seed-code zip creation notes
Do not hand-build the zips with a plain `zip -r`; that has drifted from the
tracked source before. Use `create_zips.sh` from this folder instead.

1. Classification: run `./create_zips.sh`. It packages `classification/model_build`
   and `classification/model_deploy` into `model-build-repo.zip` and
   `model-deploy-repo.zip`, and verifies the result. These are the seed-code zips
   a SageMaker Project copies into one `models/<model-name>/` folder of the shared
   model-build and model-deploy repositories (see
   `classification/model_build/README.md` for the mono-repo layout).
2. LLM fine-tuning: run `./create_zips.sh llm`. It rebuilds
   `llm-fine-tuning/model-build-repo.zip` and `llm-fine-tuning/model-deploy-repo.zip`
   as flat zips (files at the zip root), removing the old zips first and leaving out
   `__pycache__`, `.DS_Store` and `.ipynb_checkpoints`.
