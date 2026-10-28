# seed-code zip creation notes
1. Classification: run `./create_zips.sh` from this folder.
2. LLM fine-tuning: run `./create_zips.sh llm` from this folder. It rebuilds
   `llm-fine-tuning/model-build-repo.zip` and `llm-fine-tuning/model-deploy-repo.zip`
   as flat zips (files at the zip root), removing the old zips first and leaving out
   `__pycache__`, `.DS_Store` and `.ipynb_checkpoints`.
