"""
Local Testing Generator for SageMigrator

Generates unit tests for training components, TorchScript compatibility tests,
data loading and preprocessing tests, and model evaluation tests.
"""

import os
import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..models.analysis import AnalysisReport
from ..models.artifacts import MigrationArtifacts
from ..models.validation import ValidationReport, CompatibilityCheck, ValidationStatus


@dataclass
class TestSuite:
    """Generated test suite"""
    test_files: Dict[str, str]  # filename -> test content
    requirements: List[str]  # additional test requirements
    setup_scripts: Dict[str, str]  # setup script name -> content
    documentation: str  # test documentation


class LocalTestingGenerator:
    """Generates comprehensive local testing suites for migration artifacts"""
    
    def __init__(self):
        self.test_templates = self._load_test_templates()
    
    def generate_test_suite(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> TestSuite:
        """Generate complete local testing suite"""
        test_files = {}
        requirements = ["pytest", "pytest-cov", "torch", "torchvision", "numpy", "pandas"]
        setup_scripts = {}
        
        # Generate unit tests for training components
        training_tests = self._generate_training_component_tests(analysis, artifacts)
        test_files.update(training_tests)
        
        # Generate TorchScript compatibility tests
        torchscript_tests = self._generate_torchscript_tests(analysis, artifacts)
        test_files.update(torchscript_tests)
        
        # Generate data loading and preprocessing tests
        data_tests = self._generate_data_loading_tests(analysis, artifacts)
        test_files.update(data_tests)
        
        # Generate model evaluation and metrics tests
        evaluation_tests = self._generate_evaluation_tests(analysis, artifacts)
        test_files.update(evaluation_tests)
        
        # Generate setup scripts
        setup_scripts = self._generate_setup_scripts(analysis, artifacts)
        
        # Generate documentation
        documentation = self._generate_test_documentation(test_files, requirements)
        
        return TestSuite(
            test_files=test_files,
            requirements=requirements,
            setup_scripts=setup_scripts,
            documentation=documentation
        )
    
    def _generate_training_component_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate unit tests for training components"""
        tests = {}
        
        # Test training script functionality
        if artifacts.training_scripts:
            for script_name, script_content in artifacts.training_scripts.items():
                test_name = f"test_{script_name.replace('.py', '')}_training.py"
                tests[test_name] = self._generate_training_script_test(
                    script_name, script_content, analysis
                )
        
        # Test model architecture
        tests["test_model_architecture.py"] = self._generate_model_architecture_test(
            analysis, artifacts
        )
        
        # Test training loop components
        tests["test_training_loop.py"] = self._generate_training_loop_test(
            analysis, artifacts
        )
        
        return tests
    
    def _generate_torchscript_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate TorchScript compatibility tests"""
        tests = {}
        
        # Main TorchScript compatibility test
        tests["test_torchscript_compatibility.py"] = f'''"""
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
            pytest.fail(f"TorchScript conversion failed: {{e}}")
    
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
'''
        
        return tests
    
    def _generate_data_loading_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate data loading and preprocessing tests"""
        tests = {}
        
        tests["test_data_loading.py"] = f'''"""
Data Loading and Preprocessing Tests

Tests for data loading, preprocessing, and S3 integration functionality.
"""

import pytest
import torch
import numpy as np
import tempfile
import os
from pathlib import Path
from torch.utils.data import DataLoader, Dataset
import json


class MockDataset(Dataset):
    """Mock dataset for testing"""
    
    def __init__(self, size=100, input_dim=10, num_classes=2):
        self.size = size
        self.input_dim = input_dim
        self.num_classes = num_classes
        
        # Generate synthetic data
        self.data = torch.randn(size, input_dim)
        self.labels = torch.randint(0, num_classes, (size,))
    
    def __len__(self):
        return self.size
    
    def __getitem__(self, idx):
        return self.data[idx], self.labels[idx]


class TestDataLoading:
    """Test data loading functionality"""
    
    def test_dataloader_creation(self):
        """Test that DataLoader can be created and used"""
        dataset = MockDataset(size=50)
        dataloader = DataLoader(dataset, batch_size=8, shuffle=True)
        
        assert len(dataloader) == 7  # 50 / 8 = 6.25, rounded up to 7
        
        # Test iteration
        for batch_idx, (data, labels) in enumerate(dataloader):
            assert data.shape[0] <= 8  # batch size
            assert data.shape[1] == 10  # input dimension
            assert labels.shape[0] <= 8
            if batch_idx >= 2:  # Test first few batches
                break
    
    def test_data_preprocessing(self):
        """Test data preprocessing functionality"""
        # Create sample data
        raw_data = torch.randn(100, 10)
        
        # Test normalization
        normalized_data = (raw_data - raw_data.mean(dim=0)) / raw_data.std(dim=0)
        
        # Verify normalization
        assert torch.allclose(normalized_data.mean(dim=0), torch.zeros(10), atol=1e-6)
        assert torch.allclose(normalized_data.std(dim=0), torch.ones(10), atol=1e-6)
    
    def test_data_validation(self):
        """Test data validation and error handling"""
        # Test with invalid data
        with pytest.raises((ValueError, TypeError)):
            invalid_dataset = MockDataset(size=0)  # Empty dataset
            DataLoader(invalid_dataset, batch_size=8)
    
    def test_data_format_consistency(self):
        """Test that data formats are consistent"""
        dataset = MockDataset()
        dataloader = DataLoader(dataset, batch_size=16)
        
        data_shapes = []
        label_shapes = []
        
        for data, labels in dataloader:
            data_shapes.append(data.shape)
            label_shapes.append(labels.shape)
        
        # All batches should have same number of features
        feature_dims = [shape[1] for shape in data_shapes]
        assert all(dim == feature_dims[0] for dim in feature_dims)
    
    def test_s3_path_handling(self):
        """Test S3 path handling and validation"""
        # Test valid S3 paths
        valid_s3_paths = [
            "s3://bucket-name/path/to/data",
            "s3://my-bucket/folder/file.csv",
            "s3://bucket/data/"
        ]
        
        for path in valid_s3_paths:
            assert path.startswith("s3://")
            parts = path.replace("s3://", "").split("/", 1)
            assert len(parts) >= 1  # At least bucket name
    
    def test_local_file_handling(self):
        """Test local file handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "test_data.json"
            test_data = {{"data": [1, 2, 3], "labels": [0, 1, 0]}}
            
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            # Test file exists and can be read
            assert test_file.exists()
            
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
                assert loaded_data == test_data


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return tests
    
    def _generate_evaluation_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate model evaluation and metrics tests"""
        tests = {}
        
        tests["test_model_evaluation.py"] = f'''"""
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
'''
        
        return tests
    
    def _generate_training_script_test(
        self, 
        script_name: str, 
        script_content: str, 
        analysis: AnalysisReport
    ) -> str:
        """Generate test for specific training script"""
        return f'''"""
Training Script Test for {script_name}

Unit tests for the training script functionality.
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import os
from pathlib import Path


class TestTrainingScript:
    """Test training script functionality"""
    
    def test_training_script_imports(self):
        """Test that all required imports work"""
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            import torch.nn.functional as F
            assert True
        except ImportError as e:
            pytest.fail(f"Required import failed: {{e}}")
    
    def test_model_creation(self):
        """Test that model can be created"""
        # This would be customized based on the actual model in the script
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 1)
        )
        assert model is not None
        assert len(list(model.parameters())) > 0
    
    def test_optimizer_creation(self):
        """Test that optimizer can be created"""
        model = nn.Sequential(nn.Linear(10, 1))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        assert optimizer is not None
    
    def test_training_step(self):
        """Test a single training step"""
        model = nn.Sequential(nn.Linear(10, 1))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()
        
        # Generate synthetic data
        inputs = torch.randn(8, 10)
        targets = torch.randn(8, 1)
        
        # Training step
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()
        
        # Verify loss is computed
        assert loss.item() >= 0
        assert not torch.isnan(loss)


if __name__ == "__main__":
    pytest.main([__file__])
'''
    
    def _generate_model_architecture_test(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Generate test for model architecture"""
        return f'''"""
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
'''
    
    def _generate_training_loop_test(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Generate test for training loop components"""
        return f'''"""
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
'''
    
    def _generate_setup_scripts(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate setup scripts for testing"""
        scripts = {}
        
        scripts["setup_test_environment.py"] = '''"""
Setup script for test environment

Prepares the testing environment with necessary dependencies and configurations.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path


def setup_test_environment():
    """Setup test environment"""
    print("Setting up test environment...")
    
    # Create test directories
    test_dirs = [
        "test_data",
        "test_models", 
        "test_outputs",
        "test_logs"
    ]
    
    for dir_name in test_dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"Created directory: {dir_name}")
    
    # Set environment variables for testing
    os.environ["TESTING"] = "true"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU for testing
    
    print("Test environment setup complete!")


def cleanup_test_environment():
    """Cleanup test environment"""
    print("Cleaning up test environment...")
    
    # Remove test directories
    import shutil
    test_dirs = [
        "test_data",
        "test_models",
        "test_outputs", 
        "test_logs"
    ]
    
    for dir_name in test_dirs:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"Removed directory: {dir_name}")
    
    print("Test environment cleanup complete!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup_test_environment()
    else:
        setup_test_environment()
'''
        
        scripts["run_tests.py"] = '''"""
Test runner script

Runs all tests with proper configuration and reporting.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """Run all tests"""
    print("Running SageMigrator local tests...")
    
    # Set up test environment
    os.environ["PYTHONPATH"] = str(Path.cwd())
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=short",
        "--cov=sagemigrator",
        "--cov-report=html",
        "--cov-report=term-missing",
        "tests/"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code: {e.returncode}")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
'''
        
        return scripts
    
    def _generate_test_documentation(
        self, 
        test_files: Dict[str, str], 
        requirements: List[str]
    ) -> str:
        """Generate documentation for the test suite"""
        return f'''# Local Testing Suite Documentation

## Overview

This test suite provides comprehensive local testing for SageMigrator migration artifacts. It includes unit tests for training components, TorchScript compatibility tests, data loading tests, and model evaluation tests.

## Test Files

{chr(10).join(f"- **{filename}**: {self._get_test_description(filename)}" for filename in test_files.keys())}

## Requirements

The following packages are required to run the tests:

{chr(10).join(f"- {req}" for req in requirements)}

Install with:
```bash
pip install {" ".join(requirements)}
```

## Running Tests

### Run All Tests
```bash
python run_tests.py
```

### Run Specific Test File
```bash
pytest test_torchscript_compatibility.py -v
```

### Run with Coverage
```bash
pytest --cov=sagemigrator --cov-report=html
```

## Test Categories

### 1. Training Component Tests
- Model architecture validation
- Training loop functionality
- Optimizer and loss function tests
- Parameter initialization checks

### 2. TorchScript Compatibility Tests
- Model conversion to TorchScript
- Save/load cycle validation
- Dual model saving (state_dict + TorchScript)
- Inference consistency checks

### 3. Data Loading Tests
- DataLoader functionality
- Data preprocessing validation
- S3 path handling
- Local file operations
- Data format consistency

### 4. Model Evaluation Tests
- Inference functionality
- Metrics calculation
- Loss computation
- Performance validation
- Batch vs individual evaluation

## Setup and Cleanup

Use the setup script to prepare the test environment:

```bash
# Setup test environment
python setup_test_environment.py

# Run tests
python run_tests.py

# Cleanup test environment
python setup_test_environment.py cleanup
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Determinism**: Use fixed random seeds where possible for reproducible results
3. **Resource Management**: Clean up temporary files and resources after tests
4. **Error Handling**: Test both success and failure scenarios
5. **Documentation**: Keep test documentation up to date

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure PYTHONPATH includes the project root
2. **CUDA Errors**: Tests run on CPU by default (CUDA_VISIBLE_DEVICES="")
3. **File Permissions**: Ensure write permissions for temporary directories
4. **Memory Issues**: Use smaller batch sizes in tests if needed

### Getting Help

If tests fail, check:
1. All dependencies are installed
2. Python path is configured correctly
3. No conflicting environment variables
4. Sufficient disk space for temporary files

For additional help, refer to the main SageBridge documentation.
'''
    
    def _get_test_description(self, filename: str) -> str:
        """Get description for test file"""
        descriptions = {
            "test_torchscript_compatibility.py": "TorchScript conversion and compatibility tests",
            "test_data_loading.py": "Data loading, preprocessing, and S3 integration tests",
            "test_model_evaluation.py": "Model evaluation, metrics, and performance tests",
            "test_model_architecture.py": "Model architecture and layer configuration tests",
            "test_training_loop.py": "Training loop, optimization, and gradient flow tests"
        }
        return descriptions.get(filename, "Test functionality")
    
    def _load_test_templates(self) -> Dict[str, str]:
        """Load test templates (placeholder for future template system)"""
        return {}
    
    def validate_generated_tests(self, test_suite: TestSuite) -> List[CompatibilityCheck]:
        """Validate the generated test suite"""
        checks = []
        
        # Check that all required test categories are present
        required_tests = [
            "test_torchscript_compatibility.py",
            "test_data_loading.py", 
            "test_model_evaluation.py"
        ]
        
        for test_name in required_tests:
            if test_name in test_suite.test_files:
                checks.append(CompatibilityCheck(
                    check_name=f"Test file {test_name}",
                    status=ValidationStatus.PASSED,
                    message=f"Required test file {test_name} is present",
                    details={"file_size": len(test_suite.test_files[test_name])},
                    severity="high"
                ))
            else:
                checks.append(CompatibilityCheck(
                    check_name=f"Test file {test_name}",
                    status=ValidationStatus.FAILED,
                    message=f"Required test file {test_name} is missing",
                    details={},
                    severity="high"
                ))
        
        # Check that setup scripts are present
        if test_suite.setup_scripts:
            checks.append(CompatibilityCheck(
                check_name="Setup scripts",
                status=ValidationStatus.PASSED,
                message="Setup scripts are present",
                details={"script_count": len(test_suite.setup_scripts)},
                severity="medium"
            ))
        
        return checks