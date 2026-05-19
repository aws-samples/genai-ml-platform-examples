# PyTorch Computer Vision Custom Image for SageMaker
# Works with: Studio V2 and Unified Studio (JupyterLab & Code Editor)
#
# Single image for all platforms -- entrypoint is configured via AppImageConfig:
#   Studio V2 JupyterLab:       ["jupyter-lab"]
#   Unified Studio JupyterLab:  ["entrypoint-sagemaker-ui-jupyter-server"]
#   Code Editor (both):         ["entrypoint-code-editor"]

FROM public.ecr.aws/sagemaker/sagemaker-distribution:4.0-cpu

ARG NB_USER="sagemaker-user"
ARG NB_UID=1000
ARG NB_GID=100

USER root

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

USER $NB_USER

# Do NOT add ENTRYPOINT -- configured via AppImageConfig at attach time
