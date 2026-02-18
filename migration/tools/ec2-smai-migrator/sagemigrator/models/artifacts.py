"""
Migration artifacts models for SageBridge

Data structures for generated migration artifacts.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from .analysis import AnalysisReport


@dataclass
class InfrastructureCode:
    """Infrastructure as code artifacts"""
    cloudformation_templates: Dict[str, str]
    iam_policies: Dict[str, str]
    deployment_scripts: Dict[str, str]
    configuration_files: Dict[str, str]


@dataclass
class TestingSuite:
    """Testing artifacts and test suites"""
    unit_tests: Dict[str, str]
    integration_tests: Dict[str, str]
    property_tests: Dict[str, str]
    performance_tests: Dict[str, str]
    test_data: Dict[str, Any]


@dataclass
class DocumentationPackage:
    """Documentation and guides"""
    readme_files: Dict[str, str]
    migration_guides: Dict[str, str]
    troubleshooting_docs: Dict[str, str]
    api_documentation: Dict[str, str]
    deployment_guides: Dict[str, str]


@dataclass
class MigrationArtifacts:
    """Complete set of migration artifacts"""
    training_scripts: Dict[str, str]
    inference_handlers: Dict[str, str]
    pipeline_definitions: Dict[str, str]
    infrastructure: InfrastructureCode
    testing_suite: TestingSuite
    documentation: DocumentationPackage
    metadata: Dict[str, Any]
    
    @classmethod
    def create_placeholder(cls, analysis: AnalysisReport) -> 'MigrationArtifacts':
        """Create placeholder migration artifacts for testing"""
        import datetime
        
        return cls(
            training_scripts={
                "train.py": "# SageMaker training script\n# Generated from analysis",
                "requirements.txt": "sagemaker>=2.0\ntorch>=2.0\nnumpy\npandas"
            },
            inference_handlers={
                "inference.py": "# SageMaker inference handler\n# Generated from analysis",
                "model.py": "# Model definition for inference"
            },
            pipeline_definitions={
                "pipeline.py": "# SageMaker pipeline definition\n# Generated from analysis"
            },
            infrastructure=InfrastructureCode(
                cloudformation_templates={
                    "main.yaml": "# CloudFormation template\n# Generated infrastructure"
                },
                iam_policies={
                    "sagemaker-role.json": "# IAM policy for SageMaker\n# Generated policies"
                },
                deployment_scripts={
                    "deploy.py": "# Deployment script\n# Generated deployment automation"
                },
                configuration_files={
                    "config.yaml": "# Configuration file\n# Generated configuration"
                }
            ),
            testing_suite=TestingSuite(
                unit_tests={
                    "test_training.py": "# Unit tests for training\n# Generated tests"
                },
                integration_tests={
                    "test_pipeline.py": "# Integration tests\n# Generated tests"
                },
                property_tests={
                    "test_properties.py": "# Property-based tests\n# Generated tests"
                },
                performance_tests={
                    "test_performance.py": "# Performance tests\n# Generated tests"
                },
                test_data={"sample_data": "test data"}
            ),
            documentation=DocumentationPackage(
                readme_files={
                    "README.md": "# Migration Documentation\n# Generated documentation"
                },
                migration_guides={
                    "MIGRATION_GUIDE.md": "# Migration Guide\n# Generated guide"
                },
                troubleshooting_docs={
                    "TROUBLESHOOTING.md": "# Troubleshooting\n# Generated troubleshooting"
                },
                api_documentation={
                    "API.md": "# API Documentation\n# Generated API docs"
                },
                deployment_guides={
                    "DEPLOYMENT.md": "# Deployment Guide\n# Generated deployment guide"
                }
            ),
            metadata={
                "source_analysis": analysis.to_dict(),
                "generation_timestamp": datetime.datetime.now().isoformat(),
                "sagebridge_version": "0.1.0"
            }
        )
    
    def save_to_directory(self, output_path: Path) -> None:
        """Save migration artifacts to directory structure"""
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save training scripts
        training_dir = output_path / "training"
        training_dir.mkdir(exist_ok=True)
        for filename, content in self.training_scripts.items():
            (training_dir / filename).write_text(content)
        
        # Save inference handlers
        inference_dir = output_path / "inference"
        inference_dir.mkdir(exist_ok=True)
        for filename, content in self.inference_handlers.items():
            (inference_dir / filename).write_text(content)
        
        # Save pipeline definitions
        pipeline_dir = output_path / "pipeline"
        pipeline_dir.mkdir(exist_ok=True)
        for filename, content in self.pipeline_definitions.items():
            (pipeline_dir / filename).write_text(content)
        
        # Save infrastructure
        infra_dir = output_path / "infrastructure"
        infra_dir.mkdir(exist_ok=True)
        for filename, content in self.infrastructure.cloudformation_templates.items():
            (infra_dir / "cloudformation" / filename).parent.mkdir(parents=True, exist_ok=True)
            (infra_dir / "cloudformation" / filename).write_text(content)
        for filename, content in self.infrastructure.iam_policies.items():
            (infra_dir / "iam" / filename).parent.mkdir(parents=True, exist_ok=True)
            (infra_dir / "iam" / filename).write_text(content)
        for filename, content in self.infrastructure.deployment_scripts.items():
            (infra_dir / "scripts" / filename).parent.mkdir(parents=True, exist_ok=True)
            (infra_dir / "scripts" / filename).write_text(content)
        
        # Save testing suite
        tests_dir = output_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        for filename, content in self.testing_suite.unit_tests.items():
            (tests_dir / "unit" / filename).parent.mkdir(parents=True, exist_ok=True)
            (tests_dir / "unit" / filename).write_text(content)
        for filename, content in self.testing_suite.integration_tests.items():
            (tests_dir / "integration" / filename).parent.mkdir(parents=True, exist_ok=True)
            (tests_dir / "integration" / filename).write_text(content)
        
        # Save documentation
        docs_dir = output_path / "docs"
        docs_dir.mkdir(exist_ok=True)
        for filename, content in self.documentation.readme_files.items():
            (docs_dir / filename).write_text(content)
        for filename, content in self.documentation.migration_guides.items():
            (docs_dir / filename).write_text(content)
        
        # Save metadata
        metadata_file = output_path / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    @classmethod
    def load_from_directory(cls, artifacts_path: Path) -> 'MigrationArtifacts':
        """Load migration artifacts from directory structure"""
        import json
        
        # Load CloudFormation templates
        cloudformation_templates = {}
        cf_dir = artifacts_path / "infrastructure" / "cloudformation"
        if cf_dir.exists():
            for cf_file in cf_dir.glob("*.yaml"):
                cloudformation_templates[cf_file.name] = cf_file.read_text()
            for cf_file in cf_dir.glob("*.yml"):
                cloudformation_templates[cf_file.name] = cf_file.read_text()
        
        # Load IAM policies
        iam_policies = {}
        iam_dir = artifacts_path / "infrastructure" / "iam"
        if iam_dir.exists():
            for iam_file in iam_dir.glob("*.json"):
                iam_policies[iam_file.stem] = iam_file.read_text()
        
        # Load deployment scripts
        deployment_scripts = {}
        scripts_dir = artifacts_path / "infrastructure" / "scripts"
        if scripts_dir.exists():
            for script_file in scripts_dir.glob("*.sh"):
                deployment_scripts[script_file.name] = script_file.read_text()
        
        # Load training scripts
        training_scripts = {}
        training_dir = artifacts_path / "training"
        if training_dir.exists():
            for training_file in training_dir.glob("*.py"):
                training_scripts[training_file.name] = training_file.read_text()
        
        # Load inference handlers
        inference_handlers = {}
        inference_dir = artifacts_path / "inference"
        if inference_dir.exists():
            for inference_file in inference_dir.glob("*.py"):
                inference_handlers[inference_file.name] = inference_file.read_text()
        
        # Load pipeline definitions
        pipeline_definitions = {}
        pipeline_dir = artifacts_path / "pipeline"
        if pipeline_dir.exists():
            for pipeline_file in pipeline_dir.glob("*.py"):
                pipeline_definitions[pipeline_file.name] = pipeline_file.read_text()
        
        # Load test files
        unit_tests = {}
        integration_tests = {}
        property_tests = {}
        performance_tests = {}
        
        tests_dir = artifacts_path / "tests"
        if tests_dir.exists():
            for test_file in tests_dir.glob("*.py"):
                if "integration" in test_file.name:
                    integration_tests[test_file.name] = test_file.read_text()
                elif "property" in test_file.name:
                    property_tests[test_file.name] = test_file.read_text()
                elif "performance" in test_file.name:
                    performance_tests[test_file.name] = test_file.read_text()
                else:
                    unit_tests[test_file.name] = test_file.read_text()
        
        # Load documentation
        readme_files = {}
        migration_guides = {}
        troubleshooting_docs = {}
        api_documentation = {}
        deployment_guides = {}
        
        docs_dir = artifacts_path / "documentation"
        if docs_dir.exists():
            for doc_file in docs_dir.glob("*.md"):
                if "readme" in doc_file.name.lower():
                    readme_files[doc_file.name] = doc_file.read_text()
                elif "migration" in doc_file.name.lower():
                    migration_guides[doc_file.name] = doc_file.read_text()
                elif "troubleshooting" in doc_file.name.lower():
                    troubleshooting_docs[doc_file.name] = doc_file.read_text()
                elif "api" in doc_file.name.lower():
                    api_documentation[doc_file.name] = doc_file.read_text()
                elif "deployment" in doc_file.name.lower():
                    deployment_guides[doc_file.name] = doc_file.read_text()
                else:
                    readme_files[doc_file.name] = doc_file.read_text()
        
        # Load metadata
        metadata = {}
        metadata_file = artifacts_path / "metadata.json"
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text())
        
        # Create infrastructure code object
        infrastructure = InfrastructureCode(
            cloudformation_templates=cloudformation_templates,
            iam_policies=iam_policies,
            deployment_scripts=deployment_scripts,
            configuration_files={}
        )
        
        # Create testing suite object
        testing_suite = TestingSuite(
            unit_tests=unit_tests,
            integration_tests=integration_tests,
            property_tests=property_tests,
            performance_tests=performance_tests,
            test_data={}
        )
        
        # Create documentation package object
        documentation = DocumentationPackage(
            readme_files=readme_files,
            migration_guides=migration_guides,
            troubleshooting_docs=troubleshooting_docs,
            api_documentation=api_documentation,
            deployment_guides=deployment_guides
        )
        
        return cls(
            training_scripts=training_scripts,
            inference_handlers=inference_handlers,
            pipeline_definitions=pipeline_definitions,
            infrastructure=infrastructure,
            testing_suite=testing_suite,
            documentation=documentation,
            metadata=metadata
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of migration artifacts"""
        return {
            "training_scripts": len(self.training_scripts),
            "inference_handlers": len(self.inference_handlers),
            "pipeline_definitions": len(self.pipeline_definitions),
            "cloudformation_templates": len(self.infrastructure.cloudformation_templates),
            "iam_policies": len(self.infrastructure.iam_policies),
            "unit_tests": len(self.testing_suite.unit_tests),
            "integration_tests": len(self.testing_suite.integration_tests),
            "documentation_files": (
                len(self.documentation.readme_files) +
                len(self.documentation.migration_guides) +
                len(self.documentation.troubleshooting_docs)
            )
        }