"""
Code Analysis Engine for SageBridge

Components for analyzing source code to identify patterns, dependencies, 
and potential migration challenges.
"""

from .dependency_analyzer import DependencyAnalyzer
from .pattern_detector import PatternDetector
from .risk_assessor import RiskAssessor
from .code_analysis_engine import CodeAnalysisEngine

__all__ = [
    'DependencyAnalyzer',
    'PatternDetector', 
    'RiskAssessor',
    'CodeAnalysisEngine'
]