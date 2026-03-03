import argparse
import os
import logging
import sys
import pickle
import xgboost as xgb
import pandas as pd
import mlflow
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max_depth', type=int, default=5)
    parser.add_argument('--eta', type=float, default=0.2)
    parser.add_argument('--gamma', type=int, default=4)
    parser.add_argument('--min_child_weight', type=int, default=6)
    parser.add_argument('--subsample', type=float, default=0.8)
    parser.add_argument('--num_round', type=int, default=100)
    parser.add_argument('--objective', type=str, default='binary:logistic')
    return parser.parse_known_args()


if __name__ == '__main__':
    args, _ = parse_args()

    # Load data
    train_data = pd.read_csv('/opt/ml/input/data/train/train.csv', header=None)
    validation_data = pd.read_csv('/opt/ml/input/data/validation/validation.csv', header=None)

    X_train, y_train = train_data.iloc[:, 1:], train_data.iloc[:, 0]
    X_val, y_val = validation_data.iloc[:, 1:], validation_data.iloc[:, 0]

    feature_names = [str(i) for i in range(X_train.shape[1])]
    dtrain = xgb.DMatrix(X_train.values, label=y_train, feature_names=feature_names)
    dval = xgb.DMatrix(X_val.values, label=y_val, feature_names=feature_names)

    # MLflow setup
    tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')
    experiment_name = os.environ.get('MLFLOW_EXPERIMENT_NAME')
    parent_run_id = os.environ.get('MLFLOW_PARENT_RUN_ID')
    
    # Try to read parent run ID from preprocessing output if not in env
    if not parent_run_id or parent_run_id == "":
        try:
            mlflow_file = '/opt/ml/input/data/mlflow/parent_run_id.txt'
            if os.path.exists(mlflow_file):
                with open(mlflow_file, 'r') as f:
                    parent_run_id = f.read().strip()
                logger.info(f"Read parent run ID from preprocessing output: {parent_run_id}")
        except Exception as e:
            logger.warning(f"Could not read parent run ID from file: {e}")

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name or 'BankMarketingExperiment')
        mlflow.xgboost.autolog(
            log_input_examples=True,
            log_model_signatures=True,
            log_models=True,
        )

    params = {
        'max_depth': args.max_depth,
        'eta': args.eta,
        'gamma': args.gamma,
        'min_child_weight': args.min_child_weight,
        'subsample': args.subsample,
        'objective': args.objective,
        'eval_metric': 'auc',
    }

    if tracking_uri:
        run_ctx = mlflow.start_run(run_name="train", parent_run_id=parent_run_id) if parent_run_id else mlflow.start_run()
    else:
        run_ctx = open(os.devnull)
    with run_ctx:
        if tracking_uri:
            mlflow.log_params(params)

        model = xgb.train(params, dtrain, args.num_round, evals=[(dval, 'validation')])

        # Evaluate
        y_pred_proba = model.predict(dval)
        y_pred = (y_pred_proba > 0.5).astype(int)

        metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'precision': precision_score(y_val, y_pred),
            'recall': recall_score(y_val, y_pred),
            'f1': f1_score(y_val, y_pred),
            'auc': roc_auc_score(y_val, y_pred_proba),
        }

        if tracking_uri:
            mlflow.log_metrics(metrics)

        logger.info(f'Metrics: {metrics}')

    # Save model for SageMaker
    model_path = '/opt/ml/model'
    os.makedirs(model_path, exist_ok=True)
    pickle.dump(model, open(f'{model_path}/xgboost-model', 'wb'))
    logger.info('Model saved to /opt/ml/model')
