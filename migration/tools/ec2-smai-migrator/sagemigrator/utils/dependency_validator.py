"""
Dependency validation utilities for SageMigrator
"""

import sys
import subprocess
from typing import List, Tuple, Dict, Optional
import importlib.util


class DependencyValidator:
    """Validates and manages dependencies for SageMaker pipeline generation and execution"""
    
    # Core dependencies required for pipeline generation
    GENERATION_DEPENDENCIES = [
        ('boto3', '1.26.0'),
        ('click', '8.0.0'),
        ('rich', '13.0.0'),
        ('pyyaml', '6.0'),
    ]
    
    # Runtime dependencies required for pipeline execution
    RUNTIME_DEPENDENCIES = [
        ('sagemaker', '2.190.0'),
        ('boto3', '1.26.0'),
        ('pandas', '1.5.0'),
        ('numpy', '1.21.0'),
        ('sklearn', '1.1.0'),  # Note: package name is scikit-learn, import name is sklearn
    ]
    
    # Optional ML dependencies
    OPTIONAL_ML_DEPENDENCIES = [
        ('torch', '1.12.0'),
        ('torchvision', '0.13.0'),
    ]
    
    @staticmethod
    def check_package_availability(package_name: str) -> bool:
        """Check if a package is available for import"""
        try:
            spec = importlib.util.find_spec(package_name)
            return spec is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            return False
    
    @staticmethod
    def get_package_version(package_name: str) -> Optional[str]:
        """Get the version of an installed package"""
        try:
            module = __import__(package_name)
            return getattr(module, '__version__', None)
        except ImportError:
            return None
    
    @classmethod
    def validate_generation_dependencies(cls) -> Tuple[bool, List[str], List[str]]:
        """
        Validate dependencies required for pipeline generation
        
        Returns:
            Tuple of (all_available, missing_packages, warnings)
        """
        missing_packages = []
        warnings = []
        
        for package, min_version in cls.GENERATION_DEPENDENCIES:
            if not cls.check_package_availability(package):
                missing_packages.append(f"{package}>={min_version}")
            else:
                current_version = cls.get_package_version(package)
                if current_version:
                    # Simple version comparison (works for most cases)
                    if cls._compare_versions(current_version, min_version) < 0:
                        warnings.append(f"{package} version {current_version} is below recommended {min_version}")
        
        return len(missing_packages) == 0, missing_packages, warnings
    
    @classmethod
    def validate_runtime_dependencies(cls) -> Tuple[bool, List[str], List[str]]:
        """
        Validate dependencies required for pipeline execution
        
        Returns:
            Tuple of (all_available, missing_packages, warnings)
        """
        missing_packages = []
        warnings = []
        
        for package, min_version in cls.RUNTIME_DEPENDENCIES:
            if not cls.check_package_availability(package):
                missing_packages.append(f"{package}>={min_version}")
            else:
                current_version = cls.get_package_version(package)
                if current_version and package == 'sagemaker':
                    # Special handling for SageMaker SDK version compatibility
                    major_version = int(current_version.split('.')[0])
                    if major_version >= 3:
                        warnings.append(
                            f"SageMaker SDK v{current_version} detected. "
                            f"Generated pipelines are optimized for v2.x. "
                            f"Consider: pip install 'sagemaker>=2.190.0,<3.0.0' --force-reinstall"
                        )
        
        return len(missing_packages) == 0, missing_packages, warnings
    
    @classmethod
    def validate_ml_dependencies(cls, processor_type: str = 'pytorch') -> Tuple[bool, List[str], List[str]]:
        """
        Validate ML framework dependencies based on processor type
        
        Args:
            processor_type: Type of processor ('pytorch' or 'sklearn')
            
        Returns:
            Tuple of (all_available, missing_packages, warnings)
        """
        missing_packages = []
        warnings = []
        
        if processor_type == 'pytorch':
            for package, min_version in cls.OPTIONAL_ML_DEPENDENCIES:
                if not cls.check_package_availability(package):
                    missing_packages.append(f"{package}>={min_version}")
        
        return len(missing_packages) == 0, missing_packages, warnings
    
    @staticmethod
    def _compare_versions(version1: str, version2: str) -> int:
        """
        Simple version comparison
        
        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        def normalize_version(v):
            return [int(x) for x in v.split('.')]
        
        try:
            v1_parts = normalize_version(version1)
            v2_parts = normalize_version(version2)
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 < v2:
                    return -1
                elif v1 > v2:
                    return 1
            return 0
        except (ValueError, AttributeError):
            return 0  # Assume equal if can't parse
    
    @classmethod
    def generate_installation_instructions(cls, missing_packages: List[str], context: str = "pipeline") -> str:
        """
        Generate installation instructions for missing packages
        
        Args:
            missing_packages: List of missing package specifications
            context: Context for the instructions ('pipeline', 'generation', 'runtime')
            
        Returns:
            Formatted installation instructions
        """
        if not missing_packages:
            return ""
        
        instructions = [
            f"❌ Missing required dependencies for {context}:",
        ]
        
        for pkg in missing_packages:
            instructions.append(f"   - {pkg}")
        
        instructions.extend([
            "",
            "📦 Install missing packages:",
            f"   pip install {' '.join(missing_packages)}",
            "",
            "💡 Or install from requirements.txt:",
            "   pip install -r requirements.txt",
        ])
        
        # Add special instructions for SageMaker SDK
        if any('sagemaker' in pkg for pkg in missing_packages):
            instructions.extend([
                "",
                "🔧 For SageMaker SDK v2.x compatibility:",
                "   pip install 'sagemaker>=2.190.0,<3.0.0' --force-reinstall",
            ])
        
        return "\n".join(instructions)
    
    @classmethod
    def validate_environment(cls, context: str = "runtime", processor_type: str = "pytorch") -> Dict[str, any]:
        """
        Comprehensive environment validation
        
        Args:
            context: Validation context ('generation', 'runtime', 'all')
            processor_type: ML processor type for framework validation
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'missing_packages': [],
            'warnings': [],
            'instructions': ""
        }
        
        if context in ['generation', 'all']:
            gen_valid, gen_missing, gen_warnings = cls.validate_generation_dependencies()
            if not gen_valid:
                results['valid'] = False
                results['missing_packages'].extend(gen_missing)
            results['warnings'].extend(gen_warnings)
        
        if context in ['runtime', 'all']:
            runtime_valid, runtime_missing, runtime_warnings = cls.validate_runtime_dependencies()
            if not runtime_valid:
                results['valid'] = False
                results['missing_packages'].extend(runtime_missing)
            results['warnings'].extend(runtime_warnings)
            
            # Check ML dependencies
            ml_valid, ml_missing, ml_warnings = cls.validate_ml_dependencies(processor_type)
            if not ml_valid:
                results['warnings'].extend([f"Optional ML dependency missing: {pkg}" for pkg in ml_missing])
            results['warnings'].extend(ml_warnings)
        
        # Generate installation instructions
        if results['missing_packages']:
            results['instructions'] = cls.generate_installation_instructions(
                results['missing_packages'], context
            )
        
        return results


def validate_pipeline_environment() -> bool:
    """
    Quick validation for pipeline execution environment
    
    Returns:
        True if environment is valid, False otherwise
    """
    validator = DependencyValidator()
    results = validator.validate_environment('runtime')
    
    if not results['valid']:
        print(results['instructions'])
        return False
    
    if results['warnings']:
        print("⚠️  Warnings:")
        for warning in results['warnings']:
            print(f"   - {warning}")
        print()
    
    return True


def validate_generation_environment() -> bool:
    """
    Quick validation for pipeline generation environment
    
    Returns:
        True if environment is valid, False otherwise
    """
    validator = DependencyValidator()
    results = validator.validate_environment('generation')
    
    if not results['valid']:
        print(results['instructions'])
        return False
    
    if results['warnings']:
        print("⚠️  Warnings:")
        for warning in results['warnings']:
            print(f"   - {warning}")
        print()
    
    return True