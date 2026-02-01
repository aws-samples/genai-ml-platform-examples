# seed-code zip creation notes

1. Open a terminal and navigate to seed-code/$template_type/model_build_repo where template_type is regression, classification or llm-fine-tuning
2. Execute the following command: zip -r ../model-build-repo.zip ./*
3. Repeat the above steps for model-deploy-repo