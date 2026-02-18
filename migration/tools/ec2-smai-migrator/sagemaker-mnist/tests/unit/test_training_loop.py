"""
Training Loop Tests

Tests for training loop components including optimization, loss calculation, and metrics.
"""

import pytest
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


class TestTrainingLoop:
    """Test training loop functionality"""
    
    def test_training_loop_basic(self):
        """Test basic training loop functionality"""
        # Create simple model and data
        model = nn.Linear(10, 1)
        optimizer = optim.SGD(model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        
        # Generate synthetic data
        X = torch.randn(100, 10)
        y = torch.randn(100, 1)
        dataset = TensorDataset(X, y)
        dataloader = DataLoader(dataset, batch_size=16)
        
        # Training loop
        model.train()
        initial_loss = None
        final_loss = None
        
        for epoch in range(5):
            epoch_loss = 0.0
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            if initial_loss is None:
                initial_loss = epoch_loss
            final_loss = epoch_loss
        
        # Loss should generally decrease (though not guaranteed for random data)
        assert final_loss is not None
        assert initial_loss is not None
    
    def test_optimizer_step(self):
        """Test optimizer step functionality"""
        model = nn.Linear(5, 1)
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        
        # Store initial parameters
        initial_params = [param.clone() for param in model.parameters()]
        
        # Perform optimization step
        x = torch.randn(8, 5)
        y = torch.randn(8, 1)
        
        optimizer.zero_grad()
        output = model(x)
        loss = nn.MSELoss()(output, y)
        loss.backward()
        optimizer.step()
        
        # Parameters should have changed
        for initial_param, current_param in zip(initial_params, model.parameters()):
            assert not torch.allclose(initial_param, current_param)
    
    def test_gradient_accumulation(self):
        """Test gradient accumulation"""
        model = nn.Linear(5, 1)
        optimizer = optim.SGD(model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        
        # Generate data
        x1 = torch.randn(4, 5)
        y1 = torch.randn(4, 1)
        x2 = torch.randn(4, 5)
        y2 = torch.randn(4, 1)
        
        # Method 1: Single batch
        optimizer.zero_grad()
        x_combined = torch.cat([x1, x2], dim=0)
        y_combined = torch.cat([y1, y2], dim=0)
        output_combined = model(x_combined)
        loss_combined = criterion(output_combined, y_combined)
        loss_combined.backward()
        grad_combined = [param.grad.clone() for param in model.parameters()]
        
        # Method 2: Gradient accumulation
        model.zero_grad()  # Reset model
        optimizer.zero_grad()
        
        # First batch
        output1 = model(x1)
        loss1 = criterion(output1, y1) / 2  # Scale by number of accumulation steps
        loss1.backward()
        
        # Second batch (accumulate)
        output2 = model(x2)
        loss2 = criterion(output2, y2) / 2
        loss2.backward()
        
        grad_accumulated = [param.grad.clone() for param in model.parameters()]
        
        # Gradients should be similar (within numerical precision)
        for g1, g2 in zip(grad_combined, grad_accumulated):
            torch.testing.assert_close(g1, g2, rtol=1e-4, atol=1e-4)
    
    def test_learning_rate_scheduling(self):
        """Test learning rate scheduling"""
        model = nn.Linear(5, 1)
        optimizer = optim.SGD(model.parameters(), lr=0.1)
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=2, gamma=0.5)
        
        # Initial learning rate
        assert optimizer.param_groups[0]['lr'] == 0.1
        
        # After 1 step (no change)
        scheduler.step()
        assert optimizer.param_groups[0]['lr'] == 0.1
        
        # After 2 steps (should decrease)
        scheduler.step()
        assert optimizer.param_groups[0]['lr'] == 0.05
        
        # After 4 steps total (should decrease again)
        scheduler.step()
        scheduler.step()
        assert optimizer.param_groups[0]['lr'] == 0.025
    
    def test_model_mode_switching(self):
        """Test switching between train and eval modes"""
        model = nn.Sequential(
            nn.Linear(5, 3),
            nn.Dropout(0.5),
            nn.Linear(3, 1)
        )
        
        # Test training mode
        model.train()
        assert model.training
        for module in model.modules():
            if hasattr(module, 'training'):
                assert module.training
        
        # Test evaluation mode
        model.eval()
        assert not model.training
        for module in model.modules():
            if hasattr(module, 'training'):
                assert not module.training


if __name__ == "__main__":
    pytest.main([__file__])
