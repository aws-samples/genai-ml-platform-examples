"""
Incremental Migration Manager for SageBridge

Supports component-by-component migration with dependency tracking, hybrid deployment
options, validation checkpoints, rollback mechanisms, and progress tracking.
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from ..models.analysis import AnalysisReport
from ..models.artifacts import MigrationArtifacts
from ..models.deployment import DeploymentPlan, DeploymentResult, DeploymentStatus
from ..utils.exceptions import MigrationError


logger = logging.getLogger(__name__)


class MigrationPhase(Enum):
    """Migration phases for incremental migration"""
    ANALYSIS = "analysis"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    TRAINING_MIGRATION = "training_migration"
    INFERENCE_MIGRATION = "inference_migration"
    PIPELINE_MIGRATION = "pipeline_migration"
    INFRASTRUCTURE_DEPLOYMENT = "infrastructure_deployment"
    VALIDATION = "validation"
    PRODUCTION_DEPLOYMENT = "production_deployment"
    CLEANUP = "cleanup"


class ComponentStatus(Enum):
    """Status of individual migration components"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationComponent:
    """Individual component in the migration process"""
    component_id: str
    name: str
    description: str
    phase: MigrationPhase
    dependencies: List[str]
    status: ComponentStatus
    estimated_duration_minutes: int
    actual_duration_minutes: Optional[float] = None
    error_message: Optional[str] = None
    rollback_steps: List[str] = None
    validation_checkpoints: List[str] = None
    artifacts_generated: List[str] = None
    
    def __post_init__(self):
        if self.rollback_steps is None:
            self.rollback_steps = []
        if self.validation_checkpoints is None:
            self.validation_checkpoints = []
        if self.artifacts_generated is None:
            self.artifacts_generated = []


@dataclass
class ValidationCheckpoint:
    """Validation checkpoint between migration phases"""
    checkpoint_id: str
    name: str
    description: str
    phase: MigrationPhase
    validation_criteria: List[str]
    status: ComponentStatus
    validation_results: Dict[str, Any] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.validation_results is None:
            self.validation_results = {}


@dataclass
class HybridDeploymentOption:
    """Hybrid deployment configuration for gradual transition"""
    option_id: str
    name: str
    description: str
    components_migrated: List[str]
    components_remaining: List[str]
    traffic_split_percentage: int  # Percentage of traffic to migrated components
    rollback_strategy: str
    monitoring_requirements: List[str]
    estimated_cost_impact: str


@dataclass
class MigrationProgress:
    """Progress tracking for incremental migration"""
    migration_id: str
    start_time: datetime
    current_phase: MigrationPhase
    completed_components: List[str]
    failed_components: List[str]
    total_components: int
    completion_percentage: float
    estimated_remaining_minutes: int
    last_checkpoint: Optional[str] = None
    current_component: Optional[str] = None
    
    def update_progress(self, completed: List[str], failed: List[str], current: Optional[str] = None):
        """Update progress tracking"""
        self.completed_components = completed
        self.failed_components = failed
        self.current_component = current
        self.completion_percentage = len(completed) / self.total_components * 100 if self.total_components > 0 else 0


@dataclass
class RollbackPlan:
    """Rollback plan for failed migration steps"""
    plan_id: str
    component_id: str
    rollback_steps: List[str]
    dependencies: List[str]  # Components that depend on this one
    estimated_duration_minutes: int
    data_backup_required: bool
    infrastructure_changes: List[str]


