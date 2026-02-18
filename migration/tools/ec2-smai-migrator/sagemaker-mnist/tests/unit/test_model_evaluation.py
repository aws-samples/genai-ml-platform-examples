"""
Model Evaluation and Metrics Tests

Tests for model evaluation, metrics calculation, and performance validation.
"""

import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


class SimpleClassifier(nn.Module):
    """Simple classifier for testing"""
    
    def __init__(self, input_dim=10, num_classes=2):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 5)
        self.fc2 = nn.Linear(5, num_classes)
        self.dropout = nn.Dropout(0.1)
    
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class TestModelEvaluation:
    """Test model evaluation functionality"""
    
    def test_model_inference(self):
        """Test model inference functionality"""
        model = SimpleClassifier(input_dim=10, num_classes=2)
        model.eval()
        
        # Test single sample
        sample_input = torch.randn(1, 10)
        with torch.no_grad():
            output = model(sample_input)
            assert output.shape == (1, 2)
            
        # Test batch
        batch_input = torch.randn(8, 10)
        with torch.no_grad():
            batch_output = model(batch_input)
            assert batch_output.shape == (8, 2)
    
    def test_metrics_calculation(self):
        """Test metrics calculation"""
        # Generate synthetic predictions and labels
        y_true = np.array([0, 1, 1, 0, 1, 0, 1, 1, 0, 0])
        y_pred = np.array([0, 1, 0, 0, 1, 1, 1, 1, 0, 0])
        
        # Calculate metrics
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred)
        recall = recall_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        
        # Verify metrics are in valid ranges
        assert 0 <= accuracy <= 1
        assert 0 <= precision <= 1
        assert 0 <= recall <= 1
        assert 0 <= f1 <= 1
        
        # Test specific values for this example
        assert accuracy == 0.8  # 8/10 correct
    
    def test_loss_calculation(self):
        """Test loss calculation"""
        model = SimpleClassifier()
        criterion = nn.CrossEntropyLoss()
        
        # Generate test data
        inputs = torch.randn(8, 10)
        targets = torch.randint(0, 2, (8,))
        
        # Calculate loss
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        
        # Verify loss properties
        assert loss.item() >= 0  # Loss should be non-negative
        assert not torch.isnan(loss)  # Loss should not be NaN
        assert torch.isfinite(loss)  # Loss should be finite
    
    def test_model_performance_validation(self):
        """Test model performance validation"""
        model = SimpleClassifier()
        
        # Generate synthetic dataset
        n_samples = 100
        inputs = torch.randn(n_samples, 10)
        targets = torch.randint(0, 2, (n_samples,))
        
        model.eval()
        with torch.no_grad():
            outputs = model(inputs)
            predictions = torch.argmax(outputs, dim=1)
        
        # Calculate accuracy
        accuracy = (predictions == targets).float().mean().item()
        
        # For untrained model, accuracy should be around 0.5 for binary classification
        assert 0.2 <= accuracy <= 0.8  # Reasonable range for random model
    
    def test_evaluation_consistency(self):
        """Test that evaluation results are consistent"""
        model = SimpleClassifier()
        model.eval()
        
        # Same input should produce same output
        test_input = torch.randn(5, 10)
        
        with torch.no_grad():
            output1 = model(test_input)
            output2 = model(test_input)
            
        torch.testing.assert_close(output1, output2, rtol=1e-5, atol=1e-5)
    
    def test_batch_vs_individual_evaluation(self):
        """Test that batch evaluation matches individual evaluation"""
        model = SimpleClassifier()
        model.eval()
        
        # Generate test data
        batch_input = torch.randn(4, 10)
        
        with torch.no_grad():
            # Batch evaluation
            batch_output = model(batch_input)
            
            # Individual evaluations
            individual_outputs = []
            for i in range(4):
                individual_output = model(batch_input[i:i+1])
                individual_outputs.append(individual_output)
            
            stacked_individual = torch.cat(individual_outputs, dim=0)
        
        # Results should match
        torch.testing.assert_close(batch_output, stacked_individual, rtol=1e-5, atol=1e-5)


if __name__ == "__main__":
    pytest.main([__file__])
