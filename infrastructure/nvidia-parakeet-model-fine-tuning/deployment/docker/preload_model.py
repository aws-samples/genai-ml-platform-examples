import nemo.collections.asr as nemo_asr
import os

print("Starting model preloading...")

# NeMo will use the NEMO_CACHE_DIR environment variable if it's set.
# The from_pretrained method will download and cache the model.
try:
    model = nemo_asr.models.EncDecRNNTBPEModel.from_pretrained(model_name="nvidia/parakeet-rnnt-1.1b")
    print("Model 'nvidia/parakeet-rnnt-1.1b' preloaded successfully.")
except Exception as e:
    print(f"An error occurred during model preloading: {e}")
    exit(1)