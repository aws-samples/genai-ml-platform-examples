"""
Dependency Analyzer for SageBridge

Analyzes Python dependencies and identifies SageMaker compatibility issues.
"""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass

from ..models.analysis import DependencyAnalysis


logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Information about a Python package"""
    name: str
    version: Optional[str] = None
    import_name: Optional[str] = None
    is_standard_library: bool = False


class DependencyAnalyzer:
    """
    Analyzes Python dependencies and identifies SageMaker compatibility issues.
    
    Parses requirements.txt, imports, and package usage to build compatibility matrix
    for SageMaker SDK v3 and identify problematic packages.
    """
    
    # SageMaker-incompatible packages and their alternatives
    PROBLEMATIC_PACKAGES = {
        'torchvision': {
            'reason': 'Not available in SageMaker containers',
            'alternative': 'manual_download',
            'description': 'Use manual data download and preprocessing'
        },
        'seaborn': {
            'reason': 'Heavy dependency, visualization not needed in training',
            'alternative': 'matplotlib',
            'description': 'Replace with matplotlib for basic plotting'
        },
        'plotly': {
            'reason': 'Interactive plotting not supported in SageMaker training',
            'alternative': 'matplotlib',
            'description': 'Use matplotlib for static plots'
        },
        'bokeh': {
            'reason': 'Interactive plotting not supported in SageMaker training',
            'alternative': 'matplotlib',
            'description': 'Use matplotlib for static plots'
        },
        'opencv-python': {
            'reason': 'May have version conflicts in SageMaker containers',
            'alternative': 'opencv-python-headless',
            'description': 'Use headless version for server environments'
        },
        'tensorflow-gpu': {
            'reason': 'Use tensorflow with automatic GPU detection',
            'alternative': 'tensorflow',
            'description': 'SageMaker handles GPU allocation automatically'
        },
        'torch-audio': {
            'reason': 'May not be available in all SageMaker containers',
            'alternative': 'torchaudio',
            'description': 'Use official torchaudio package'
        }
    }
    
    # SageMaker-compatible packages
    COMPATIBLE_PACKAGES = {
        'torch', 'tensorflow', 'scikit-learn', 'numpy', 'pandas', 'matplotlib',
        'boto3', 'sagemaker', 'transformers', 'datasets', 'accelerate',
        'pytorch-lightning', 'xgboost', 'lightgbm', 'catboost',
        'opencv-python-headless', 'pillow', 'requests', 'urllib3',
        'joblib', 'cloudpickle', 'dill', 'psutil', 'tqdm'
    }
    
    # Standard library modules (Python 3.8+)
    STANDARD_LIBRARY = {
        'os', 'sys', 'json', 'csv', 'pickle', 'gzip', 'tarfile', 'zipfile',
        'urllib', 'http', 'logging', 'datetime', 'time', 'random', 'math',
        'statistics', 'collections', 'itertools', 'functools', 'operator',
        'pathlib', 'glob', 'shutil', 'tempfile', 'subprocess', 'threading',
        'multiprocessing', 'concurrent', 'asyncio', 'socket', 'ssl',
        'hashlib', 'hmac', 'base64', 'binascii', 'struct', 'array',
        'copy', 'deepcopy', 'weakref', 'gc', 'inspect', 'types',
        'importlib', 'pkgutil', 'warnings', 'traceback', 'pdb',
        'unittest', 'doctest', 'argparse', 'configparser', 'io',
        'contextlib', 'abc', 'typing', 'dataclasses', 'enum'
    }
    
    def __init__(self):
        """Initialize the Dependency Analyzer"""
        self.found_imports: Set[str] = set()
        self.requirements_packages: Dict[str, str] = {}
        self.import_to_package_map: Dict[str, str] = {}
        
        # Build import to package mapping
        self._build_import_mapping()
    
    def _build_import_mapping(self) -> None:
        """Build mapping from import names to package names"""
        # Common import name to package name mappings
        self.import_to_package_map.update({
            'cv2': 'opencv-python',
            'PIL': 'pillow',
            'sklearn': 'scikit-learn',
            'torch': 'torch',
            'torchvision': 'torchvision',
            'tensorflow': 'tensorflow',
            'tf': 'tensorflow',
            'numpy': 'numpy',
            'np': 'numpy',
            'pandas': 'pandas',
            'pd': 'pandas',
            'matplotlib': 'matplotlib',
            'plt': 'matplotlib',
            'seaborn': 'seaborn',
            'sns': 'seaborn',
            'plotly': 'plotly',
            'bokeh': 'bokeh',
            'requests': 'requests',
            'boto3': 'boto3',
            'sagemaker': 'sagemaker',
            'transformers': 'transformers',
            'datasets': 'datasets',
            'accelerate': 'accelerate',
            'lightning': 'pytorch-lightning',
            'xgboost': 'xgboost',
            'lightgbm': 'lightgbm',
            'catboost': 'catboost'
        })
    
    def analyze_directory(self, source_path: Path) -> DependencyAnalysis:
        """
        Analyze dependencies in a source code directory.
        
        Args:
            source_path: Path to source code directory
            
        Returns:
            DependencyAnalysis with compatibility assessment
        """
        logger.info(f"Analyzing dependencies in: {source_path}")
        
        # Reset state
        self.found_imports.clear()
        self.requirements_packages.clear()
        
        # Parse requirements.txt files
        self._parse_requirements_files(source_path)
        
        # Parse Python files for imports
        self._parse_python_imports(source_path)
        
        # Build analysis results
        return self._build_dependency_analysis()
    
    def _parse_requirements_files(self, source_path: Path) -> None:
        """Parse requirements.txt files to extract package dependencies"""
        requirements_files = list(source_path.rglob("requirements*.txt"))
        
        for req_file in requirements_files:
            logger.debug(f"Parsing requirements file: {req_file}")
            
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            package_info = self._parse_requirement_line(line)
                            if package_info:
                                self.requirements_packages[package_info.name] = package_info.version or ""
            except Exception as e:
                logger.warning(f"Failed to parse {req_file}: {e}")
    
    def _parse_requirement_line(self, line: str) -> Optional[PackageInfo]:
        """Parse a single requirement line"""
        # Remove comments
        line = line.split('#')[0].strip()
        if not line:
            return None
        
        # Handle different requirement formats
        # package==1.0.0, package>=1.0.0, package~=1.0.0, etc.
        match = re.match(r'^([a-zA-Z0-9_-]+)([><=!~]+)?([0-9.]+.*)?', line)
        if match:
            package_name = match.group(1).lower()
            version = match.group(3) if match.group(3) else None
            return PackageInfo(name=package_name, version=version)
        
        return None
    
    def _parse_python_imports(self, source_path: Path) -> None:
        """Parse Python files to extract import statements"""
        python_files = list(source_path.rglob("*.py"))
        
        for py_file in python_files:
            logger.debug(f"Parsing imports in: {py_file}")
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to extract imports
                tree = ast.parse(content)
                imports = self._extract_imports_from_ast(tree)
                self.found_imports.update(imports)
                
            except Exception as e:
                logger.warning(f"Failed to parse {py_file}: {e}")
    
    def _extract_imports_from_ast(self, tree: ast.AST) -> Set[str]:
        """Extract import names from AST"""
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        
        return imports
    
    def _build_dependency_analysis(self) -> DependencyAnalysis:
        """Build dependency analysis results"""
        # Map imports to package names
        all_packages = set()
        
        # Add packages from requirements.txt
        all_packages.update(self.requirements_packages.keys())
        
        # Add packages inferred from imports
        for import_name in self.found_imports:
            if import_name in self.import_to_package_map:
                all_packages.add(self.import_to_package_map[import_name])
            elif import_name not in self.STANDARD_LIBRARY:
                # Assume import name is package name if not in standard library
                all_packages.add(import_name)
        
        # Categorize packages
        compatible_packages = []
        problematic_packages = []
        missing_packages = []
        version_conflicts = {}
        sagemaker_alternatives = {}
        
        for package in all_packages:
            if package in self.PROBLEMATIC_PACKAGES:
                problematic_packages.append(package)
                alt_info = self.PROBLEMATIC_PACKAGES[package]
                sagemaker_alternatives[package] = alt_info['alternative']
            elif package in self.COMPATIBLE_PACKAGES:
                compatible_packages.append(package)
            else:
                # Check if package is in requirements but not in imports (potentially missing)
                if package in self.requirements_packages and package not in self._get_package_names_from_imports():
                    missing_packages.append(package)
                else:
                    compatible_packages.append(package)  # Assume compatible if unknown
        
        # Check for version conflicts (simplified - would need more sophisticated logic)
        for package, version in self.requirements_packages.items():
            if package == 'torch' and version and version.startswith('1.'):
                version_conflicts[package] = f"{version} -> 2.0.0+ (recommended for SageMaker)"
        
        return DependencyAnalysis(
            total_dependencies=len(all_packages),
            compatible_packages=sorted(compatible_packages),
            problematic_packages=sorted(problematic_packages),
            missing_packages=sorted(missing_packages),
            version_conflicts=version_conflicts,
            sagemaker_alternatives=sagemaker_alternatives
        )
    
    def _get_package_names_from_imports(self) -> Set[str]:
        """Get package names inferred from imports"""
        package_names = set()
        for import_name in self.found_imports:
            if import_name in self.import_to_package_map:
                package_names.add(self.import_to_package_map[import_name])
            elif import_name not in self.STANDARD_LIBRARY:
                package_names.add(import_name)
        return package_names
    
    def get_package_recommendations(self, package_name: str) -> Optional[Dict[str, str]]:
        """
        Get recommendations for a specific package.
        
        Args:
            package_name: Name of the package
            
        Returns:
            Dictionary with recommendation details or None if no issues
        """
        if package_name in self.PROBLEMATIC_PACKAGES:
            return self.PROBLEMATIC_PACKAGES[package_name]
        return None
    
    def is_package_compatible(self, package_name: str) -> bool:
        """
        Check if a package is compatible with SageMaker.
        
        Args:
            package_name: Name of the package
            
        Returns:
            True if compatible, False otherwise
        """
        return (package_name in self.COMPATIBLE_PACKAGES and 
                package_name not in self.PROBLEMATIC_PACKAGES)