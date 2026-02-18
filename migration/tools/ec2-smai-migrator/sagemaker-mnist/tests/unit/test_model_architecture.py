"""
Model Architecture Tests

Tests for model architecture, layer configurations, and parameter counts.
"""

import pytest
import torch
import torch.nn as nn


class TestModelArchitecture:
    """Test model architecture components"""
    
    def test_layer_initialization(self):
        """Test that layers are properly initialized"""
        layer = nn.Linear(10, 5)
        
        # Check weight and bias shapes
        assert layer.weight.shape == (5, 10)
        assert layer.bias.shape == (5,)
        
        # Check that weights are not all zeros
        assert not torch.allclose(layer.weight, torch.zeros_like(layer.weight))
    
    def test_activation_functions(self):
        """Test activation functions"""
        x = torch.randn(8, 10)
        
        # Test ReLU
        relu = nn.ReLU()
        relu_output = relu(x)
        assert torch.all(relu_output >= 0)  # ReLU should be non-negative
        
        # Test Sigmoid
        sigmoid = nn.Sigmoid()
        sigmoid_output = sigmoid(x)
        assert torch.all(sigmoid_output >= 0) and torch.all(sigmoid_output <= 1)
    
    def test_model_parameter_count(self):
        """Test model parameter counting"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        # For this model: (10*5 + 5) + (5*1 + 1) = 61 parameters
        assert total_params == 61
        assert trainable_params == 61
    
    def test_model_forward_pass(self):
        """Test model forward pass"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 2)
        )
        
        # Test single sample
        x = torch.randn(1, 10)
        output = model(x)
        assert output.shape == (1, 2)
        
        # Test batch
        x_batch = torch.randn(8, 10)
        output_batch = model(x_batch)
        assert output_batch.shape == (8, 2)
    
    def test_model_gradient_flow(self):
        """Test that gradients flow properly"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        
        x = torch.randn(8, 10, requires_grad=True)
        y = torch.randn(8, 1)
        
        output = model(x)
        loss = nn.MSELoss()(output, y)
        loss.backward()
        
        # Check that gradients exist
        for param in model.parameters():
            assert param.grad is not None
            assert not torch.allclose(param.grad, torch.zeros_like(param.grad))


if __name__ == "__main__":
    pytest.main([__file__])
