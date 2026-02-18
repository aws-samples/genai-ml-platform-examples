"""
Pattern Detector for SageBridge

Detects training patterns, data loading patterns, and model patterns in source code.
"""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass

from ..models.analysis import PatternAnalysis


logger = logging.getLogger(__name__)


@dataclass
class DetectedPattern:
    """Information about a detected pattern"""
    pattern_type: str
    pattern_name: str
    file_path: str
    line_number: int
    confidence: float
    sagemaker_equivalent: Optional[str] = None
    migration_notes: Optional[str] = None


class PatternDetector:
    """
    Detects distributed training patterns, data loading patterns, and model patterns.
    
    Identifies patterns in source code and maps them to SageMaker equivalents.
    """
    
    # Distributed training patterns
    DISTRIBUTED_PATTERNS = {
        'DataParallel': {
            'signatures': ['torch.nn.DataParallel', 'nn.DataParallel', 'DataParallel('],
            'sagemaker_equivalent': 'SageMaker distributed training',
            'migration_notes': 'Use SageMaker distributed training configuration'
        },
        'DistributedDataParallel': {
            'signatures': ['torch.nn.parallel.DistributedDataParallel', 'DistributedDataParallel(', 'DDP('],
            'sagemaker_equivalent': 'SageMaker distributed training',
            'migration_notes': 'Configure distribution in SageMaker estimator'
        },
        'torch.distributed': {
            'signatures': ['torch.distributed.init_process_group', 'dist.init_process_group', 'torch.distributed.'],
            'sagemaker_equivalent': 'SageMaker distributed training',
            'migration_notes': 'SageMaker handles process group initialization'
        },
        'horovod': {
            'signatures': ['import horovod', 'horovod.torch', 'hvd.'],
            'sagemaker_equivalent': 'SageMaker distributed training',
            'migration_notes': 'Replace Horovod with SageMaker distributed training'
        }
    }
    
    # Data loading patterns
    DATA_LOADING_PATTERNS = {
        'local_files': {
            'signatures': ['open(', 'pd.read_csv(', 'np.load(', 'torch.load(', 'pickle.load('],
            'sagemaker_equivalent': 'S3 data input',
            'migration_notes': 'Use S3 input channels in SageMaker'
        },
        'custom_dataset': {
            'signatures': ['class.*Dataset', 'torch.utils.data.Dataset', 'Dataset.__init__'],
            'sagemaker_equivalent': 'SageMaker compatible dataset',
            'migration_notes': 'Ensure dataset works with S3 data paths'
        },
        'dataloader': {
            'signatures': ['DataLoader(', 'torch.utils.data.DataLoader'],
            'sagemaker_equivalent': 'SageMaker DataLoader',
            'migration_notes': 'Configure for distributed training if needed'
        },
        'torchvision_datasets': {
            'signatures': ['torchvision.datasets', 'datasets.CIFAR', 'datasets.MNIST', 'datasets.ImageFolder'],
            'sagemaker_equivalent': 'Manual data download',
            'migration_notes': 'Implement manual data download and preprocessing'
        },
        's3_integration': {
            'signatures': ['boto3.client', 's3.download_file', 's3.upload_file', 'S3Downloader', 'S3Uploader'],
            'sagemaker_equivalent': 'Native S3 integration',
            'migration_notes': 'Already compatible with SageMaker'
        }
    }
    
    # Model patterns
    MODEL_PATTERNS = {
        'sequential_model': {
            'signatures': ['nn.Sequential', 'torch.nn.Sequential', 'Sequential('],
            'sagemaker_equivalent': 'Compatible',
            'migration_notes': 'No changes needed'
        },
        'custom_model': {
            'signatures': ['class.*nn.Module', 'nn.Module.__init__', 'super().__init__()'],
            'sagemaker_equivalent': 'Compatible',
            'migration_notes': 'Ensure model can be serialized'
        },
        'model_saving': {
            'signatures': ['torch.save(', 'model.save(', 'joblib.dump(', 'pickle.dump('],
            'sagemaker_equivalent': 'SageMaker model artifacts',
            'migration_notes': 'Save to /opt/ml/model/ in SageMaker'
        },
        'model_loading': {
            'signatures': ['torch.load(', 'model.load(', 'joblib.load(', 'pickle.load('],
            'sagemaker_equivalent': 'SageMaker model loading',
            'migration_notes': 'Load from /opt/ml/model/ in SageMaker'
        },
        'torchscript': {
            'signatures': ['torch.jit.script', 'torch.jit.trace', 'torch.jit.save'],
            'sagemaker_equivalent': 'Compatible',
            'migration_notes': 'Recommended for SageMaker inference'
        },
        'custom_loss': {
            'signatures': ['class.*Loss', 'nn.Module.*forward', 'def.*loss'],
            'sagemaker_equivalent': 'Compatible',
            'migration_notes': 'Ensure loss function is included in training script'
        },
        'custom_metrics': {
            'signatures': ['def.*accuracy', 'def.*precision', 'def.*recall', 'def.*f1', 'sklearn.metrics'],
            'sagemaker_equivalent': 'SageMaker metrics',
            'migration_notes': 'Log metrics using SageMaker logging'
        }
    }
    
    # Visualization patterns
    VISUALIZATION_PATTERNS = {
        'matplotlib': {
            'signatures': ['import matplotlib', 'plt.', 'matplotlib.pyplot'],
            'sagemaker_equivalent': 'Compatible',
            'migration_notes': 'Save plots to /opt/ml/output/ for artifacts'
        },
        'seaborn': {
            'signatures': ['import seaborn', 'sns.', 'seaborn.'],
            'sagemaker_equivalent': 'matplotlib',
            'migration_notes': 'Replace with matplotlib for lighter dependency'
        },
        'plotly': {
            'signatures': ['import plotly', 'plotly.', 'go.Figure', 'px.'],
            'sagemaker_equivalent': 'matplotlib',
            'migration_notes': 'Replace with matplotlib for static plots'
        },
        'tensorboard': {
            'signatures': ['SummaryWriter', 'tensorboard', 'torch.utils.tensorboard'],
            'sagemaker_equivalent': 'SageMaker Experiments',
            'migration_notes': 'Use SageMaker Experiments for tracking'
        }
    }
    
    def __init__(self):
        """Initialize the Pattern Detector"""
        self.detected_patterns: List[DetectedPattern] = []
    
    def analyze_directory(self, source_path: Path) -> PatternAnalysis:
        """
        Analyze patterns in a source code directory.
        
        Args:
            source_path: Path to source code directory
            
        Returns:
            PatternAnalysis with detected patterns
        """
        logger.info(f"Analyzing patterns in: {source_path}")
        
        # Reset state
        self.detected_patterns.clear()
        
        # Analyze Python files
        python_files = list(source_path.rglob("*.py"))
        for py_file in python_files:
            self._analyze_file(py_file)
        
        # Build analysis results
        return self._build_pattern_analysis()
    
    def _analyze_file(self, file_path: Path) -> None:
        """Analyze patterns in a single Python file"""
        logger.debug(f"Analyzing patterns in: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Analyze using both text patterns and AST
            self._detect_text_patterns(file_path, content)
            self._detect_ast_patterns(file_path, content)
            
        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
    
    def _detect_text_patterns(self, file_path: Path, content: str) -> None:
        """Detect patterns using text-based matching"""
        lines = content.split('\n')
        
        # Check all pattern categories
        pattern_categories = [
            ('distributed', self.DISTRIBUTED_PATTERNS),
            ('data_loading', self.DATA_LOADING_PATTERNS),
            ('model', self.MODEL_PATTERNS),
            ('visualization', self.VISUALIZATION_PATTERNS)
        ]
        
        for category, patterns in pattern_categories:
            for pattern_name, pattern_info in patterns.items():
                for signature in pattern_info['signatures']:
                    for line_num, line in enumerate(lines, 1):
                        if self._matches_signature(line, signature):
                            confidence = self._calculate_confidence(line, signature)
                            
                            detected_pattern = DetectedPattern(
                                pattern_type=category,
                                pattern_name=pattern_name,
                                file_path=str(file_path),
                                line_number=line_num,
                                confidence=confidence,
                                sagemaker_equivalent=pattern_info.get('sagemaker_equivalent'),
                                migration_notes=pattern_info.get('migration_notes')
                            )
                            
                            self.detected_patterns.append(detected_pattern)
    
    def _detect_ast_patterns(self, file_path: Path, content: str) -> None:
        """Detect patterns using AST analysis"""
        try:
            tree = ast.parse(content)
            
            # Detect class definitions that extend nn.Module
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if self._is_nn_module_subclass(node):
                        detected_pattern = DetectedPattern(
                            pattern_type='model',
                            pattern_name='custom_model',
                            file_path=str(file_path),
                            line_number=node.lineno,
                            confidence=0.9,
                            sagemaker_equivalent='Compatible',
                            migration_notes='Ensure model can be serialized'
                        )
                        self.detected_patterns.append(detected_pattern)
                    
                    if self._is_dataset_subclass(node):
                        detected_pattern = DetectedPattern(
                            pattern_type='data_loading',
                            pattern_name='custom_dataset',
                            file_path=str(file_path),
                            line_number=node.lineno,
                            confidence=0.9,
                            sagemaker_equivalent='SageMaker compatible dataset',
                            migration_notes='Ensure dataset works with S3 data paths'
                        )
                        self.detected_patterns.append(detected_pattern)
        
        except Exception as e:
            logger.debug(f"AST analysis failed for {file_path}: {e}")
    
    def _matches_signature(self, line: str, signature: str) -> bool:
        """Check if a line matches a pattern signature"""
        # Simple text matching for now - could be enhanced with regex
        return signature.lower() in line.lower()
    
    def _calculate_confidence(self, line: str, signature: str) -> float:
        """Calculate confidence score for pattern match"""
        # Simple confidence calculation based on context
        line_lower = line.lower()
        
        # Higher confidence for exact matches
        if signature.lower() == line_lower.strip():
            return 1.0
        
        # Medium confidence for function calls
        if '(' in signature and '(' in line:
            return 0.8
        
        # Lower confidence for partial matches
        return 0.6
    
    def _is_nn_module_subclass(self, node: ast.ClassDef) -> bool:
        """Check if class extends nn.Module"""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if (isinstance(base.value, ast.Name) and 
                    base.value.id == 'nn' and 
                    base.attr == 'Module'):
                    return True
            elif isinstance(base, ast.Name):
                if base.id in ['Module', 'nn.Module']:
                    return True
        return False
    
    def _is_dataset_subclass(self, node: ast.ClassDef) -> bool:
        """Check if class extends Dataset"""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr == 'Dataset':
                    return True
            elif isinstance(base, ast.Name):
                if base.id == 'Dataset':
                    return True
        return False
    
    def _build_pattern_analysis(self) -> PatternAnalysis:
        """Build pattern analysis results"""
        # Categorize detected patterns
        training_patterns = []
        data_loading_patterns = []
        model_patterns = []
        
        # Flags for specific capabilities
        distributed_training = False
        custom_metrics = False
        visualization_usage = False
        
        for pattern in self.detected_patterns:
            if pattern.pattern_type == 'distributed':
                training_patterns.append(pattern.pattern_name)
                distributed_training = True
            elif pattern.pattern_type == 'data_loading':
                data_loading_patterns.append(pattern.pattern_name)
            elif pattern.pattern_type == 'model':
                model_patterns.append(pattern.pattern_name)
                if pattern.pattern_name == 'custom_metrics':
                    custom_metrics = True
            elif pattern.pattern_type == 'visualization':
                visualization_usage = True
        
        # Remove duplicates and sort
        training_patterns = sorted(list(set(training_patterns)))
        data_loading_patterns = sorted(list(set(data_loading_patterns)))
        model_patterns = sorted(list(set(model_patterns)))
        
        return PatternAnalysis(
            training_patterns=training_patterns,
            data_loading_patterns=data_loading_patterns,
            model_patterns=model_patterns,
            distributed_training=distributed_training,
            custom_metrics=custom_metrics,
            visualization_usage=visualization_usage
        )
    
    def get_pattern_recommendations(self, pattern_name: str) -> Optional[Dict[str, str]]:
        """
        Get recommendations for a specific pattern.
        
        Args:
            pattern_name: Name of the pattern
            
        Returns:
            Dictionary with recommendation details or None if not found
        """
        # Search all pattern categories
        all_patterns = {
            **self.DISTRIBUTED_PATTERNS,
            **self.DATA_LOADING_PATTERNS,
            **self.MODEL_PATTERNS,
            **self.VISUALIZATION_PATTERNS
        }
        
        return all_patterns.get(pattern_name)
    
    def get_detected_patterns_by_type(self, pattern_type: str) -> List[DetectedPattern]:
        """
        Get detected patterns filtered by type.
        
        Args:
            pattern_type: Type of patterns to filter by
            
        Returns:
            List of detected patterns of the specified type
        """
        return [p for p in self.detected_patterns if p.pattern_type == pattern_type]
    
    def has_distributed_training(self) -> bool:
        """Check if distributed training patterns were detected"""
        return any(p.pattern_type == 'distributed' for p in self.detected_patterns)
    
    def has_custom_datasets(self) -> bool:
        """Check if custom dataset patterns were detected"""
        return any(p.pattern_name == 'custom_dataset' for p in self.detected_patterns)
    
    def has_torchvision_usage(self) -> bool:
        """Check if torchvision dataset usage was detected"""
        return any(p.pattern_name == 'torchvision_datasets' for p in self.detected_patterns)