"""
TorchScript Compatibility Tests

Tests to ensure models can be converted to and loaded from TorchScript format.
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import os
from pathlib import Path


class TestTorchScriptCompatibility:
    """Test TorchScript model conversion and loading"""
    
    def test_model_torchscript_conversion(self):
        """Test that models can be converted to TorchScript"""
        # Create a simple test model
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        
        # Test conversion to TorchScript
        model.eval()
        example_input = torch.randn(1, 10)
        
        try:
            traced_model = torch.jit.trace(model, example_input)
            assert traced_model is not None
            
            # Test that traced model produces same output
            with torch.no_grad():
                original_output = model(example_input)
                traced_output = traced_model(example_input)
                torch.testing.assert_close(original_output, traced_output, rtol=1e-5, atol=1e-5)
                
        except Exception as e:
            pytest.fail(f"TorchScript conversion failed: {e}")
    
    def test_torchscript_save_load_cycle(self):
        """Test saving and loading TorchScript models"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        
        model.eval()
        example_input = torch.randn(1, 10)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "model.pt"
            
            # Convert to TorchScript and save
            traced_model = torch.jit.trace(model, example_input)
            torch.jit.save(traced_model, model_path)
            
            # Load and test
            loaded_model = torch.jit.load(model_path)
            
            with torch.no_grad():
                original_output = traced_model(example_input)
                loaded_output = loaded_model(example_input)
                torch.testing.assert_close(original_output, loaded_output, rtol=1e-5, atol=1e-5)
    
    def test_dual_model_saving(self):
        """Test saving both state_dict and TorchScript versions"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        
        model.eval()
        example_input = torch.randn(1, 10)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dict_path = Path(temp_dir) / "model_state_dict.pth"
            torchscript_path = Path(temp_dir) / "model_torchscript.pt"
            
            # Save state dict
            torch.save(model.state_dict(), state_dict_path)
            
            # Save TorchScript
            traced_model = torch.jit.trace(model, example_input)
            torch.jit.save(traced_model, torchscript_path)
            
            # Verify both files exist and can be loaded
            assert state_dict_path.exists()
            assert torchscript_path.exists()
            
            # Test state dict loading
            new_model = nn.Sequential(
                nn.Linear(10, 5),
                nn.ReLU(),
                nn.Linear(5, 1)
            )
            new_model.load_state_dict(torch.load(state_dict_path))
            
            # Test TorchScript loading
            loaded_torchscript = torch.jit.load(torchscript_path)
            
            # Verify outputs match
            with torch.no_grad():
                state_dict_output = new_model(example_input)
                torchscript_output = loaded_torchscript(example_input)
                torch.testing.assert_close(state_dict_output, torchscript_output, rtol=1e-5, atol=1e-5)


if __name__ == "__main__":
    pytest.main([__file__])
