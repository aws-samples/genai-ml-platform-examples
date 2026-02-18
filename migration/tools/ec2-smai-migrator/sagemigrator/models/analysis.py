"""
Analysis models for SageBridge

Data structures for source code analysis results.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class RiskLevel(Enum):
    """Risk levels for migration assessment"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SourceCodeInfo:
    """Information about the source code being analyzed"""
    path: str
    total_files: int
    python_files: int
    notebook_files: int
    config_files: int
    total_lines: int
    estimated_complexity: str  # simple, moderate, complex


@dataclass
class DependencyAnalysis:
    """Analysis of dependencies and compatibility"""
    total_dependencies: int
    compatible_packages: List[str]
    problematic_packages: List[str]
    missing_packages: List[str]
    version_conflicts: Dict[str, str]
    sagemaker_alternatives: Dict[str, str]


@dataclass
class PatternAnalysis:
    """Analysis of code patterns and structures"""
    training_patterns: List[str]
    data_loading_patterns: List[str]
    model_patterns: List[str]
    distributed_training: bool
    custom_metrics: bool
    visualization_usage: bool


@dataclass
class RiskAssessment:
    """Risk assessment for migration"""
    overall_risk: RiskLevel
    high_risk_items: List[str]
    medium_risk_items: List[str]
    low_risk_items: List[str]
    estimated_effort_hours: int
    complexity_score: float


@dataclass
class MigrationRecommendation:
    """Recommendation for migration approach"""
    category: str
    priority: str
    description: str
    action_required: str
    estimated_effort: str


@dataclass
class AnalysisReport:
    """Complete analysis report for source code"""
    source_info: SourceCodeInfo
    dependencies: DependencyAnalysis
    patterns: PatternAnalysis
    risks: RiskAssessment
    recommendations: List[MigrationRecommendation]
    analysis_timestamp: str
    
    @classmethod
    def create_placeholder(cls, source_path: Path) -> 'AnalysisReport':
        """Create a placeholder analysis report for testing"""
        import datetime
        
        return cls(
            source_info=SourceCodeInfo(
                path=str(source_path),
                total_files=10,
                python_files=8,
                notebook_files=1,
                config_files=1,
                total_lines=1500,
                estimated_complexity="moderate"
            ),
            dependencies=DependencyAnalysis(
                total_dependencies=15,
                compatible_packages=["numpy", "pandas", "scikit-learn"],
                problematic_packages=["torchvision", "seaborn"],
                missing_packages=[],
                version_conflicts={"torch": "1.9.0 -> 2.0.0"},
                sagemaker_alternatives={"torchvision": "manual_download", "seaborn": "matplotlib"}
            ),
            patterns=PatternAnalysis(
                training_patterns=["pytorch_training", "custom_dataset"],
                data_loading_patterns=["local_files", "csv_loading"],
                model_patterns=["sequential_model", "custom_loss"],
                distributed_training=False,
                custom_metrics=True,
                visualization_usage=True
            ),
            risks=RiskAssessment(
                overall_risk=RiskLevel.MEDIUM,
                high_risk_items=["torchvision dependency"],
                medium_risk_items=["custom metrics", "visualization code"],
                low_risk_items=["basic pytorch patterns"],
                estimated_effort_hours=16,
                complexity_score=0.6
            ),
            recommendations=[
                MigrationRecommendation(
                    category="dependencies",
                    priority="high",
                    description="Replace torchvision with manual data download",
                    action_required="Implement custom data loading",
                    estimated_effort="4 hours"
                )
            ],
            analysis_timestamp=datetime.datetime.now().isoformat()
        )
    
    def save_to_file(self, file_path: Path) -> None:
        """Save analysis report to JSON file"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(asdict(self), f, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, file_path: Path) -> 'AnalysisReport':
        """Load analysis report from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of analysis results"""
        return {
            "source_path": self.source_info.path,
            "total_files": self.source_info.total_files,
            "overall_risk": self.risks.overall_risk.value,
            "problematic_packages": len(self.dependencies.problematic_packages),
            "estimated_effort_hours": self.risks.estimated_effort_hours,
            "high_risk_items": len(self.risks.high_risk_items),
            "recommendations": len(self.recommendations)
        }