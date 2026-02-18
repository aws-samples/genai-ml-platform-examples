"""
Code Analysis Engine for SageBridge

Main engine that orchestrates dependency analysis, pattern detection, and risk assessment.
"""

import logging
from pathlib import Path
from typing import Optional

from .dependency_analyzer import DependencyAnalyzer
from .pattern_detector import PatternDetector
from .risk_assessor import RiskAssessor
from ..models.analysis import AnalysisReport, SourceCodeInfo


logger = logging.getLogger(__name__)


class CodeAnalysisEngine:
    """
    Main engine that orchestrates dependency analysis, pattern detection, and risk assessment.
    
    Integrates all analysis components to provide comprehensive source code analysis.
    """
    
    def __init__(self):
        """Initialize the Code Analysis Engine"""
        self.dependency_analyzer = DependencyAnalyzer()
        self.pattern_detector = PatternDetector()
        self.risk_assessor = RiskAssessor()
        
        logger.info("Code Analysis Engine initialized")
    
    def analyze_source_code(self, source_path: Path) -> AnalysisReport:
        """
        Perform comprehensive analysis of source code.
        
        Args:
            source_path: Path to source code directory
            
        Returns:
            AnalysisReport with complete analysis results
            
        Raises:
            ValueError: If source path is invalid
            RuntimeError: If analysis fails
        """
        logger.info(f"Starting comprehensive source code analysis: {source_path}")
        
        # Validate input
        if not source_path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        if not source_path.is_dir():
            raise ValueError(f"Source path must be a directory: {source_path}")
        
        try:
            # Gather source code information
            source_info = self._analyze_source_structure(source_path)
            logger.info(f"Source structure analysis complete: {source_info.total_files} files")
            
            # Analyze dependencies
            dependencies = self.dependency_analyzer.analyze_directory(source_path)
            logger.info(f"Dependency analysis complete: {dependencies.total_dependencies} dependencies")
            
            # Detect patterns
            patterns = self.pattern_detector.analyze_directory(source_path)
            logger.info(f"Pattern detection complete: {len(patterns.training_patterns)} training patterns")
            
            # Assess risks
            risks = self.risk_assessor.assess_migration_risk(source_info, dependencies, patterns)
            logger.info(f"Risk assessment complete: {risks.overall_risk.value} risk level")
            
            # Generate recommendations
            recommendations = risks  # Risk assessor generates recommendations
            
            # Create analysis report
            analysis_report = AnalysisReport(
                source_info=source_info,
                dependencies=dependencies,
                patterns=patterns,
                risks=risks,
                recommendations=self.risk_assessor._generate_recommendations(),
                analysis_timestamp=self._get_timestamp()
            )
            
            logger.info("Source code analysis completed successfully")
            return analysis_report
            
        except Exception as e:
            logger.error(f"Source code analysis failed: {str(e)}")
            raise RuntimeError(f"Analysis failed: {str(e)}") from e
    
    def _analyze_source_structure(self, source_path: Path) -> SourceCodeInfo:
        """Analyze the structure of the source code directory"""
        logger.debug(f"Analyzing source structure: {source_path}")
        
        # Count different file types
        total_files = 0
        python_files = 0
        notebook_files = 0
        config_files = 0
        total_lines = 0
        
        # Recursively analyze all files
        for file_path in source_path.rglob("*"):
            if file_path.is_file():
                total_files += 1
                
                if file_path.suffix == '.py':
                    python_files += 1
                    total_lines += self._count_lines(file_path)
                elif file_path.suffix == '.ipynb':
                    notebook_files += 1
                elif file_path.name in ['requirements.txt', 'setup.py', 'pyproject.toml', 'environment.yml']:
                    config_files += 1
        
        # Estimate complexity based on structure
        estimated_complexity = self._estimate_complexity(python_files, total_lines)
        
        return SourceCodeInfo(
            path=str(source_path),
            total_files=total_files,
            python_files=python_files,
            notebook_files=notebook_files,
            config_files=config_files,
            total_lines=total_lines,
            estimated_complexity=estimated_complexity
        )
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return len(f.readlines())
        except Exception as e:
            logger.debug(f"Failed to count lines in {file_path}: {e}")
            return 0
    
    def _estimate_complexity(self, python_files: int, total_lines: int) -> str:
        """Estimate code complexity based on metrics"""
        # Simple heuristic for complexity estimation
        if python_files > 15 or total_lines > 3000:
            return "complex"
        elif python_files > 5 or total_lines > 1000:
            return "moderate"
        else:
            return "simple"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for analysis report"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def get_dependency_recommendations(self, package_name: str) -> Optional[dict]:
        """Get recommendations for a specific package"""
        return self.dependency_analyzer.get_package_recommendations(package_name)
    
    def get_pattern_recommendations(self, pattern_name: str) -> Optional[dict]:
        """Get recommendations for a specific pattern"""
        return self.pattern_detector.get_pattern_recommendations(pattern_name)
    
    def is_package_compatible(self, package_name: str) -> bool:
        """Check if a package is compatible with SageMaker"""
        return self.dependency_analyzer.is_package_compatible(package_name)