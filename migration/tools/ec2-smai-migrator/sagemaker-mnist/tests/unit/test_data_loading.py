"""
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
            test_data = {"data": [1, 2, 3], "labels": [0, 1, 0]}
            
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            # Test file exists and can be read
            assert test_file.exists()
            
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
                assert loaded_data == test_data


if __name__ == "__main__":
    pytest.main([__file__])
