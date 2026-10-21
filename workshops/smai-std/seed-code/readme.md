# seed-code zip creation notes

Run `./create_zips.sh` from this folder. It packages `classification/model_build`
and `classification/model_deploy` into `model-build-repo.zip` and
`model-deploy-repo.zip`, and verifies the result — do not hand-build the zips
with a plain `zip -r`; that has drifted from the tracked source before.

These are the seed-code zips a SageMaker Project copies into one `models/<model-name>/`
folder of the shared model-build and model-deploy repositories (see
`classification/model_build/README.md` for the mono-repo layout).