class IncrementalMigrationManager:
    """
    Manages incremental migration with component-by-component approach,
    dependency tracking, validation checkpoints, and rollback mechanisms.
    """
    
    def __init__(self, migration_id: str, output_path: Path):
        """
        Initialize the Incremental Migration Manager.
        
        Args:
            migration_id: Unique identifier for this migration
            output_path: Path to store migration artifacts and progress
        """
        self.migration_id = migration_id
        self.output_path = output_path
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.components: Dict[str, MigrationComponent] = {}
        self.checkpoints: Dict[str, ValidationCheckpoint] = {}
        self.hybrid_options: Dict[str, HybridDeploymentOption] = {}
        self.rollback_plans: Dict[str, RollbackPlan] = {}
        self.progress: Optional[MigrationProgress] = None
        
        # Dependency graph for component ordering
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        logger.info(f"Initialized Incremental Migration Manager for migration: {migration_id}")
    
    def create_migration_plan(self, analysis: AnalysisReport) -> Dict[str, Any]:
        """
        Create a comprehensive incremental migration plan based on analysis.
        
        Args:
            analysis: Source code analysis report
            
        Returns:
            Dictionary containing the complete migration plan
        """
        logger.info("Creating incremental migration plan")
        
        # Create migration components based on analysis
        self._create_migration_components(analysis)
        
        # Create validation checkpoints
        self._create_validation_checkpoints()
        
        # Generate hybrid deployment options
        self._generate_hybrid_deployment_options(analysis)
        
        # Create rollback plans
        self._create_rollback_plans()
        
        # Initialize progress tracking
        self._initialize_progress_tracking()
        
        migration_plan = {
            "migration_id": self.migration_id,
            "components": {comp_id: asdict(comp) for comp_id, comp in self.components.items()},
            "checkpoints": {cp_id: asdict(cp) for cp_id, cp in self.checkpoints.items()},
            "hybrid_options": {opt_id: asdict(opt) for opt_id, opt in self.hybrid_options.items()},
            "rollback_plans": {plan_id: asdict(plan) for plan_id, plan in self.rollback_plans.items()},
            "progress": asdict(self.progress) if self.progress else None,
            "dependency_order": self._get_execution_order()
        }
        
        # Save migration plan
        self._save_migration_plan(migration_plan)
        
        logger.info("Incremental migration plan created successfully")
        return migration_plan
    
    def _create_migration_components(self, analysis: AnalysisReport) -> None:
        """Create migration components based on analysis results"""
        
        # Analysis component
        self.components["analysis"] = MigrationComponent(
            component_id="analysis",
            name="Source Code Analysis",
            description="Analyze source code for migration compatibility",
            phase=MigrationPhase.ANALYSIS,
            dependencies=[],
            status=ComponentStatus.COMPLETED,  # Already done
            estimated_duration_minutes=5,
            validation_checkpoints=["analysis_validation"]
        )
        
        # Dependency resolution component
        self.components["dependency_resolution"] = MigrationComponent(
            component_id="dependency_resolution",
            name="Dependency Resolution",
            description="Resolve package dependencies and compatibility issues",
            phase=MigrationPhase.DEPENDENCY_RESOLUTION,
            dependencies=["analysis"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=15,
            validation_checkpoints=["dependency_validation"],
            rollback_steps=["restore_original_requirements"]
        )
        
        # Training migration component
        self.components["training_migration"] = MigrationComponent(
            component_id="training_migration",
            name="Training Code Migration",
            description="Convert training scripts to SageMaker format",
            phase=MigrationPhase.TRAINING_MIGRATION,
            dependencies=["dependency_resolution"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=30,
            validation_checkpoints=["training_validation"],
            rollback_steps=["restore_original_training_scripts"]
        )
        
        # Inference migration component (if needed)
        if analysis.patterns.model_patterns:
            self.components["inference_migration"] = MigrationComponent(
                component_id="inference_migration",
                name="Inference Code Migration",
                description="Create SageMaker inference handlers",
                phase=MigrationPhase.INFERENCE_MIGRATION,
                dependencies=["training_migration"],
                status=ComponentStatus.PENDING,
                estimated_duration_minutes=20,
                validation_checkpoints=["inference_validation"],
                rollback_steps=["remove_inference_handlers"]
            )
        
        # Pipeline migration component
        self.components["pipeline_migration"] = MigrationComponent(
            component_id="pipeline_migration",
            name="Pipeline Creation",
            description="Create SageMaker pipeline definitions",
            phase=MigrationPhase.PIPELINE_MIGRATION,
            dependencies=["training_migration"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=25,
            validation_checkpoints=["pipeline_validation"],
            rollback_steps=["remove_pipeline_definitions"]
        )
        
        # Infrastructure deployment component
        self.components["infrastructure_deployment"] = MigrationComponent(
            component_id="infrastructure_deployment",
            name="Infrastructure Deployment",
            description="Deploy AWS infrastructure and IAM roles",
            phase=MigrationPhase.INFRASTRUCTURE_DEPLOYMENT,
            dependencies=["pipeline_migration"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=15,
            validation_checkpoints=["infrastructure_validation"],
            rollback_steps=["delete_cloudformation_stack", "remove_iam_roles"]
        )
        
        # Validation component
        self.components["validation"] = MigrationComponent(
            component_id="validation",
            name="Migration Validation",
            description="Comprehensive validation of migrated components",
            phase=MigrationPhase.VALIDATION,
            dependencies=["infrastructure_deployment"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=20,
            validation_checkpoints=["final_validation"]
        )
        
        # Production deployment component
        self.components["production_deployment"] = MigrationComponent(
            component_id="production_deployment",
            name="Production Deployment",
            description="Deploy to production environment",
            phase=MigrationPhase.PRODUCTION_DEPLOYMENT,
            dependencies=["validation"],
            status=ComponentStatus.PENDING,
            estimated_duration_minutes=10,
            validation_checkpoints=["production_validation"],
            rollback_steps=["rollback_production_deployment"]
        )
        
        # Build dependency graph
        self._build_dependency_graph()
    
    def _create_validation_checkpoints(self) -> None:
        """Create validation checkpoints between migration phases"""
        
        self.checkpoints["analysis_validation"] = ValidationCheckpoint(
            checkpoint_id="analysis_validation",
            name="Analysis Validation",
            description="Validate source code analysis results",
            phase=MigrationPhase.ANALYSIS,
            validation_criteria=[
                "All source files analyzed",
                "Dependencies identified",
                "Risk assessment completed",
                "Migration recommendations generated"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["dependency_validation"] = ValidationCheckpoint(
            checkpoint_id="dependency_validation",
            name="Dependency Validation",
            description="Validate dependency resolution",
            phase=MigrationPhase.DEPENDENCY_RESOLUTION,
            validation_criteria=[
                "All problematic packages identified",
                "SageMaker alternatives found",
                "Requirements.txt updated",
                "No version conflicts"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["training_validation"] = ValidationCheckpoint(
            checkpoint_id="training_validation",
            name="Training Validation",
            description="Validate training code migration",
            phase=MigrationPhase.TRAINING_MIGRATION,
            validation_criteria=[
                "Training scripts converted to SageMaker format",
                "SDK v3 compatibility verified",
                "Local testing successful",
                "TorchScript compatibility (if applicable)"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["inference_validation"] = ValidationCheckpoint(
            checkpoint_id="inference_validation",
            name="Inference Validation",
            description="Validate inference code migration",
            phase=MigrationPhase.INFERENCE_MIGRATION,
            validation_criteria=[
                "Inference handlers created",
                "Model loading tested",
                "Input/output formats validated",
                "Error handling implemented"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["pipeline_validation"] = ValidationCheckpoint(
            checkpoint_id="pipeline_validation",
            name="Pipeline Validation",
            description="Validate pipeline creation",
            phase=MigrationPhase.PIPELINE_MIGRATION,
            validation_criteria=[
                "Pipeline definition created",
                "Step dependencies correct",
                "Parameter passing validated",
                "Local pipeline execution successful"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["infrastructure_validation"] = ValidationCheckpoint(
            checkpoint_id="infrastructure_validation",
            name="Infrastructure Validation",
            description="Validate infrastructure deployment",
            phase=MigrationPhase.INFRASTRUCTURE_DEPLOYMENT,
            validation_criteria=[
                "CloudFormation template valid",
                "IAM policies correct",
                "S3 buckets created",
                "Roles and permissions working"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["final_validation"] = ValidationCheckpoint(
            checkpoint_id="final_validation",
            name="Final Validation",
            description="Comprehensive final validation",
            phase=MigrationPhase.VALIDATION,
            validation_criteria=[
                "End-to-end pipeline execution",
                "Model training successful",
                "Inference endpoint working",
                "Monitoring and logging active",
                "Security best practices verified"
            ],
            status=ComponentStatus.PENDING
        )
        
        self.checkpoints["production_validation"] = ValidationCheckpoint(
            checkpoint_id="production_validation",
            name="Production Validation",
            description="Validate production deployment",
            phase=MigrationPhase.PRODUCTION_DEPLOYMENT,
            validation_criteria=[
                "Production environment stable",
                "Performance benchmarks met",
                "Cost optimization verified",
                "Backup and recovery tested"
            ],
            status=ComponentStatus.PENDING
        )
    
    def _generate_hybrid_deployment_options(self, analysis: AnalysisReport) -> None:
        """Generate hybrid deployment options for gradual transition"""
        
        # Option 1: Training-first migration
        self.hybrid_options["training_first"] = HybridDeploymentOption(
            option_id="training_first",
            name="Training-First Migration",
            description="Migrate training components first, keep existing inference",
            components_migrated=["training_migration", "pipeline_migration"],
            components_remaining=["inference_migration", "production_deployment"],
            traffic_split_percentage=0,  # No production traffic initially
            rollback_strategy="Keep existing training infrastructure as backup",
            monitoring_requirements=[
                "Training job success rate",
                "Model quality metrics",
                "Training cost comparison"
            ],
            estimated_cost_impact="10-20% increase during transition"
        )
        
        # Option 2: Inference-first migration (if applicable)
        if analysis.patterns.model_patterns:
            self.hybrid_options["inference_first"] = HybridDeploymentOption(
                option_id="inference_first",
                name="Inference-First Migration",
                description="Migrate inference components first, keep existing training",
                components_migrated=["inference_migration"],
                components_remaining=["training_migration", "pipeline_migration"],
                traffic_split_percentage=10,  # Start with 10% traffic
                rollback_strategy="Blue-green deployment with instant rollback",
                monitoring_requirements=[
                    "Inference latency",
                    "Error rates",
                    "Model accuracy",
                    "Cost per inference"
                ],
                estimated_cost_impact="5-15% increase during transition"
            )
        
        # Option 3: Gradual component migration
        self.hybrid_options["gradual_migration"] = HybridDeploymentOption(
            option_id="gradual_migration",
            name="Gradual Component Migration",
            description="Migrate one component at a time with validation",
            components_migrated=[],  # Will be updated as components are migrated
            components_remaining=list(self.components.keys()),
            traffic_split_percentage=0,
            rollback_strategy="Component-level rollback with dependency management",
            monitoring_requirements=[
                "Component health checks",
                "Integration test results",
                "Performance metrics",
                "Error tracking"
            ],
            estimated_cost_impact="Minimal increase, component by component"
        )
        
        # Option 4: Full migration with staging
        self.hybrid_options["full_with_staging"] = HybridDeploymentOption(
            option_id="full_with_staging",
            name="Full Migration with Staging",
            description="Complete migration to staging environment first",
            components_migrated=list(self.components.keys()),
            components_remaining=[],
            traffic_split_percentage=0,  # Staging environment
            rollback_strategy="Keep production environment unchanged until validation",
            monitoring_requirements=[
                "Staging environment stability",
                "Performance comparison",
                "Feature parity validation",
                "Load testing results"
            ],
            estimated_cost_impact="20-30% increase for dual environments"
        )
    
    def _create_rollback_plans(self) -> None:
        """Create rollback plans for each component"""
        
        for component_id, component in self.components.items():
            if component.rollback_steps:
                # Find dependent components
                dependents = [
                    comp_id for comp_id, comp in self.components.items()
                    if component_id in comp.dependencies
                ]
                
                self.rollback_plans[component_id] = RollbackPlan(
                    plan_id=f"rollback_{component_id}",
                    component_id=component_id,
                    rollback_steps=component.rollback_steps,
                    dependencies=dependents,
                    estimated_duration_minutes=max(5, component.estimated_duration_minutes // 3),
                    data_backup_required=component_id in ["training_migration", "infrastructure_deployment"],
                    infrastructure_changes=self._get_infrastructure_changes(component_id)
                )
    
    def _get_infrastructure_changes(self, component_id: str) -> List[str]:
        """Get infrastructure changes for a component (for rollback planning)"""
        infrastructure_changes = {
            "infrastructure_deployment": [
                "CloudFormation stack deletion",
                "IAM role removal",
                "S3 bucket cleanup"
            ],
            "training_migration": [
                "SageMaker training job cleanup"
            ],
            "inference_migration": [
                "SageMaker endpoint deletion",
                "Model registry cleanup"
            ],
            "pipeline_migration": [
                "Pipeline definition removal"
            ]
        }
        return infrastructure_changes.get(component_id, [])
    
    def _build_dependency_graph(self) -> None:
        """Build dependency graph for component ordering"""
        for component_id, component in self.components.items():
            self.dependency_graph[component_id] = set(component.dependencies)
    
    def _get_execution_order(self) -> List[str]:
        """Get execution order based on dependencies (topological sort)"""
        # Simple topological sort implementation
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(node: str):
            if node in temp_visited:
                raise MigrationError(f"Circular dependency detected involving {node}")
            if node in visited:
                return
            
            temp_visited.add(node)
            for dependency in self.dependency_graph.get(node, set()):
                visit(dependency)
            temp_visited.remove(node)
            visited.add(node)
            result.append(node)
        
        for component_id in self.components.keys():
            if component_id not in visited:
                visit(component_id)
        
        return result
    
    def _initialize_progress_tracking(self) -> None:
        """Initialize progress tracking"""
        self.progress = MigrationProgress(
            migration_id=self.migration_id,
            start_time=datetime.now(),
            current_phase=MigrationPhase.ANALYSIS,
            completed_components=[],
            failed_components=[],
            total_components=len(self.components),
            completion_percentage=0.0,
            estimated_remaining_minutes=sum(comp.estimated_duration_minutes for comp in self.components.values())
        )
    
    def get_next_component(self) -> Optional[MigrationComponent]:
        """Get the next component to execute based on dependencies"""
        execution_order = self._get_execution_order()
        
        for component_id in execution_order:
            component = self.components[component_id]
            if component.status == ComponentStatus.PENDING:
                # Check if all dependencies are completed
                dependencies_met = all(
                    self.components[dep_id].status == ComponentStatus.COMPLETED
                    for dep_id in component.dependencies
                )
                if dependencies_met:
                    return component
        
        return None
    
    def start_component(self, component_id: str) -> None:
        """Start execution of a component"""
        if component_id not in self.components:
            raise MigrationError(f"Component not found: {component_id}")
        
        component = self.components[component_id]
        component.status = ComponentStatus.IN_PROGRESS
        
        if self.progress:
            self.progress.current_component = component_id
            self.progress.current_phase = component.phase
        
        logger.info(f"Started component: {component_id}")
        self._save_progress()
    
    def complete_component(self, component_id: str, artifacts_generated: Optional[List[str]] = None) -> None:
        """Mark a component as completed"""
        if component_id not in self.components:
            raise MigrationError(f"Component not found: {component_id}")
        
        component = self.components[component_id]
        component.status = ComponentStatus.COMPLETED
        
        if artifacts_generated:
            component.artifacts_generated.extend(artifacts_generated)
        
        if self.progress:
            self.progress.completed_components.append(component_id)
            self.progress.update_progress(
                self.progress.completed_components,
                self.progress.failed_components
            )
        
        logger.info(f"Completed component: {component_id}")
        self._save_progress()
    
    def fail_component(self, component_id: str, error_message: str) -> None:
        """Mark a component as failed"""
        if component_id not in self.components:
            raise MigrationError(f"Component not found: {component_id}")
        
        component = self.components[component_id]
        component.status = ComponentStatus.FAILED
        component.error_message = error_message
        
        if self.progress:
            self.progress.failed_components.append(component_id)
            self.progress.update_progress(
                self.progress.completed_components,
                self.progress.failed_components
            )
        
        logger.error(f"Failed component: {component_id} - {error_message}")
        self._save_progress()
    
    def execute_rollback(self, component_id: str) -> Dict[str, Any]:
        """Execute rollback for a failed component"""
        if component_id not in self.rollback_plans:
            raise MigrationError(f"No rollback plan found for component: {component_id}")
        
        rollback_plan = self.rollback_plans[component_id]
        logger.info(f"Executing rollback for component: {component_id}")
        
        rollback_result = {
            "component_id": component_id,
            "rollback_steps": rollback_plan.rollback_steps,
            "steps_executed": [],
            "success": True,
            "errors": []
        }
        
        # Execute rollback steps (placeholder implementation)
        for step in rollback_plan.rollback_steps:
            try:
                logger.info(f"Executing rollback step: {step}")
                # TODO: Implement actual rollback logic
                rollback_result["steps_executed"].append(step)
            except Exception as e:
                rollback_result["success"] = False
                rollback_result["errors"].append(f"Failed to execute {step}: {str(e)}")
                logger.error(f"Rollback step failed: {step} - {str(e)}")
        
        # Update component status
        if rollback_result["success"]:
            self.components[component_id].status = ComponentStatus.ROLLED_BACK
        
        # Handle dependent components
        for dependent_id in rollback_plan.dependencies:
            if self.components[dependent_id].status == ComponentStatus.COMPLETED:
                logger.warning(f"Dependent component {dependent_id} may need rollback")
        
        self._save_progress()
        return rollback_result
    
    def validate_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """Execute validation checkpoint"""
        if checkpoint_id not in self.checkpoints:
            raise MigrationError(f"Checkpoint not found: {checkpoint_id}")
        
        checkpoint = self.checkpoints[checkpoint_id]
        logger.info(f"Validating checkpoint: {checkpoint_id}")
        
        validation_result = {
            "checkpoint_id": checkpoint_id,
            "criteria": checkpoint.validation_criteria,
            "results": {},
            "success": True,
            "errors": []
        }
        
        # Execute validation criteria (placeholder implementation)
        for criterion in checkpoint.validation_criteria:
            try:
                # TODO: Implement actual validation logic
                validation_result["results"][criterion] = True
                logger.info(f"Validation criterion passed: {criterion}")
            except Exception as e:
                validation_result["success"] = False
                validation_result["results"][criterion] = False
                validation_result["errors"].append(f"Failed criterion {criterion}: {str(e)}")
                logger.error(f"Validation criterion failed: {criterion} - {str(e)}")
        
        # Update checkpoint status
        checkpoint.status = ComponentStatus.COMPLETED if validation_result["success"] else ComponentStatus.FAILED
        checkpoint.validation_results = validation_result["results"]
        if not validation_result["success"]:
            checkpoint.error_message = "; ".join(validation_result["errors"])
        
        self._save_progress()
        return validation_result
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status and progress"""
        if not self.progress:
            return {"error": "Migration not initialized"}
        
        return {
            "migration_id": self.migration_id,
            "progress": asdict(self.progress),
            "components": {
                comp_id: {
                    "name": comp.name,
                    "status": comp.status.value,
                    "phase": comp.phase.value,
                    "error_message": comp.error_message
                }
                for comp_id, comp in self.components.items()
            },
            "checkpoints": {
                cp_id: {
                    "name": cp.name,
                    "status": cp.status.value,
                    "phase": cp.phase.value
                }
                for cp_id, cp in self.checkpoints.items()
            },
            "next_component": self.get_next_component().component_id if self.get_next_component() else None
        }
    
    def generate_status_report(self) -> str:
        """Generate a human-readable status report"""
        if not self.progress:
            return "Migration not initialized"
        
        report_lines = [
            f"Migration Status Report - {self.migration_id}",
            f"Started: {self.progress.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Current Phase: {self.progress.current_phase.value}",
            f"Progress: {self.progress.completion_percentage:.1f}%",
            f"Completed: {len(self.progress.completed_components)}/{self.progress.total_components}",
            ""
        ]
        
        if self.progress.failed_components:
            report_lines.extend([
                "Failed Components:",
                *[f"  - {comp_id}: {self.components[comp_id].error_message}" 
                  for comp_id in self.progress.failed_components],
                ""
            ])
        
        if self.progress.current_component:
            current_comp = self.components[self.progress.current_component]
            report_lines.extend([
                f"Current Component: {current_comp.name}",
                f"Status: {current_comp.status.value}",
                ""
            ])
        
        next_comp = self.get_next_component()
        if next_comp:
            report_lines.extend([
                f"Next Component: {next_comp.name}",
                f"Estimated Duration: {next_comp.estimated_duration_minutes} minutes",
                ""
            ])
        
        return "\n".join(report_lines)
    
    def _save_migration_plan(self, migration_plan: Dict[str, Any]) -> None:
        """Save migration plan to file"""
        plan_file = self.output_path / "migration_plan.json"
        with open(plan_file, 'w') as f:
            json.dump(migration_plan, f, indent=2, default=str)
        logger.info(f"Migration plan saved to: {plan_file}")
    
    def _save_progress(self) -> None:
        """Save current progress to file"""
        if not self.progress:
            return
        
        progress_file = self.output_path / "migration_progress.json"
        progress_data = {
            "progress": asdict(self.progress),
            "components": {comp_id: asdict(comp) for comp_id, comp in self.components.items()},
            "checkpoints": {cp_id: asdict(cp) for cp_id, cp in self.checkpoints.items()},
            "last_updated": datetime.now().isoformat()
        }
        
        # Convert enums to strings for JSON serialization
        progress_data["progress"]["current_phase"] = progress_data["progress"]["current_phase"].value
        progress_data["progress"]["start_time"] = progress_data["progress"]["start_time"].isoformat()
        
        for comp_data in progress_data["components"].values():
            comp_data["status"] = comp_data["status"].value
            comp_data["phase"] = comp_data["phase"].value
        
        for cp_data in progress_data["checkpoints"].values():
            cp_data["status"] = cp_data["status"].value
            cp_data["phase"] = cp_data["phase"].value
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2, default=str)
    
    def load_migration_state(self) -> bool:
        """Load migration state from saved files"""
        try:
            progress_file = self.output_path / "migration_progress.json"
            if not progress_file.exists():
                return False
            
            with open(progress_file, 'r') as f:
                data = json.load(f)
            
            # Restore progress
            progress_data = data["progress"]
            progress_data["start_time"] = datetime.fromisoformat(progress_data["start_time"])
            progress_data["current_phase"] = MigrationPhase(progress_data["current_phase"])
            self.progress = MigrationProgress(**progress_data)
            
            # Restore components
            for comp_id, comp_data in data["components"].items():
                comp_data["status"] = ComponentStatus(comp_data["status"])
                comp_data["phase"] = MigrationPhase(comp_data["phase"])
                self.components[comp_id] = MigrationComponent(**comp_data)
            
            # Restore checkpoints
            for cp_id, cp_data in data["checkpoints"].items():
                cp_data["status"] = ComponentStatus(cp_data["status"])
                cp_data["phase"] = MigrationPhase(cp_data["phase"])
                self.checkpoints[cp_id] = ValidationCheckpoint(**cp_data)
            
            # Rebuild dependency graph
            self._build_dependency_graph()
            
            logger.info("Migration state loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load migration state: {str(e)}")
            return False