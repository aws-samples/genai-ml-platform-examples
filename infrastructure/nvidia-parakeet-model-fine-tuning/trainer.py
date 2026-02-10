"""
ASR Model Training and Evaluation
--------------------------------
This script handles:
1. Training an ASR model from a pretrained base or continuing from a checkpoint
2. Evaluating model performance on test data
3. Logging metrics to MLflow and TensorBoard
4. Model registration for production
"""

import os
import time
import json
import torch
import pandas as pd
import mlflow
from tqdm import tqdm
from omegaconf import OmegaConf
from nemo.collections.asr.models import ASRModel
from nemo.utils import logging, model_utils
from nemo.utils.get_rank import is_global_rank_zero
from lightning.pytorch import Trainer
from lightning.pytorch.callbacks.early_stopping import EarlyStopping
from nemo.collections.asr.metrics.wer import word_error_rate
from nemo.utils import exp_manager
from lightning.pytorch.strategies import FSDPStrategy
from nemo.utils.trainer_utils import resolve_trainer_cfg
import argparse

# Set PyTorch configuration
torch.set_float32_matmul_precision('medium')
torch.cuda.empty_cache()
def is_main_process():
    return get_rank() == 0

class ASRTrainer:
    """Handles ASR model training, evaluation, and logging."""
    
    def __init__(self, config_path, tokenizer_path=None, experiment_name="parakeet_fine_tuning"):
        """
        Initialize the ASR trainer with configuration settings.
        
        Args:
            config_path: Path to the YAML configuration file
            tokenizer_path: Path to the tokenizer directory
            max_steps: Maximum training steps
            accelerator: Hardware accelerator type ('gpu', 'cpu', etc.)
            devices: Number of devices to use for training
        """
        self.config = OmegaConf.load(config_path)
        self.tokenizer_path = tokenizer_path
        self.experiment_name = experiment_name
        
        # Update tokenizer configuration
        self.update_config()
    
    def update_config(self):
        """Update configuration with runtime settings."""
        # If we're using a custom tokenizer path
        if self.tokenizer_path:
            self.config.model.tokenizer.dir = self.tokenizer_path
        
        # Always ensure normalize_text is consistent
        self.config.model.train_ds.normalize_text = self.config.model.normalize_text
        self.config.model.validation_ds.normalize_text = self.config.model.normalize_text
        self.config.model.test_ds.normalize_text = self.config.model.normalize_text
    
    def get_base_model(self, trainer):
        """
        Get the base model to start training from based on config settings.
        
        Args:
            trainer: PyTorch Lightning Trainer
            
        Returns:
            ASRModel instance
        """
        model_path = self.config.init_from_nemo_model
        pretrained_name = self.config.init_from_pretrained_model
        
        if model_path is not None and pretrained_name is not None:
            raise ValueError("Only set one of `init_from_nemo_model` or `init_from_pretrained_model` in config but not both")
        elif model_path is None and pretrained_name is None:
            # Use a default pretrained model
            logging.info(f"No model specified, defaulting to: {pretrained_name}")
        
        asr_model = None
        if model_path is not None:
            logging.info(f"Loading model from: {model_path}")
            asr_model = ASRModel.restore_from(restore_path=model_path)
        else:
            # Handle multi-GPU download efficiently
            num_ranks = trainer.num_devices * trainer.num_nodes if hasattr(trainer, 'num_nodes') else trainer.num_devices

            if num_ranks > 1 and is_global_rank_zero():
                logging.info(f"Downloading pretrained model '{pretrained_name}' on main process")
                asr_model = ASRModel.from_pretrained(model_name=pretrained_name)
            else:
                # Wait for model download to complete on main process
                wait_time = 1 if is_global_rank_zero() else 60
                logging.info(f"Waiting {wait_time}s for model download")
                time.sleep(wait_time)
                asr_model = ASRModel.from_pretrained(model_name=pretrained_name)
        asr_model.to(f"cuda:{int(os.environ.get('LOCAL_RANK', 0))}")
        # Unfreezing encoders to update the parameters
        asr_model.encoder.unfreeze()
        logging.info("Model encoder has been un-frozen")
        asr_model.set_trainer(trainer)
        return asr_model
    
    def update_tokenizer(self, asr_model):
        """
        Update the tokenizer of the model if specified in config.
        
        Args:
            asr_model: The ASR model to update
            
        Returns:
            Updated ASR model
        """
        if not self.config.model.tokenizer.update_tokenizer:
            return asr_model
            
        vocab_size = asr_model.tokenizer.vocab_size
        decoder = asr_model.decoder.state_dict()
        joint_state = asr_model.joint.state_dict() if hasattr(asr_model, 'joint') else None
        
        tokenizer_dir = self.config.model.tokenizer.dir
        tokenizer_type = self.config.model.tokenizer.type
        
        if tokenizer_dir is None:
            raise ValueError("Tokenizer directory must be specified if update_tokenizer is True")
            
        logging.info(f"Updating tokenizer: {tokenizer_type} from {tokenizer_dir}")
        asr_model.change_vocabulary(new_tokenizer_dir=tokenizer_dir, new_tokenizer_type=tokenizer_type)
        

        if asr_model.tokenizer.vocab_size != vocab_size:
            logging.warning(
                "Vocabulary size changed. Decoder will be reinitialized."
            )
        else:
            asr_model.decoder.load_state_dict(decoder)
            if joint_state is not None:
                asr_model.joint.load_state_dict(joint_state)
        
        
        
        return asr_model
    
    def setup_dataloaders(self, asr_model):
        """
        Set up training, validation and test dataloaders.
        
        Args:
            asr_model: ASR model
            
        Returns:
            ASR model with dataloaders configured
        """
        cfg = model_utils.convert_model_config_to_dict_config(self.config)
        
        # Setup training data
        asr_model.setup_training_data(cfg.model.train_ds)
        
        # Setup validation data
        if isinstance(cfg.model.validation_ds, list):
            asr_model.setup_multiple_validation_data(cfg.model.validation_ds)
        else:
            asr_model.setup_validation_data(cfg.model.validation_ds)
        
        # Setup test data if available
        if hasattr(cfg.model, 'test_ds') and cfg.model.test_ds.manifest_filepath is not None:
            if isinstance(cfg.model.test_ds, list):
                asr_model.setup_multiple_test_data(cfg.model.test_ds)
            else:
                asr_model.setup_test_data(cfg.model.test_ds)
        
        return asr_model
    
    def create_trainer(self):
        """
        Create PyTorch Lightning Trainer with logging configuration.
        
        Args:
            run_id: MLflow run ID for logging
            
        Returns:
            PyTorch Lightning Trainer
        """
        
        trainer = Trainer(
            strategy=self.config.trainer_strategy.strategy, # ddp or deepspeed
            devices=self.config.trainer.devices,
            accelerator=self.config.trainer.accelerator,
            max_epochs=self.config.trainer.max_epochs,
            max_steps=self.config.trainer.max_steps,
            log_every_n_steps=self.config.trainer.log_every_n_steps,
            enable_checkpointing=False,
            logger = self.config.trainer.logger,
            check_val_every_n_epoch = self.config.trainer.check_val_every_n_epoch,
            precision=self.config.trainer.precision,  # Mixed precision for better memory efficiency
            sync_batchnorm=self.config.trainer.sync_batchnorm,  # Synchronize batch norm across GPUs
            gradient_clip_val=self.config.trainer.gradient_clip_val  # No gradient clipping
        )

        logdir = exp_manager.exp_manager(trainer, self.config.exp_manager)
        return trainer

    
    def train(self, model_path):
        """
        Train the ASR model.
        
        Args:
            model_path: Path to save the trained model
            
        Returns:
            Trained model path and MLflow run ID
        """

        trainer = self.create_trainer()
            
        # Initialize model based on config settings
        asr_model = self.get_base_model(trainer)
        
        # Update tokenizer if needed
        if self.config.model.tokenizer.update_tokenizer:
            asr_model = self.update_tokenizer(asr_model)
        
        # Setup dataloaders
        asr_model = self.setup_dataloaders(asr_model)
        
        # Setup optimization
        asr_model.setup_optimization(self.config.model.optim)
        
        # Setup SpecAug if available
        if hasattr(self.config.model, 'spec_augment') and self.config.model.spec_augment is not None:
            asr_model.spec_augment = ASRModel.from_config_dict(self.config.model.spec_augment)
            
        # Train the model
        trainer.fit(asr_model)
        
        # Save the trained model
        os.makedirs(os.path.dirname(model_path), exist_ok=True)

        asr_model.save_to(model_path)
        logging.info(f"Last Epoch Model Saved to: {model_path}")
        time.sleep(50)
        
        return model_path
    

def main():
    """Main function to run the training and evaluation."""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='ASR Model Training and Evaluation')
    parser.add_argument('--config_path', type=str, default="configs/fine_tuning_config.yaml",
                        help='Path to the YAML configuration file')
    parser.add_argument('--model_path', type=str, default=None,
                        help='Path to save the trained model')
    parser.add_argument('--tokenizer_path', type=str, default=None,
                        help='Path to the tokenizer directory')
    
    args = parser.parse_args()
    
    # Create trainer
    trainer = ASRTrainer(
        config_path=args.config_path,
        tokenizer_path=args.tokenizer_path
    )
    
    # Set model output path if not specified
    if args.model_path is None:
        args.model_path = os.path.join('trained_models', f"{trainer.config.name}.nemo")
    
    # Train model
    trained_model_path = trainer.train(args.model_path)
    


if __name__ == "__main__":
    main()
