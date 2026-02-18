#!/usr/bin/env python3
"""
SageMaker Training Script for MNIST CNN
Converted from EC2 training code by SageMigrator
"""

import argparse
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.optim.lr_scheduler import StepLR
import pandas as pd
import numpy as np


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        output = F.log_softmax(x, dim=1)
        return output


def train_epoch(args, model, device, train_loader, optimizer, epoch):
    model.train()
    total_loss = 0
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        
        if batch_idx % args.log_interval == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]	Loss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))
            if args.dry_run:
                break
    
    return total_loss / len(train_loader)


def test_model(model, device, test_loader):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(output, target, reduction='sum').item()
            pred = output.argmax(dim=1, keepdim=True)
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)
    accuracy = 100. * correct / len(test_loader.dataset)

    print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset), accuracy))
    
    return test_loss, accuracy


def load_data_from_parquet(data_dir):
    """Load preprocessed data from parquet files"""
    try:
        # Try to load preprocessed parquet data first
        train_path = os.path.join(data_dir, 'training', 'train.parquet')
        test_path = os.path.join(data_dir, 'testing', 'test.parquet')
        
        if os.path.exists(train_path) and os.path.exists(test_path):
            print("Loading preprocessed parquet data...")
            train_df = pd.read_parquet(train_path)
            test_df = pd.read_parquet(test_path)
            
            # Separate features and targets
            train_features = train_df.drop('target', axis=1).values
            train_targets = train_df['target'].values
            test_features = test_df.drop('target', axis=1).values
            test_targets = test_df['target'].values
            
            # Reshape to image format (28x28)
            train_features = train_features.reshape(-1, 1, 28, 28)
            test_features = test_features.reshape(-1, 1, 28, 28)
            
            # Convert to tensors
            train_data = torch.utils.data.TensorDataset(
                torch.FloatTensor(train_features), 
                torch.LongTensor(train_targets)
            )
            test_data = torch.utils.data.TensorDataset(
                torch.FloatTensor(test_features), 
                torch.LongTensor(test_targets)
            )
            
            return train_data, test_data
        else:
            print("Parquet files not found, falling back to MNIST download...")
            return None, None
            
    except Exception as e:
        print(f"Error loading parquet data: {e}")
        print("Falling back to MNIST download...")
        return None, None


def main():
    # Training settings
    parser = argparse.ArgumentParser(description='PyTorch MNIST Example for SageMaker')
    parser.add_argument('--batch-size', type=int, default=64, metavar='N',
                        help='input batch size for training (default: 64)')
    parser.add_argument('--test-batch-size', type=int, default=1000, metavar='N',
                        help='input batch size for testing (default: 1000)')
    parser.add_argument('--epochs', type=int, default=10, metavar='N',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--lr', type=float, default=1.0, metavar='LR',
                        help='learning rate (default: 1.0)')
    parser.add_argument('--gamma', type=float, default=0.7, metavar='M',
                        help='Learning rate step gamma (default: 0.7)')
    parser.add_argument('--dry-run', action='store_true',
                        help='quickly check a single pass')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status')
    
    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--data-dir', type=str, default=os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data'))
    
    args = parser.parse_args()

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    torch.manual_seed(args.seed)

    # Try to load preprocessed data, fallback to MNIST download
    train_data, test_data = load_data_from_parquet(args.data_dir)
    
    if train_data is None or test_data is None:
        # Fallback to downloading MNIST data
        print("Downloading MNIST dataset...")
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])
        train_data = datasets.MNIST('/tmp/data', train=True, download=True, transform=transform)
        test_data = datasets.MNIST('/tmp/data', train=False, transform=transform)

    # Create data loaders
    train_kwargs = {'batch_size': args.batch_size, 'shuffle': True}
    test_kwargs = {'batch_size': args.test_batch_size, 'shuffle': False}
    
    if torch.cuda.is_available():
        cuda_kwargs = {'num_workers': 1, 'pin_memory': True}
        train_kwargs.update(cuda_kwargs)
        test_kwargs.update(cuda_kwargs)

    train_loader = torch.utils.data.DataLoader(train_data, **train_kwargs)
    test_loader = torch.utils.data.DataLoader(test_data, **test_kwargs)

    # Initialize model and optimizer
    model = Net().to(device)
    optimizer = optim.Adadelta(model.parameters(), lr=args.lr)
    scheduler = StepLR(optimizer, step_size=1, gamma=args.gamma)

    # Training loop
    best_accuracy = 0
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(args, model, device, train_loader, optimizer, epoch)
        test_loss, accuracy = test_model(model, device, test_loader)
        scheduler.step()
        
        # Save best model
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            print(f"New best accuracy: {best_accuracy:.2f}%")

    # Save the model in SageMaker format
    print(f"Saving model to {args.model_dir}")
    os.makedirs(args.model_dir, exist_ok=True)
    
    # Save the model state dict
    model_path = os.path.join(args.model_dir, 'model.pth')
    torch.save(model.state_dict(), model_path)
    
    # Save the complete model for inference
    model_full_path = os.path.join(args.model_dir, 'model.pt')
    torch.save(model, model_full_path)
    
    # Save model info
    model_info = {
        'model_name': 'mnist_cnn',
        'framework': 'pytorch',
        'framework_version': torch.__version__,
        'final_accuracy': best_accuracy,
        'epochs_trained': args.epochs
    }
    
    import json
    with open(os.path.join(args.model_dir, 'model_info.json'), 'w') as f:
        json.dump(model_info, f, indent=2)
    
    print(f"Training completed! Final accuracy: {best_accuracy:.2f}%")
    print(f"Model saved to: {args.model_dir}")


if __name__ == '__main__':
    main()
