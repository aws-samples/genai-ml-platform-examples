"""
Risk Assessor for SageBridge

Evaluates migration complexity and assigns risk scores based on detected patterns and dependencies.
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

from ..models.analysis import (
    RiskLevel, RiskAssessment, MigrationRecommendation,
    DependencyAnalysis, PatternAnalysis, SourceCodeInfo
)


logger = logging.getLogger(__name__)


@dataclass
class RiskFactor:
    """Individual risk factor with score and description"""
    name: str
    score: float  # 0.0 to 1.0
    level: RiskLevel
    description: str
    impact: str
    mitigation: str


class RiskAssessor:
    """
    Evaluates migration complexity based on detected patterns and dependencies.
    
    Assigns risk scores and generates recommendations with migration priority ordering.
    """
    
    # Risk scoring weights
    DEPENDENCY_WEIGHT = 0.3
    PATTERN_WEIGHT = 0.4
    COMPLEXITY_WEIGHT = 0.3
    
    # Risk thresholds
    LOW_RISK_THRESHOLD = 0.3
    MEDIUM_RISK_THRESHOLD = 0.6
    HIGH_RISK_THRESHOLD = 0.8
    
    def __init__(self):
        """Initialize the Risk Assessor"""
        self.risk_factors: List[RiskFactor] = []
    
    def assess_migration_risk(
        self,
        source_info: SourceCodeInfo,
        dependencies: DependencyAnalysis,
        patterns: PatternAnalysis
    ) -> RiskAssessment:
        """
        Assess migration risk based on analysis results.
        
        Args:
            source_info: Information about source code structure
            dependencies: Dependency analysis results
            patterns: Pattern analysis results
            
        Returns:
            RiskAssessment with overall risk and recommendations
        """
        logger.info("Assessing migration risk")
        
        # Reset state
        self.risk_factors.clear()
        
        # Evaluate different risk categories
        dependency_risk = self._assess_dependency_risk(dependencies)
        pattern_risk = self._assess_pattern_risk(patterns)
        complexity_risk = self._assess_complexity_risk(source_info)
        
        # Calculate overall risk score
        overall_score = (
            dependency_risk * self.DEPENDENCY_WEIGHT +
            pattern_risk * self.PATTERN_WEIGHT +
            complexity_risk * self.COMPLEXITY_WEIGHT
        )
        
        # Determine risk level
        overall_risk = self._score_to_risk_level(overall_score)
        
        # Categorize risk items
        high_risk_items, medium_risk_items, low_risk_items = self._categorize_risk_items()
        
        # Estimate effort
        estimated_effort_hours = self._estimate_effort(overall_score, source_info)
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        return RiskAssessment(
            overall_risk=overall_risk,
            high_risk_items=high_risk_items,
            medium_risk_items=medium_risk_items,
            low_risk_items=low_risk_items,
            estimated_effort_hours=estimated_effort_hours,
            complexity_score=overall_score
        )
    
    def _assess_dependency_risk(self, dependencies: DependencyAnalysis) -> float:
        """Assess risk from dependency analysis"""
        risk_score = 0.0
        
        # Problematic packages contribute to risk
        if dependencies.problematic_packages:
            for package in dependencies.problematic_packages:
                if package in ['torchvision', 'seaborn']:
                    # High impact packages
                    risk_factor = RiskFactor(
                        name=f"Problematic dependency: {package}",
                        score=0.8,
                        level=RiskLevel.HIGH,
                        description=f"Package {package} is not compatible with SageMaker",
                        impact="May cause training job failures",
                        mitigation=f"Replace with {dependencies.sagemaker_alternatives.get(package, 'alternative')}"
                    )
                    risk_score += 0.2
                else:
                    # Medium impact packages
                    risk_factor = RiskFactor(
                        name=f"Problematic dependency: {package}",
                        score=0.6,
                        level=RiskLevel.MEDIUM,
                        description=f"Package {package} may have compatibility issues",
                        impact="May require container customization",
                        mitigation="Consider alternative or custom container"
                    )
                    risk_score += 0.1
                
                self.risk_factors.append(risk_factor)
        
        # Version conflicts add risk
        if dependencies.version_conflicts:
            for package, conflict in dependencies.version_conflicts.items():
                risk_factor = RiskFactor(
                    name=f"Version conflict: {package}",
                    score=0.5,
                    level=RiskLevel.MEDIUM,
                    description=f"Version conflict detected: {conflict}",
                    impact="May cause compatibility issues",
                    mitigation="Update to recommended version"
                )
                self.risk_factors.append(risk_factor)
                risk_score += 0.1
        
        # Missing packages (lower risk)
        if dependencies.missing_packages:
            risk_factor = RiskFactor(
                name="Missing packages detected",
                score=0.3,
                level=RiskLevel.LOW,
                description=f"{len(dependencies.missing_packages)} packages in requirements but not used",
                impact="Minimal - may increase container size",
                mitigation="Clean up requirements.txt"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.05
        
        return min(risk_score, 1.0)
    
    def _assess_pattern_risk(self, patterns: PatternAnalysis) -> float:
        """Assess risk from pattern analysis"""
        risk_score = 0.0
        
        # Distributed training patterns
        if patterns.distributed_training:
            risk_factor = RiskFactor(
                name="Distributed training detected",
                score=0.7,
                level=RiskLevel.HIGH,
                description="Code uses distributed training patterns",
                impact="Requires SageMaker distributed training configuration",
                mitigation="Configure distribution in SageMaker estimator"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.3
        
        # Data loading patterns
        if 'torchvision_datasets' in patterns.data_loading_patterns:
            risk_factor = RiskFactor(
                name="Torchvision datasets usage",
                score=0.8,
                level=RiskLevel.HIGH,
                description="Code uses torchvision datasets",
                impact="Will fail in SageMaker containers",
                mitigation="Implement manual data download"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.4
        
        if 'local_files' in patterns.data_loading_patterns:
            risk_factor = RiskFactor(
                name="Local file access",
                score=0.6,
                level=RiskLevel.MEDIUM,
                description="Code accesses local files directly",
                impact="Needs S3 integration for SageMaker",
                mitigation="Use S3 input channels"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.2
        
        # Visualization usage
        if patterns.visualization_usage:
            risk_factor = RiskFactor(
                name="Visualization code detected",
                score=0.4,
                level=RiskLevel.MEDIUM,
                description="Code includes visualization/plotting",
                impact="May not work in headless SageMaker environment",
                mitigation="Save plots to output directory or remove"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.1
        
        # Custom metrics (lower risk)
        if patterns.custom_metrics:
            risk_factor = RiskFactor(
                name="Custom metrics detected",
                score=0.3,
                level=RiskLevel.LOW,
                description="Code uses custom evaluation metrics",
                impact="May need integration with SageMaker logging",
                mitigation="Use SageMaker metrics logging"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.05
        
        return min(risk_score, 1.0)
    
    def _assess_complexity_risk(self, source_info: SourceCodeInfo) -> float:
        """Assess risk from code complexity"""
        risk_score = 0.0
        
        # File count risk
        if source_info.python_files > 20:
            risk_factor = RiskFactor(
                name="Large codebase",
                score=0.6,
                level=RiskLevel.MEDIUM,
                description=f"Large number of Python files ({source_info.python_files})",
                impact="More complex migration with multiple components",
                mitigation="Consider incremental migration approach"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.2
        elif source_info.python_files > 10:
            risk_score += 0.1
        
        # Lines of code risk
        if source_info.total_lines > 5000:
            risk_factor = RiskFactor(
                name="Large codebase (lines)",
                score=0.5,
                level=RiskLevel.MEDIUM,
                description=f"Large codebase ({source_info.total_lines} lines)",
                impact="More time needed for analysis and testing",
                mitigation="Thorough testing and validation"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.15
        elif source_info.total_lines > 2000:
            risk_score += 0.1
        
        # Complexity assessment
        if source_info.estimated_complexity == "complex":
            risk_factor = RiskFactor(
                name="High code complexity",
                score=0.7,
                level=RiskLevel.HIGH,
                description="Code structure appears complex",
                impact="May require significant refactoring",
                mitigation="Plan for additional development time"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.3
        elif source_info.estimated_complexity == "moderate":
            risk_score += 0.1
        
        # Notebook files (additional complexity)
        if source_info.notebook_files > 0:
            risk_factor = RiskFactor(
                name="Jupyter notebooks detected",
                score=0.4,
                level=RiskLevel.MEDIUM,
                description=f"Contains {source_info.notebook_files} notebook files",
                impact="Notebooks need conversion to Python scripts",
                mitigation="Convert notebooks to training scripts"
            )
            self.risk_factors.append(risk_factor)
            risk_score += 0.1
        
        return min(risk_score, 1.0)
    
    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        if score >= self.HIGH_RISK_THRESHOLD:
            return RiskLevel.CRITICAL if score >= 0.9 else RiskLevel.HIGH
        elif score >= self.MEDIUM_RISK_THRESHOLD:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _categorize_risk_items(self) -> Tuple[List[str], List[str], List[str]]:
        """Categorize risk factors by level"""
        high_risk_items = []
        medium_risk_items = []
        low_risk_items = []
        
        for factor in self.risk_factors:
            if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                high_risk_items.append(factor.name)
            elif factor.level == RiskLevel.MEDIUM:
                medium_risk_items.append(factor.name)
            else:
                low_risk_items.append(factor.name)
        
        return high_risk_items, medium_risk_items, low_risk_items
    
    def _estimate_effort(self, risk_score: float, source_info: SourceCodeInfo) -> int:
        """Estimate effort in hours based on risk and complexity"""
        base_hours = 8  # Minimum effort for any migration
        
        # Risk-based multiplier
        risk_multiplier = 1 + (risk_score * 2)  # 1x to 3x based on risk
        
        # Size-based hours
        size_hours = 0
        if source_info.python_files > 10:
            size_hours += (source_info.python_files - 10) * 2
        
        if source_info.total_lines > 1000:
            size_hours += (source_info.total_lines - 1000) // 500
        
        # Complexity-based hours
        complexity_hours = 0
        if source_info.estimated_complexity == "complex":
            complexity_hours = 16
        elif source_info.estimated_complexity == "moderate":
            complexity_hours = 8
        
        total_hours = int((base_hours + size_hours + complexity_hours) * risk_multiplier)
        
        # Cap at reasonable maximum
        return min(total_hours, 120)
    
    def _generate_recommendations(self) -> List[MigrationRecommendation]:
        """Generate migration recommendations based on risk factors"""
        recommendations = []
        
        # Sort risk factors by score (highest first)
        sorted_factors = sorted(self.risk_factors, key=lambda x: x.score, reverse=True)
        
        for i, factor in enumerate(sorted_factors[:10]):  # Top 10 risks
            priority = "high" if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else \
                      "medium" if factor.level == RiskLevel.MEDIUM else "low"
            
            # Estimate effort for this specific issue
            effort_map = {
                RiskLevel.CRITICAL: "8-16 hours",
                RiskLevel.HIGH: "4-8 hours", 
                RiskLevel.MEDIUM: "2-4 hours",
                RiskLevel.LOW: "1-2 hours"
            }
            
            recommendation = MigrationRecommendation(
                category=self._get_category_from_factor_name(factor.name),
                priority=priority,
                description=factor.description,
                action_required=factor.mitigation,
                estimated_effort=effort_map[factor.level]
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_category_from_factor_name(self, factor_name: str) -> str:
        """Determine category from risk factor name"""
        if "dependency" in factor_name.lower():
            return "dependencies"
        elif "distributed" in factor_name.lower():
            return "distributed_training"
        elif "data" in factor_name.lower() or "file" in factor_name.lower():
            return "data_loading"
        elif "visualization" in factor_name.lower():
            return "visualization"
        elif "complexity" in factor_name.lower() or "codebase" in factor_name.lower():
            return "code_structure"
        elif "notebook" in factor_name.lower():
            return "notebooks"
        else:
            return "general"
    
    def get_risk_factors(self) -> List[RiskFactor]:
        """Get all identified risk factors"""
        return self.risk_factors.copy()
    
    def get_high_risk_factors(self) -> List[RiskFactor]:
        """Get only high and critical risk factors"""
        return [f for f in self.risk_factors if f.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
    
    def get_migration_priority_order(self) -> List[str]:
        """Get recommended order for addressing migration issues"""
        # Sort by risk level and score
        sorted_factors = sorted(
            self.risk_factors,
            key=lambda x: (x.level.value, x.score),
            reverse=True
        )
        
        return [f.name for f in sorted_factors]