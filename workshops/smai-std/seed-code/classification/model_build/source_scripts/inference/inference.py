# =============================================================================
# SageMaker script-mode inference handler — bank-marketing XGBoost
# =============================================================================
# VERBATIM COPY of the handler Lab 3A writes inline
# (lab3-model-build/lab-3a_traditional_ml_experimenation.ipynb, the cell that
# assigns `inference_script`). Extracted to a real file here because this
# pipeline bakes it into the model tarball at code/inference.py from a
# ProcessingStep, and a pipeline step cannot read a notebook.
#
# SYNC RULE: Lab 3A's notebook is the canonical source. If you change the
# handler there, re-extract it here in the same commit. The two MUST stay
# identical: Lab 3A's endpoint and this pipeline's endpoint are meant to be the
# same serving contract, and Lab 5 compares captured predictions across both.
#
# The container runs this via SAGEMAKER_PROGRAM=inference.py +
# SAGEMAKER_SUBMIT_DIRECTORY=/opt/ml/model/code. Without those two env vars the
# stock XGBoost container ignores this file and serves bare probabilities.
#
# Deliberately avoids type hints and modern syntax: the XGBoost 1.7-1 container
# ships Python 3.9.
# =============================================================================
import json
import os
import time
import uuid
import logging
from datetime import datetime

import pandas as pd
import numpy as np
import xgboost as xgb
import boto3

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration from container environment ---
# INTERIM: the Lab 3A deploy cell injects these as container env vars. The
# planned end-state is to manage them centrally as environment variables;
# for now the notebook resolves and passes them at deploy time.
ENABLE_INFERENCE_CAPTURE = os.getenv('ENABLE_INFERENCE_CAPTURE', 'true').lower() == 'true'
ENDPOINT_NAME = os.getenv('ENDPOINT_NAME', 'unknown')
MODEL_VERSION = os.getenv('MODEL_VERSION', 'unknown')
MLFLOW_RUN_ID = os.getenv('MLFLOW_RUN_ID', 'unknown')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', '')
HIGH_CONFIDENCE_THRESHOLD = float(os.getenv('HIGH_CONFIDENCE_THRESHOLD', '0.9'))
LOW_CONFIDENCE_LOWER = float(os.getenv('LOW_CONFIDENCE_LOWER', '0.4'))
LOW_CONFIDENCE_UPPER = float(os.getenv('LOW_CONFIDENCE_UPPER', '0.6'))

sqs_client = None


def _region_from_queue_url(url):
    # URL shape: https://sqs.<region>.amazonaws.com/<account>/<queue>
    # Untyped on purpose: the XGBoost container ships Python 3.9.
    try:
        host = url.split('//', 1)[1].split('/', 1)[0]
        parts = host.split('.')
        if len(parts) >= 3 and parts[0] == 'sqs':
            return parts[1]
    except Exception:
        pass
    return None


def get_sqs_client():
    global sqs_client
    if sqs_client is None:
        region = (_region_from_queue_url(SQS_QUEUE_URL)
                  or os.getenv('SAGEMAKER_REGION')
                  or os.getenv('AWS_REGION'))
        if not region:
            raise RuntimeError('Cannot determine AWS region for SQS client.')
        sqs_client = boto3.client('sqs', region_name=region)
    return sqs_client


def get_prediction_bucket(p):
    if p < 0.2:
        return 'very_low'
    if p < 0.4:
        return 'low'
    if p < 0.6:
        return 'medium'
    if p < 0.8:
        return 'high'
    return 'very_high'


def model_fn(model_dir):
    # model_dir is /opt/ml/model, into which the S3Prefix ModelDataSource
    # downloaded the WHOLE MLflow logged-model directory: the booster written by
    # mlflow.xgboost.log_model(model_format='json') plus MLmodel, conda.yaml and
    # the code/ directory this file came from.
    #
    # The booster is loaded with plain xgboost rather than
    # mlflow.xgboost.load_model(): mlflow is not installed in the stock XGBoost
    # serving container, and installing it would add a pip step to every cold
    # start. Booster.load_model() sniffs the format, so json / ubj / legacy
    # binary all work. Several names are tried so an artifact produced by an
    # older notebook run (or a repacked tarball) still loads.
    start = time.time()
    model_path = None
    for fn in ['model.json', 'model.ubj', 'model.xgb', 'model.pkl',
               'xgboost-model.json', 'xgboost-model',
               os.path.join('data', 'model.json'),
               os.path.join('data', 'model.xgb')]:
        p = os.path.join(model_dir, fn)
        if os.path.exists(p):
            model_path = p
            break
    if model_path is None:
        raise FileNotFoundError(
            'No model file found in ' + model_dir + ' (contents: '
            + str(sorted(os.listdir(model_dir))) + ')')
    if model_path.endswith('.pkl'):
        import pickle
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
    else:
        model = xgb.Booster()
        model.load_model(model_path)
    # feature_names.json is logged at the artifact root (Step 5.4), so it lands
    # next to the model; code/ is checked too for older layouts.
    feature_names = None
    for meta in [os.path.join(model_dir, 'feature_names.json'),
                 os.path.join(model_dir, 'code', 'feature_names.json')]:
        if os.path.exists(meta):
            with open(meta) as f:
                feature_names = json.load(f)['feature_names']
            break
    load_ms = (time.time() - start) * 1000
    logger.info('Model loaded in %.1fms; %d features', load_ms, len(feature_names or []))
    return {'model': model, 'feature_names': feature_names, 'model_load_time_ms': load_ms}


