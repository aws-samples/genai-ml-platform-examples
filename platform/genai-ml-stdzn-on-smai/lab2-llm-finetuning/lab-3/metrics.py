# metrics.py
from rouge_score import rouge_scorer
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import mlflow

def rouge1_metric(eval_df, builtin_metrics):
    scorer = rouge_scorer.RougeScorer(['rouge1'], use_stemmer=True)
    scores = [scorer.score(target, pred)['rouge1'].fmeasure 
              for pred, target in zip(eval_df["prediction"], eval_df["target"])]
    return sum(scores) / len(scores)

def rouge2_metric(eval_df, builtin_metrics):
    scorer = rouge_scorer.RougeScorer(['rouge2'], use_stemmer=True)
    scores = [scorer.score(target, pred)['rouge2'].fmeasure 
              for pred, target in zip(eval_df["prediction"], eval_df["target"])]
    return sum(scores) / len(scores)

def rougeL_metric(eval_df, builtin_metrics):
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = [scorer.score(target, pred)['rougeL'].fmeasure 
              for pred, target in zip(eval_df["prediction"], eval_df["target"])]
    return sum(scores) / len(scores)

def bleu_metric(eval_df, builtin_metrics):
    smooth = SmoothingFunction().method1
    scores = [sentence_bleu([target.split()], pred.split(), smoothing_function=smooth)
              for pred, target in zip(eval_df["prediction"], eval_df["target"])]
    return sum(scores) / len(scores)

rouge1 = mlflow.metrics.make_metric(eval_fn=rouge1_metric, greater_is_better=True, name="rouge1")
rouge2 = mlflow.metrics.make_metric(eval_fn=rouge2_metric, greater_is_better=True, name="rouge2")
rougeL = mlflow.metrics.make_metric(eval_fn=rougeL_metric, greater_is_better=True, name="rougeL")
bleu = mlflow.metrics.make_metric(eval_fn=bleu_metric, greater_is_better=True, name="bleu")