def input_fn(request_body, content_type='application/json'):
    if isinstance(request_body, (bytes, bytearray)):
        request_body = request_body.decode('utf-8')
    if content_type == 'application/json':
        data = json.loads(request_body)
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            raise ValueError('Unsupported JSON payload: ' + str(type(data)))
    elif content_type == 'text/csv':
        from io import StringIO
        df = pd.read_csv(StringIO(request_body), header=None)
        # Positional CSV -> name columns from FEATURE_NAMES so capture records
        # carry named features (matching the training_data baseline).
        names = os.getenv('FEATURE_NAMES')
        if names:
            cols = [c.strip() for c in names.split(',')]
            if len(cols) == df.shape[1]:
                df.columns = cols
    else:
        raise ValueError('Unsupported content type: ' + str(content_type))
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def predict_fn(input_data, model_dict):
    start = time.time()
    model = model_dict['model']
    feature_names = model_dict['feature_names']
    # Fall back to incoming column order if the artifact had no feature_names.
    if not feature_names:
        feature_names = list(input_data.columns)
    for f in feature_names:
        if f not in input_data.columns:
            input_data[f] = 0.0
    ordered = input_data[feature_names]
    preprocessing_ms = (time.time() - start) * 1000

    # DMatrix from a numpy array: the booster is trained on a header-less
    # positional CSV, so it carries no feature names and name-based validation
    # would mismatch. A booster that DOES carry names (trained from a DataFrame,
    # e.g. by an older version of train.py) is fed the same positional values
    # under its own names, which keeps this handler working either way.
    _booster_features = getattr(model, 'feature_names', None)
    if _booster_features and len(_booster_features) == ordered.shape[1]:
        dmatrix = xgb.DMatrix(ordered.values, feature_names=list(_booster_features))
    else:
        dmatrix = xgb.DMatrix(ordered.values)
    probabilities = model.predict(dmatrix)
    predictions = (probabilities > 0.5).astype(int)

    results = {
        'predictions': predictions.tolist(),
        'probabilities': {
            'yes': probabilities.tolist(),
            'no': (1 - probabilities).tolist(),
        },
    }
    latency_ms = (time.time() - start) * 1000

    # Fire-and-forget capture: a send failure must never fail the prediction.
    if ENABLE_INFERENCE_CAPTURE and SQS_QUEUE_URL:
        try:
            sqs = get_sqs_client()
            for i in range(len(predictions)):
                p_yes = float(probabilities[i])
                conf = max(p_yes, 1 - p_yes)
                msg = {
                    'inference_id': str(uuid.uuid4()),
                    'request_timestamp': datetime.utcnow().isoformat(),
                    'endpoint_name': ENDPOINT_NAME,
                    'model_version': MODEL_VERSION,
                    'mlflow_run_id': MLFLOW_RUN_ID,
                    'input_features': json.dumps(ordered.iloc[i].to_dict()),
                    'prediction': int(predictions[i]),
                    'probability_positive': p_yes,
                    'probability_negative': float(1 - p_yes),
                    'confidence_score': conf,
                    'ground_truth': None,
                    'ground_truth_timestamp': None,
                    'ground_truth_source': None,
                    'days_to_ground_truth': None,
                    'inference_latency_ms': latency_ms,
                    'model_load_time_ms': model_dict.get('model_load_time_ms', 0),
                    'preprocessing_time_ms': preprocessing_ms,
                    'client_id': (str(input_data.iloc[i].get('client_id', '')) or None),
                    'is_high_confidence': bool(conf > HIGH_CONFIDENCE_THRESHOLD),
                    'is_low_confidence': bool(LOW_CONFIDENCE_LOWER <= conf <= LOW_CONFIDENCE_UPPER),
                    'prediction_bucket': get_prediction_bucket(p_yes),
                    'request_id': str(uuid.uuid4()),
                    'response_time': datetime.utcnow().isoformat(),
                    'error_message': None,
                    'inference_mode': 'realtime',
                    'monitoring_run_id': None,
                }
                sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(msg))
        except Exception as e:
            print('SQS send failed: ' + str(e))

    return results


def output_fn(prediction, accept='application/json'):
    if accept in ('application/json', '*/*', None, ''):
        return json.dumps(prediction)
    raise ValueError('Unsupported accept type: ' + str(accept))
