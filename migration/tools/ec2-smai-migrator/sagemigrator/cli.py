"""
SageMigrator CLI - Command Line Interface for EC2 to SageMaker Migration

Provides user-friendly commands for analyzing, migrating, validating, and deploying
EC2 training code to SageMaker.
"""

import click
import logging
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .migration_agent import MigrationAgent
from .config import Config
from .utils.logging import setup_logging


# Initialize rich console for better output formatting
console = Console()


def show_progress(description: str, total: int = 100):
    """Create a progress bar for long-running operations"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    )


def display_analysis_summary(analysis_report):
    """Display analysis results in a formatted table"""
    console.print("\n[bold blue]Compatibility Issues:[/bold blue]")
    
    table = Table(title="Analysis Summary", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")
    table.add_column("Details", style="yellow")
    
    # Add rows based on analysis report structure
    if hasattr(analysis_report, 'dependencies'):
        table.add_row(
            "Dependencies", 
            str(analysis_report.dependencies.total_dependencies),
            f"Problematic: {len(analysis_report.dependencies.problematic_packages)}"
        )
    
    if hasattr(analysis_report, 'patterns'):
        patterns_count = sum([
            1 for attr in ['uses_gpu', 'distributed_training', 'compute_intensive'] 
            if getattr(analysis_report.patterns, attr, False)
        ])
        table.add_row("Patterns Detected", str(patterns_count), "GPU, Distributed, Compute-intensive")
    
    if hasattr(analysis_report, 'risks'):
        table.add_row(
            "Risk Level", 
            str(len(analysis_report.risks.high_risk_items)),
            f"High: {len(analysis_report.risks.high_risk_items)}, Medium: {len(analysis_report.risks.medium_risk_items)}"
        )
    
    console.print(table)
    
    # Display dependencies to replace
    if hasattr(analysis_report, 'dependencies') and analysis_report.dependencies.problematic_packages:
        console.print("\n[bold yellow]Dependencies to Replace:[/bold yellow]")
        for pkg in analysis_report.dependencies.problematic_packages[:5]:
            console.print(f"  • {pkg}")
    else:
        console.print("\n[bold yellow]Dependencies to Replace:[/bold yellow]")
        console.print("  • No problematic dependencies found")


def display_validation_results(validation_report):
    """Display validation results with color coding"""
    if validation_report.has_errors():
        console.print(Panel("❌ Validation Failed", style="red"))
        for error in validation_report.get_errors():
            console.print(f"  • {error}", style="red")
    elif validation_report.has_warnings():
        console.print(Panel("⚠️  Validation Completed with Warnings", style="yellow"))
        for warning in validation_report.get_warnings():
            console.print(f"  • {warning}", style="yellow")
    else:
        console.print(Panel("✅ All Validations Passed!", style="green"))


def confirm_action(message: str) -> bool:
    """Ask user for confirmation"""
    return click.confirm(message)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[str]) -> None:
    """SageMigrator - Intelligent EC2 to SageMaker Migration System"""
    ctx.ensure_object(dict)
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)
    
    # Load configuration
    config_path = Path(config) if config else None
    ctx.obj['config'] = Config.load(config_path)
    ctx.obj['verbose'] = verbose
    
    # Display welcome message
    if not ctx.invoked_subcommand:
        console.print(Panel.fit(
            "[bold blue]SageMigrator[/bold blue]\n"
            "Intelligent EC2 to SageMaker Migration System\n\n"
            "Use --help to see available commands",
            style="blue"
        ))


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[str]) -> None:
    """SageMigrator - Intelligent EC2 to SageMaker Migration System"""
    ctx.ensure_object(dict)
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)
    
    # Load configuration
    config_path = Path(config) if config else None
    ctx.obj['config'] = Config.load(config_path)
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('source_path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', '-o', type=click.Path(), help='Output directory for analysis report')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'table']), 
              default='table', help='Output format for analysis results')
@click.pass_context
def analyze(ctx: click.Context, source_path: str, output: Optional[str], output_format: str) -> None:
    """Analyze source code for SageMaker compatibility issues"""
    console.print(f"[bold blue]Analyzing source code at:[/bold blue] {source_path}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        with show_progress("Analyzing source code...") as progress:
            task = progress.add_task("Analysis", total=100)
            
            # Simulate progress updates during analysis
            progress.update(task, advance=20)
            time.sleep(0.5)  # Simulate work
            
            analysis_report = agent.analyze_source_code(source_path)
            
            progress.update(task, advance=80)
            time.sleep(0.2)
        
        if output_format == 'table':
            display_analysis_summary(analysis_report)
        
        console.print("[green]Analysis completed successfully[/green]")
        
        if output:
            output_path = Path(output)
            output_path.mkdir(parents=True, exist_ok=True)
            # Default to JSON format when saving to file
            save_format = output_format if output_format != 'table' else 'json'
            report_file = output_path / f"analysis_report.{save_format}"
            analysis_report.save_to_file(report_file)
            console.print(f"[green]Analysis report saved to:[/green] {report_file}")
        
        # Show recommendations
        if hasattr(analysis_report, 'recommendations') and analysis_report.recommendations:
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            for i, rec in enumerate(analysis_report.recommendations[:5], 1):
                console.print(f"  {i}. {rec}")
            
    except Exception as e:
        console.print(f"[red]Error during analysis:[/red] {str(e)}")
        raise click.ClickException(f"Analysis failed: {str(e)}")


@cli.command()
@click.argument('source_path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', '-o', type=click.Path(), required=True, help='Output directory for migration artifacts')
@click.option('--skip-validation', is_flag=True, help='Skip validation of generated artifacts')
@click.option('--interactive', '-i', is_flag=True, help='Interactive mode with confirmations')
@click.option('--dry-run', is_flag=True, help='Show what would be generated without creating files')
@click.option('--processor-type', type=click.Choice(['pytorch', 'sklearn']), default='sklearn',
              help='Processor type for evaluation step (pytorch or sklearn)')
@click.pass_context
def migrate(ctx: click.Context, source_path: str, output: str, skip_validation: bool, 
           interactive: bool, dry_run: bool, processor_type: str) -> None:
    """Perform full migration from EC2 to SageMaker"""
    console.print(f"[bold blue]Starting migration of:[/bold blue] {source_path}")
    console.print(f"[blue]Processor Type:[/blue] {processor_type}")
    
    if dry_run:
        console.print("[yellow]Running in dry-run mode - no files will be created[/yellow]")
    
    config = ctx.obj['config']
    
    # Add processor type to config
    config.processor_type = processor_type
    
    agent = MigrationAgent(config)
    
    try:
        # Step 1: Analyze source code
        with show_progress("Analyzing source code...") as progress:
            task = progress.add_task("Analysis", total=100)
            analysis_report = agent.analyze_source_code(source_path)
            progress.update(task, advance=100)
        
        console.print("✅ [green]Analysis completed[/green]")
        display_analysis_summary(analysis_report)
        
        if interactive and not confirm_action("Continue with migration?"):
            console.print("[yellow]Migration cancelled by user[/yellow]")
            return
        
        # Step 2: Generate migration artifacts
        with show_progress("Generating migration artifacts...") as progress:
            task = progress.add_task("Generation", total=100)
            
            progress.update(task, advance=20, description="Generating training scripts...")
            time.sleep(0.3)
            
            progress.update(task, advance=40, description="Generating infrastructure code...")
            time.sleep(0.3)
            
            progress.update(task, advance=70, description="Generating validation tests...")
            time.sleep(0.3)
            
            migration_artifacts = agent.generate_migration_artifacts(analysis_report)
            progress.update(task, advance=100)
        
        console.print("✅ [green]Artifact generation completed[/green]")
        
        # Show what would be created
        if dry_run:
            console.print("\n[bold yellow]Files that would be created:[/bold yellow]")
            for script_name in migration_artifacts.training_scripts.keys():
                console.print(f"  📄 training/{script_name}")
            for handler_name in migration_artifacts.inference_handlers.keys():
                console.print(f"  📄 inference/{handler_name}")
            console.print(f"  📄 infrastructure/cloudformation.yaml")
            console.print(f"  📄 tests/ (multiple test files)")
            console.print(f"  📄 documentation/ (multiple docs)")
            return
        
        # Save artifacts to output directory
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)
        migration_artifacts.save_to_directory(output_path)
        
        # Step 3: Validate artifacts if not skipped
        if not skip_validation:
            with show_progress("Validating migration artifacts...") as progress:
                task = progress.add_task("Validation", total=100)
                validation_report = agent.validate_migration(migration_artifacts)
                progress.update(task, advance=100)
            
            validation_report.save_to_file(output_path / "validation_report.json")
            display_validation_results(validation_report)
        
        # Success summary
        console.print(Panel.fit(
            f"[bold green]Migration Completed Successfully![/bold green]\n\n"
            f"📁 Artifacts saved to: {output_path}\n"
            f"📊 Analysis report: analysis_report.json\n"
            f"✅ Validation report: validation_report.json\n\n"
            f"Next steps:\n"
            f"1. Review generated artifacts\n"
            f"2. Run: sagemigrator validate {output_path}\n"
            f"3. Deploy: sagemigrator deploy {output_path}",
            style="green"
        ))
        
    except Exception as e:
        console.print(f"[red]Error during migration:[/red] {str(e)}")
        raise click.ClickException(f"Migration failed: {str(e)}")


@cli.command()
@click.argument('artifacts_path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', '-o', type=click.Path(), help='Output file for validation report')
@click.option('--detailed', is_flag=True, help='Show detailed validation results')
@click.option('--fix-issues', is_flag=True, help='Attempt to automatically fix common issues')
@click.pass_context
def validate(ctx: click.Context, artifacts_path: str, output: Optional[str], 
            detailed: bool, fix_issues: bool) -> None:
    """Validate migration artifacts for production readiness"""
    console.print(f"[bold blue]Validating artifacts at:[/bold blue] {artifacts_path}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        # Load migration artifacts
        with show_progress("Loading migration artifacts...") as progress:
            task = progress.add_task("Loading", total=100)
            artifacts_path_obj = Path(artifacts_path)
            migration_artifacts = agent.load_migration_artifacts(artifacts_path_obj)
            progress.update(task, advance=100)
        
        # Validate artifacts
        with show_progress("Running validation checks...") as progress:
            task = progress.add_task("Validation", total=100)
            
            progress.update(task, advance=25, description="Checking code compatibility...")
            time.sleep(0.2)
            
            progress.update(task, advance=50, description="Validating infrastructure...")
            time.sleep(0.2)
            
            progress.update(task, advance=75, description="Checking security settings...")
            time.sleep(0.2)
            
            validation_report = agent.validate_migration(migration_artifacts)
            progress.update(task, advance=100)
        
        if output:
            output_path = Path(output)
            validation_report.save_to_file(output_path)
            console.print(f"[green]Validation report saved to:[/green] {output_path}")
        
        # Display results
        display_validation_results(validation_report)
        
        if detailed:
            console.print("\n[bold yellow]Detailed Results:[/bold yellow]")
            if hasattr(validation_report, 'compatibility_checks'):
                for check in validation_report.compatibility_checks[:10]:  # Show first 10
                    status_color = "green" if str(check.status).upper() == "PASSED" else "red"
                    console.print(f"  [{status_color}]{check.check_name}[/{status_color}]: {check.message}")
        
        # Show production readiness score
        if hasattr(validation_report, 'production_readiness_score'):
            score = validation_report.production_readiness_score
            score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            console.print(f"\n[bold]Production Readiness Score:[/bold] [{score_color}]{score:.1f}%[/{score_color}]")
        
        # Offer to fix issues if requested
        if fix_issues and validation_report.has_errors():
            if confirm_action("Attempt to automatically fix detected issues?"):
                console.print("[yellow]Automatic issue fixing is not yet implemented[/yellow]")
                console.print("[yellow]Please review the validation report and fix issues manually[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error during validation:[/red] {str(e)}")
        raise click.ClickException(f"Validation failed: {str(e)}")


@cli.command()
@click.argument('artifacts_path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--region', default='us-east-1', help='AWS region for deployment')
@click.option('--dry-run', is_flag=True, help='Show what would be deployed without actually deploying')
@click.option('--interactive', '-i', is_flag=True, help='Interactive deployment with confirmations')
@click.option('--stack-name', help='Custom CloudFormation stack name')
@click.pass_context
def deploy(ctx: click.Context, artifacts_path: str, region: str, dry_run: bool, 
          interactive: bool, stack_name: Optional[str]) -> None:
    """Deploy infrastructure and SageMaker resources"""
    console.print(f"[bold blue]Deploying artifacts from:[/bold blue] {artifacts_path}")
    console.print(f"[blue]Target region:[/blue] {region}")
    
    if dry_run:
        console.print("[yellow]Running in dry-run mode - no resources will be created[/yellow]")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        # Load migration artifacts
        with show_progress("Loading migration artifacts...") as progress:
            task = progress.add_task("Loading", total=100)
            artifacts_path_obj = Path(artifacts_path)
            migration_artifacts = agent.load_migration_artifacts(artifacts_path_obj)
            progress.update(task, advance=100)
        
        if dry_run or interactive:
            console.print("\n[bold yellow]Deployment Plan:[/bold yellow]")
            deployment_plan = agent.generate_deployment_plan(migration_artifacts, region)
            
            # Display deployment steps
            table = Table(title="Deployment Steps", show_header=True, header_style="bold magenta")
            table.add_column("Step", style="cyan", no_wrap=True)
            table.add_column("Resource", style="green")
            table.add_column("Description", style="yellow")
            
            for i, step in enumerate(deployment_plan.steps, 1):
                table.add_row(str(i), step.step_name, step.description)
            
            console.print(table)
            
            if dry_run:
                console.print("\n[yellow]Dry run completed - no resources were created[/yellow]")
                return
            
            if interactive and not confirm_action("Proceed with deployment?"):
                console.print("[yellow]Deployment cancelled by user[/yellow]")
                return
        
        # Execute deployment
        with show_progress("Deploying infrastructure...") as progress:
            task = progress.add_task("Deployment", total=100)
            
            progress.update(task, advance=20, description="Creating CloudFormation stack...")
            time.sleep(1.0)
            
            progress.update(task, advance=50, description="Provisioning resources...")
            time.sleep(1.5)
            
            progress.update(task, advance=80, description="Configuring permissions...")
            time.sleep(0.5)
            
            deployment_result = agent.deploy_infrastructure(migration_artifacts, region)
            progress.update(task, advance=100)
        
        if deployment_result.success:
            console.print(Panel.fit(
                f"[bold green]Deployment Completed Successfully![/bold green]\n\n"
                f"🏗️  Stack Name: {deployment_result.stack_name}\n"
                f"🌍 Region: {deployment_result.region}\n"
                f"📊 Resources Created: {len(deployment_result.resources_created)}\n"
                f"🔑 ExecutionRoleArn: {deployment_result.get_execution_role_arn()}\n"
                f"🪣 S3BucketName: {deployment_result.get_s3_bucket_name()}\n\n"
                f"Next steps:\n"
                f"1. Execute SageMaker pipeline: sagemigrator execute {artifacts_path}/training/pipeline.py\n"
                f"2. Test your SageMaker pipeline\n"
                f"3. Monitor CloudWatch logs\n"
                f"4. Check AWS console for resources",
                style="green"
            ))
            
            # Show created resources
            if deployment_result.resources_created:
                console.print("\n[bold yellow]Created Resources:[/bold yellow]")
                for resource in deployment_result.resources_created[:10]:  # Show first 10
                    console.print(f"  🔧 {resource}")
        else:
            console.print(Panel("❌ Deployment Failed", style="red"))
            for error in deployment_result.errors:
                console.print(f"  • {error}", style="red")
                    
    except Exception as e:
        console.print(f"[red]Error during deployment:[/red] {str(e)}")
        raise click.ClickException(f"Deployment failed: {str(e)}")


@cli.group()
def incremental():
    """Incremental migration commands for component-by-component migration"""
    pass


@incremental.command()
@click.argument('source_path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--migration-id', required=True, help='Unique identifier for this migration')
@click.option('--output', '-o', type=click.Path(), required=True, help='Output directory for migration artifacts and progress')
@click.option('--interactive', '-i', is_flag=True, help='Interactive planning with user input')
@click.pass_context
def plan(ctx: click.Context, source_path: str, migration_id: str, output: str, interactive: bool) -> None:
    """Create an incremental migration plan"""
    console.print(f"[bold blue]Creating incremental migration plan for:[/bold blue] {source_path}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        # Analyze source code first
        with show_progress("Analyzing source code...") as progress:
            task = progress.add_task("Analysis", total=100)
            analysis_report = agent.analyze_source_code(source_path)
            progress.update(task, advance=100)
        
        # Create incremental migration plan
        with show_progress("Creating migration plan...") as progress:
            task = progress.add_task("Planning", total=100)
            output_path = Path(output)
            migration_plan = agent.create_incremental_migration_plan(analysis_report, migration_id, output_path)
            progress.update(task, advance=100)
        
        console.print("✅ [green]Incremental migration plan created successfully![/green]")
        
        # Display plan summary
        summary_table = Table(title="Migration Plan Summary", show_header=True, header_style="bold magenta")
        summary_table.add_column("Metric", style="cyan", no_wrap=True)
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Migration ID", migration_id)
        summary_table.add_row("Total Components", str(len(migration_plan['components'])))
        summary_table.add_row("Validation Checkpoints", str(len(migration_plan['checkpoints'])))
        summary_table.add_row("Hybrid Options", str(len(migration_plan['hybrid_options'])))
        summary_table.add_row("Plan Location", str(output_path))
        
        console.print(summary_table)
        
        # Show execution order
        console.print("\n[bold yellow]Execution Order:[/bold yellow]")
        execution_table = Table(show_header=True, header_style="bold blue")
        execution_table.add_column("Step", style="cyan", no_wrap=True)
        execution_table.add_column("Component", style="green")
        execution_table.add_column("Duration", style="yellow")
        execution_table.add_column("Dependencies", style="magenta")
        
        for i, component_id in enumerate(migration_plan['dependency_order'], 1):
            component = migration_plan['components'][component_id]
            dependencies = ", ".join(component.get('dependencies', []))
            execution_table.add_row(
                str(i), 
                component['name'], 
                f"{component['estimated_duration_minutes']} min",
                dependencies or "None"
            )
        
        console.print(execution_table)
        
        if interactive:
            console.print("\n[bold yellow]Next Steps:[/bold yellow]")
            console.print("1. Review the execution plan above")
            console.print("2. Run: sagemigrator incremental status --migration-id {} --output {}".format(migration_id, output))
            console.print("3. Execute components: sagemigrator incremental execute <component-id> --migration-id {} --output {}".format(migration_id, output))
        
    except Exception as e:
        console.print(f"[red]Error creating migration plan:[/red] {str(e)}")
        raise click.ClickException(f"Plan creation failed: {str(e)}")


@incremental.command()
@click.option('--migration-id', required=True, help='Migration identifier')
@click.option('--output', '-o', type=click.Path(exists=True), required=True, help='Migration artifacts directory')
@click.option('--watch', '-w', is_flag=True, help='Watch mode - continuously update status')
@click.pass_context
def status(ctx: click.Context, migration_id: str, output: str, watch: bool) -> None:
    """Get current migration status and progress"""
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    def display_status():
        try:
            output_path = Path(output)
            status_info = agent.get_migration_status(migration_id, output_path)
            
            progress_info = status_info['progress']
            
            # Clear screen for watch mode
            if watch:
                console.clear()
            
            # Main status panel
            status_text = (
                f"[bold blue]Migration ID:[/bold blue] {migration_id}\n"
                f"[bold blue]Current Phase:[/bold blue] {progress_info['current_phase']}\n"
                f"[bold blue]Progress:[/bold blue] {progress_info['completion_percentage']:.1f}%\n"
                f"[bold blue]Completed:[/bold blue] {len(progress_info['completed_components'])}/{progress_info['total_components']}"
            )
            
            console.print(Panel(status_text, title="Migration Status", style="blue"))
            
            # Progress bar
            progress_bar = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            )
            
            with progress_bar:
                task = progress_bar.add_task("Overall Progress", total=100)
                progress_bar.update(task, completed=progress_info['completion_percentage'])
            
            # Component status table
            component_table = Table(title="Component Status", show_header=True, header_style="bold magenta")
            component_table.add_column("Component", style="cyan")
            component_table.add_column("Status", style="green")
            component_table.add_column("Duration", style="yellow")
            component_table.add_column("Error", style="red")
            
            for comp_id, comp_info in status_info['components'].items():
                status_emoji = "✅" if comp_info['status'] == 'completed' else "❌" if comp_info['status'] == 'failed' else "⏳"
                error_msg = comp_info.get('error_message', '')[:50] + "..." if len(comp_info.get('error_message', '')) > 50 else comp_info.get('error_message', '')
                
                component_table.add_row(
                    f"{status_emoji} {comp_info['name']}",
                    comp_info['status'],
                    f"{comp_info.get('duration_minutes', 0):.1f} min",
                    error_msg
                )
            
            console.print(component_table)
            
            # Failed components details
            if progress_info['failed_components']:
                console.print(f"\n[bold red]Failed Components ({len(progress_info['failed_components'])}):[/bold red]")
                for comp_id in progress_info['failed_components']:
                    comp_info = status_info['components'][comp_id]
                    console.print(f"  ❌ {comp_info['name']}: {comp_info['error_message']}")
            
            # Next component
            if status_info['next_component']:
                next_comp = status_info['components'][status_info['next_component']]
                console.print(f"\n[bold yellow]Next Component:[/bold yellow] {next_comp['name']}")
                console.print(f"[yellow]Estimated Duration:[/yellow] {next_comp['estimated_duration_minutes']} minutes")
            
            if watch:
                console.print("\n[dim]Press Ctrl+C to exit watch mode[/dim]")
            
        except Exception as e:
            console.print(f"[red]Error getting migration status:[/red] {str(e)}")
            if not watch:
                raise click.ClickException(f"Status retrieval failed: {str(e)}")
    
    if watch:
        try:
            while True:
                display_status()
                time.sleep(5)  # Update every 5 seconds
        except KeyboardInterrupt:
            console.print("\n[yellow]Watch mode stopped[/yellow]")
    else:
        display_status()


@incremental.command()
@click.option('--migration-id', required=True, help='Migration identifier')
@click.option('--output', '-o', type=click.Path(exists=True), required=True, help='Migration artifacts directory')
@click.pass_context
def report(ctx: click.Context, migration_id: str, output: str) -> None:
    """Generate detailed migration status report"""
    click.echo(f"Generating status report for migration: {migration_id}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        output_path = Path(output)
        report = agent.generate_migration_status_report(migration_id, output_path)
        
        click.echo("\n" + "="*60)
        click.echo(report)
        click.echo("="*60)
        
    except Exception as e:
        click.echo(f"Error generating status report: {str(e)}", err=True)
        raise click.ClickException(f"Report generation failed: {str(e)}")


@incremental.command()
@click.argument('component_id')
@click.option('--migration-id', required=True, help='Migration identifier')
@click.option('--output', '-o', type=click.Path(exists=True), required=True, help='Migration artifacts directory')
@click.option('--force', is_flag=True, help='Force execution even if dependencies are not met')
@click.pass_context
def execute(ctx: click.Context, component_id: str, migration_id: str, output: str, force: bool) -> None:
    """Execute a specific migration component"""
    console.print(f"[bold blue]Executing component:[/bold blue] {component_id}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        output_path = Path(output)
        
        # Check dependencies unless forced
        if not force:
            status_info = agent.get_migration_status(migration_id, output_path)
            component_info = status_info['components'].get(component_id)
            
            if not component_info:
                console.print(f"[red]Component '{component_id}' not found in migration plan[/red]")
                return
            
            # Check if dependencies are met
            dependencies = component_info.get('dependencies', [])
            if dependencies:
                console.print(f"[yellow]Checking dependencies:[/yellow] {', '.join(dependencies)}")
                for dep in dependencies:
                    dep_status = status_info['components'].get(dep, {}).get('status')
                    if dep_status != 'completed':
                        console.print(f"[red]Dependency '{dep}' is not completed (status: {dep_status})[/red]")
                        if not confirm_action("Continue anyway?"):
                            return
        
        # Execute component with progress tracking
        with show_progress(f"Executing {component_id}...") as progress:
            task = progress.add_task("Execution", total=100)
            
            progress.update(task, advance=20, description="Preparing component...")
            time.sleep(0.3)
            
            progress.update(task, advance=60, description="Running component logic...")
            result = agent.execute_migration_component(component_id, migration_id, output_path)
            
            progress.update(task, advance=100, description="Component completed")
        
        if result['success']:
            console.print(Panel.fit(
                f"[bold green]Component Executed Successfully![/bold green]\n\n"
                f"⏱️  Duration: {result['duration_minutes']:.1f} minutes\n"
                f"📄 Artifacts: {len(result['artifacts_generated'])} files generated",
                style="green"
            ))
            
            if result['artifacts_generated']:
                console.print("\n[bold yellow]Generated Artifacts:[/bold yellow]")
                for artifact in result['artifacts_generated']:
                    console.print(f"  📄 {artifact}")
        else:
            console.print(Panel("❌ Component Execution Failed", style="red"))
            
    except Exception as e:
        console.print(f"[red]Error executing component:[/red] {str(e)}")
        raise click.ClickException(f"Component execution failed: {str(e)}")


@incremental.command()
@click.argument('component_id')
@click.option('--migration-id', required=True, help='Migration identifier')
@click.option('--output', '-o', type=click.Path(exists=True), required=True, help='Migration artifacts directory')
@click.pass_context
def rollback(ctx: click.Context, component_id: str, migration_id: str, output: str) -> None:
    """Rollback a failed migration component"""
    click.echo(f"Rolling back component: {component_id}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        output_path = Path(output)
        result = agent.rollback_migration_component(component_id, migration_id, output_path)
        
        if result['success']:
            click.echo("✅ Component rollback completed successfully!")
            click.echo(f"Steps executed: {len(result['steps_executed'])}")
        else:
            click.echo("❌ Component rollback failed")
            for error in result['errors']:
                click.echo(f"  - {error}")
                
    except Exception as e:
        click.echo(f"Error during rollback: {str(e)}", err=True)
        raise click.ClickException(f"Rollback failed: {str(e)}")


@incremental.command()
@click.argument('checkpoint_id')
@click.option('--migration-id', required=True, help='Migration identifier')
@click.option('--output', '-o', type=click.Path(exists=True), required=True, help='Migration artifacts directory')
@click.pass_context
def checkpoint(ctx: click.Context, checkpoint_id: str, migration_id: str, output: str) -> None:
    """Validate a migration checkpoint"""
    click.echo(f"Validating checkpoint: {checkpoint_id}")
    
    config = ctx.obj['config']
    agent = MigrationAgent(config)
    
    try:
        output_path = Path(output)
        result = agent.validate_migration_checkpoint(checkpoint_id, migration_id, output_path)
        
        if result['success']:
            click.echo("✅ Checkpoint validation passed!")
            click.echo(f"Criteria validated: {len(result['criteria'])}")
        else:
            click.echo("❌ Checkpoint validation failed")
            for error in result['errors']:
                click.echo(f"  - {error}")
                
    except Exception as e:
        click.echo(f"Error validating checkpoint: {str(e)}", err=True)
        raise click.ClickException(f"Checkpoint validation failed: {str(e)}")


@cli.command('generate-standalone-pipeline')
@click.argument('output_path', type=click.Path())
@click.option('--source-dir', type=click.Path(exists=True), help='Source directory with training code')
@click.option('--role', help='SageMaker execution role ARN')
@click.option('--bucket', help='S3 bucket for artifacts')
@click.option('--accuracy-threshold', type=float, default=0.95, help='Accuracy threshold for model registration')
@click.option('--instance-type', default='ml.m5.large', help='Training instance type')
@click.option('--framework-version', default='2.1.0', help='PyTorch framework version')
@click.option('--processor-type', type=click.Choice(['pytorch', 'sklearn']), default='pytorch', 
              help='Processor type for evaluation step (pytorch or sklearn)')
@click.pass_context
def generate_standalone_pipeline(ctx: click.Context, output_path: str, source_dir: Optional[str], 
                     role: Optional[str], bucket: Optional[str], accuracy_threshold: float,
                     instance_type: str, framework_version: str, processor_type: str) -> None:
    """Generate standalone SageMaker Pipeline with train, evaluate, and conditional register steps"""
    
    # Validate dependencies before generation
    def validate_dependencies():
        """Validate that required packages are available for pipeline generation"""
        try:
            from ..utils.dependency_validator import validate_generation_environment
            if not validate_generation_environment():
                raise click.ClickException("Missing required dependencies for pipeline generation")
        except ImportError:
            # Fallback to simple validation
            required_packages = ['boto3', 'click', 'rich']
            missing_packages = []
            
            for package in required_packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)
            
            if missing_packages:
                console.print(f"[red]❌ Missing required dependencies:[/red]")
                for pkg in missing_packages:
                    console.print(f"   - {pkg}")
                console.print(f"\\n[yellow]📦 Install missing packages:[/yellow]")
                console.print(f"   pip install {' '.join(missing_packages)}")
                raise click.ClickException("Missing required dependencies")
    
    # Check dependencies
    validate_dependencies()
    
    console.print(f"[bold blue]Generating SageMaker Pipeline at:[/bold blue] {output_path}")
    console.print(f"[blue]Processor Type:[/blue] {processor_type}")
    
    config = ctx.obj['config']
    
    try:
        # Use current directory as source if not specified
        if not source_dir:
            source_dir = "."
        
        # Auto-detect role and bucket if not provided
        if not role:
            try:
                # Try to use the role validator for better role discovery
                from ..utils.role_validator import discover_and_select_role
                discovered_role = discover_and_select_role(config.project_name, "us-east-1")
                if discovered_role:
                    role = discovered_role
                    console.print(f"[green]✅ Discovered SageMaker role:[/green] {role}")
                else:
                    # Fallback to account-based role generation
                    import boto3
                    sts = boto3.client('sts')
                    account_id = sts.get_caller_identity()['Account']
                    role = f"arn:aws:iam::{account_id}:role/sagemigrator-project-SageMaker-ExecutionRole-dev"
                    console.print(f"[yellow]⚠️  Using default role pattern:[/yellow] {role}")
                    console.print("[yellow]Note: Role may need to be created. Check the generated README for instructions.[/yellow]")
            except Exception as e:
                # Final fallback
                role = "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
                console.print(f"[red]⚠️  Role discovery failed:[/red] {e}")
                console.print(f"[yellow]Using placeholder role:[/yellow] {role}")
                console.print("[yellow]You'll need to update this with a valid role ARN.[/yellow]")
        
        if not bucket:
            try:
                # Try to use the S3 bucket validator for better bucket setup
                from ..utils.s3_bucket_validator import setup_project_bucket
                discovered_bucket = setup_project_bucket(config.project_name, "us-east-1")
                if discovered_bucket:
                    bucket = discovered_bucket
                    console.print(f"[green]✅ Set up S3 bucket:[/green] {bucket}")
                else:
                    # Fallback to account-based bucket generation
                    import boto3
                    sts = boto3.client('sts')
                    account_id = sts.get_caller_identity()['Account']
                    # Always use us-east-1 as default region for bucket
                    bucket = f"sagemigrator-project-sagemaker-bucket-{account_id}-us-east-1"
                    
                    # Validate bucket name format
                    from .utils.s3_arn_validator import validate_s3_resource_arn
                    bucket_arn = validate_s3_resource_arn(bucket)
                    console.print(f"[yellow]⚠️  Using default bucket pattern:[/yellow] {bucket}")
                    console.print(f"[yellow]Bucket ARN:[/yellow] {bucket_arn}")
                    console.print("[yellow]Note: Bucket may need to be created. Check the generated README for instructions.[/yellow]")
            except Exception as e:
                # Final fallback
                bucket = "sagemaker-default-bucket"
                console.print(f"[red]⚠️  Bucket setup failed:[/red] {e}")
                console.print(f"[yellow]Using placeholder bucket:[/yellow] {bucket}")
                console.print("[yellow]You'll need to update this with a valid bucket name.[/yellow]")
        
        with show_progress("Generating pipeline components...") as progress:
            task = progress.add_task("Generation", total=100)
            
            # Generate pipeline code
            from .pipeline_generator import SageMakerPipelineGenerator
            
            generator = SageMakerPipelineGenerator(
                role=role,
                bucket=bucket,
                accuracy_threshold=accuracy_threshold,
                instance_type=instance_type,
                framework_version=framework_version,
                region="us-east-1",  # Always use us-east-1 as default
                processor_type=processor_type  # Add processor type parameter
            )
            
            progress.update(task, advance=25, description="Analyzing source code...")
            
            # Analyze source directory
            analysis_result = generator.analyze_source_directory(source_dir)
            
            progress.update(task, advance=50, description="Generating pipeline definition...")
            
            # Generate pipeline
            pipeline_code = generator.generate_pipeline()
            
            progress.update(task, advance=75, description="Creating evaluation script...")
            
            # Generate evaluation script based on processor type
            evaluation_script = generator.generate_evaluation_script(processor_type)
            
            progress.update(task, advance=85, description="Creating preprocessing script...")
            
            # Generate preprocessing script
            preprocessing_script = generator.generate_preprocessing_script()
            
            progress.update(task, advance=90, description="Saving files...")
            
            # Create output directory
            output_path_obj = Path(output_path)
            output_path_obj.mkdir(parents=True, exist_ok=True)
            
            # Save pipeline definition
            pipeline_file = output_path_obj / "pipeline.py"
            with open(pipeline_file, 'w') as f:
                f.write(pipeline_code)
            
            # Save evaluation script
            eval_file = output_path_obj / "evaluation.py"
            with open(eval_file, 'w') as f:
                f.write(evaluation_script)
            # Set execute permissions
            eval_file.chmod(0o755)
            
            # Generate and save evaluation wrapper script
            eval_wrapper_script = generator.generate_evaluation_wrapper_script()
            eval_wrapper_file = output_path_obj / "run_evaluation.sh"
            with open(eval_wrapper_file, 'w') as f:
                f.write(eval_wrapper_script)
            # Set execute permissions
            eval_wrapper_file.chmod(0o755)
            
            # Save preprocessing script
            preprocess_file = output_path_obj / "preprocessing.py"
            with open(preprocess_file, 'w') as f:
                f.write(preprocessing_script)
            # Set execute permissions
            preprocess_file.chmod(0o755)
            
            # Generate and save preprocessing wrapper script
            preprocess_wrapper_script = generator.generate_preprocessing_wrapper_script()
            preprocess_wrapper_file = output_path_obj / "run_preprocessing.sh"
            with open(preprocess_wrapper_file, 'w') as f:
                f.write(preprocess_wrapper_script)
            # Set execute permissions
            preprocess_wrapper_file.chmod(0o755)
            
            # Generate deployment script
            deploy_script = generator.generate_deployment_script()
            deploy_file = output_path_obj / "deploy_pipeline.py"
            with open(deploy_file, 'w') as f:
                f.write(deploy_script)
            # Set execute permissions
            deploy_file.chmod(0o755)
            
            # Generate README
            readme_content = generator.generate_readme()
            readme_file = output_path_obj / "README.md"
            with open(readme_file, 'w') as f:
                f.write(readme_content)
            
            progress.update(task, advance=100)
        
        console.print("✅ [green]Pipeline generation completed successfully![/green]")
        
        # Display summary
        console.print(Panel.fit(
            f"[bold green]SageMaker Pipeline Generated![/bold green]\n\n"
            f"📁 Output directory: {output_path}\n"
            f"🔧 Role: {role}\n"
            f"🪣 Bucket: {bucket}\n"
            f"📊 Accuracy threshold: {accuracy_threshold}\n"
            f"💻 Instance type: {instance_type}\n"
            f"🔄 Processor type: {processor_type}\n\n"
            f"Generated files:\n"
            f"  📄 pipeline.py - Main pipeline definition\n"
            f"  📄 preprocessing.py - Data preprocessing script\n"
            f"  📄 evaluation.py - Model evaluation script ({processor_type} processor)\n"
            f"  📄 deploy_pipeline.py - Deployment script\n"
            f"  📄 README.md - Usage instructions",
            style="green"
        ))
        
        console.print("\n[bold yellow]Next steps:[/bold yellow]")
        console.print("1. Review the generated pipeline code")
        console.print("2. Ensure SageMaker SDK v2.x is installed:")
        console.print("   [dim]pip install 'sagemaker>=2.190.0,<3.0.0'[/dim]")
        console.print("3. Customize parameters if needed")
        console.print(f"4. Deploy: python {output_path}/deploy_pipeline.py")
        console.print(f"5. Execute: python {output_path}/pipeline.py")
        
        console.print("\n[bold cyan]💡 Tip:[/bold cyan] Generated pipelines include automatic dependency validation")
        
    except Exception as e:
        console.print(f"[red]Error generating pipeline:[/red] {str(e)}")
        raise click.ClickException(f"Pipeline generation failed: {str(e)}")


@cli.command()
@click.option('--topic', type=click.Choice(['migration', 'validation', 'deployment', 'troubleshooting']), 
              help='Specific help topic')
def help_guide(topic: Optional[str]) -> None:
    """Show detailed help and best practices guide"""
    
    if topic == 'migration':
        console.print(Panel.fit(
            "[bold blue]Migration Best Practices[/bold blue]\n\n"
            "1. [yellow]Pre-Migration Analysis[/yellow]\n"
            "   • Run analysis first: sagemigrator analyze <source>\n"
            "   • Review compatibility issues\n"
            "   • Check dependency conflicts\n\n"
            "2. [yellow]Migration Process[/yellow]\n"
            "   • Use interactive mode: sagemigrator migrate -i <source> -o <output>\n"
            "   • Start with dry-run to preview changes\n"
            "   • Validate artifacts before deployment\n\n"
            "3. [yellow]Testing[/yellow]\n"
            "   • Run local tests first\n"
            "   • Use incremental migration for complex projects\n"
            "   • Test with small datasets initially",
            style="blue"
        ))
    
    elif topic == 'validation':
        console.print(Panel.fit(
            "[bold blue]Validation Guide[/bold blue]\n\n"
            "1. [yellow]Validation Types[/yellow]\n"
            "   • Code compatibility checks\n"
            "   • Infrastructure validation\n"
            "   • Security best practices\n"
            "   • Production readiness assessment\n\n"
            "2. [yellow]Common Issues[/yellow]\n"
            "   • Missing IAM permissions\n"
            "   • Incompatible package versions\n"
            "   • Resource naming conflicts\n"
            "   • Region-specific limitations\n\n"
            "3. [yellow]Resolution Steps[/yellow]\n"
            "   • Check validation report details\n"
            "   • Fix high-priority issues first\n"
            "   • Use --detailed flag for more info",
            style="blue"
        ))
    
    elif topic == 'deployment':
        console.print(Panel.fit(
            "[bold blue]Deployment Guide[/bold blue]\n\n"
            "1. [yellow]Pre-Deployment[/yellow]\n"
            "   • Validate artifacts thoroughly\n"
            "   • Check AWS credentials and permissions\n"
            "   • Verify target region availability\n\n"
            "2. [yellow]Deployment Process[/yellow]\n"
            "   • Use dry-run first: sagemigrator deploy --dry-run\n"
            "   • Monitor CloudFormation stack creation\n"
            "   • Check CloudWatch logs for issues\n\n"
            "3. [yellow]Post-Deployment[/yellow]\n"
            "   • Test SageMaker pipeline execution\n"
            "   • Verify endpoint functionality\n"
            "   • Set up monitoring and alerts",
            style="blue"
        ))
    
    elif topic == 'troubleshooting':
        console.print(Panel.fit(
            "[bold blue]Troubleshooting Guide[/bold blue]\n\n"
            "1. [yellow]Common Errors[/yellow]\n"
            "   • Import errors: Check requirements.txt\n"
            "   • Permission denied: Verify IAM roles\n"
            "   • Resource limits: Check service quotas\n"
            "   • Timeout errors: Increase max_run parameter\n\n"
            "2. [yellow]Debugging Steps[/yellow]\n"
            "   • Enable verbose logging: -v flag\n"
            "   • Check CloudWatch logs\n"
            "   • Review validation report\n"
            "   • Use incremental migration for isolation\n\n"
            "3. [yellow]Getting Help[/yellow]\n"
            "   • Check documentation\n"
            "   • Review error messages carefully\n"
            "   • Use diagnostic utilities",
            style="blue"
        ))
    
    else:
        # General help
        console.print(Panel.fit(
            "[bold blue]SageMigrator Help Guide[/bold blue]\n\n"
            "[yellow]Quick Start:[/yellow]\n"
            "1. sagemigrator analyze <source-path>\n"
            "2. sagemigrator migrate <source-path> -o <output-path>\n"
            "3. sagemigrator validate <output-path>\n"
            "4. sagemigrator deploy <output-path>\n"
            "5. sagemigrator execute <pipeline-path>\n\n"
            "[yellow]Available Topics:[/yellow]\n"
            "• migration - Migration best practices\n"
            "• validation - Validation and troubleshooting\n"
            "• deployment - Deployment procedures\n"
            "• troubleshooting - Common issues and solutions\n\n"
            "[yellow]Examples:[/yellow]\n"
            "sagemigrator help-guide --topic migration\n"
            "sagemigrator help-guide --topic validation\n"
            "sagemigrator execute pipeline.py --capture-output\n"
            "sagemigrator execute pipeline.py -e AWS_REGION=us-west-2",
            style="blue"
        ))


@cli.command()
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table')
def version(output_format: str) -> None:
    """Show version information and system status"""
    
    version_info = {
        "sagemigrator_version": "1.0.0",
        "python_version": "3.8+",
        "supported_frameworks": ["PyTorch", "TensorFlow", "Scikit-learn"],
        "aws_regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
        "features": [
            "Code Analysis",
            "SDK v3 Compatibility", 
            "TorchScript Support",
            "Infrastructure Generation",
            "Incremental Migration",
            "Production Validation"
        ]
    }
    
    if output_format == 'json':
        import json
        console.print(json.dumps(version_info, indent=2))
    else:
        console.print(Panel.fit(
            f"[bold blue]SageMigrator v{version_info['sagemigrator_version']}[/bold blue]\n\n"
            f"[yellow]Python:[/yellow] {version_info['python_version']}\n"
            f"[yellow]Frameworks:[/yellow] {', '.join(version_info['supported_frameworks'])}\n"
            f"[yellow]AWS Regions:[/yellow] {', '.join(version_info['aws_regions'])}\n\n"
            f"[yellow]Features:[/yellow]\n" + 
            "\n".join(f"  ✓ {feature}" for feature in version_info['features']),
            title="Version Information",
            style="blue"
        ))

@cli.command()
@click.argument('pipeline_path', type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option('--working-dir', '-w', type=click.Path(exists=True, file_okay=False, dir_okay=True), 
              help='Working directory to run the pipeline from (defaults to pipeline file directory)')
@click.option('--env-vars', '-e', multiple=True, 
              help='Environment variables to set (format: KEY=VALUE)')
@click.option('--timeout', '-t', type=int, default=3600, 
              help='Timeout in seconds for pipeline execution (default: 3600)')
@click.option('--capture-output', is_flag=True, 
              help='Capture and display pipeline output in real-time')
@click.pass_context
def execute(ctx: click.Context, pipeline_path: str, working_dir: Optional[str], 
           env_vars: tuple, timeout: int, capture_output: bool) -> None:
    """Execute a SageMaker training pipeline.py file"""
    
    import subprocess
    import os
    import sys
    from pathlib import Path
    
    pipeline_file = Path(pipeline_path)
    console.print(f"[bold blue]Executing SageMaker pipeline:[/bold blue] {pipeline_file}")
    
    # Determine working directory
    if working_dir:
        work_dir = Path(working_dir)
    else:
        work_dir = pipeline_file.parent
    
    console.print(f"[blue]Working directory:[/blue] {work_dir}")
    
    # Parse environment variables
    env = os.environ.copy()
    for env_var in env_vars:
        if '=' not in env_var:
            console.print(f"[red]Invalid environment variable format:[/red] {env_var}")
            console.print("[yellow]Use format: KEY=VALUE[/yellow]")
            raise click.ClickException(f"Invalid environment variable: {env_var}")
        
        key, value = env_var.split('=', 1)
        env[key] = value
        console.print(f"[green]Set environment variable:[/green] {key}={value}")
    
    # Validate pipeline file
    if not pipeline_file.name.endswith('.py'):
        console.print(f"[red]Error:[/red] Pipeline file must be a Python file (.py)")
        raise click.ClickException(f"Invalid file type: {pipeline_file}")
    
    # Check if file contains SageMaker pipeline code
    try:
        with open(pipeline_file, 'r') as f:
            content = f.read()
            
        # Basic validation for SageMaker pipeline
        sagemaker_indicators = [
            'sagemaker',
            'Pipeline',
            'TrainingStep',
            'ProcessingStep'
        ]
        
        found_indicators = [indicator for indicator in sagemaker_indicators if indicator in content]
        
        if not found_indicators:
            console.print("[yellow]Warning:[/yellow] File doesn't appear to contain SageMaker pipeline code")
            if not click.confirm("Continue anyway?"):
                console.print("[yellow]Execution cancelled by user[/yellow]")
                return
        else:
            console.print(f"[green]✓ Detected SageMaker components:[/green] {', '.join(found_indicators)}")
            
    except Exception as e:
        console.print(f"[red]Error reading pipeline file:[/red] {e}")
        raise click.ClickException(f"Failed to read pipeline file: {e}")
    
    # Prepare execution command
    python_executable = sys.executable
    cmd = [python_executable, str(pipeline_file.name)]
    
    console.print(f"[blue]Command:[/blue] {' '.join(cmd)}")
    console.print(f"[blue]Timeout:[/blue] {timeout} seconds")
    
    if ctx.obj['verbose']:
        console.print(f"[dim]Full command: {' '.join(cmd)}[/dim]")
        console.print(f"[dim]Environment variables: {len(env_vars)} custom vars[/dim]")
    
    try:
        # Execute the pipeline
        console.print("\n[bold green]Starting pipeline execution...[/bold green]")
        
        if capture_output:
            # Real-time output capture
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Stream output in real-time
            try:
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())
                
                # Wait for process to complete
                return_code = process.wait(timeout=timeout)
                
            except subprocess.TimeoutExpired:
                process.kill()
                console.print(f"\n[red]❌ Pipeline execution timed out after {timeout} seconds[/red]")
                raise click.ClickException(f"Pipeline execution timed out")
                
        else:
            # Execute without real-time output
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return_code = result.returncode
            
            # Display output
            if result.stdout:
                console.print("\n[bold yellow]Pipeline Output:[/bold yellow]")
                console.print(result.stdout)
            
            if result.stderr:
                console.print("\n[bold red]Pipeline Errors:[/bold red]")
                console.print(result.stderr)
        
        # Check execution result
        if return_code == 0:
            console.print(Panel.fit(
                "[bold green]✅ Pipeline executed successfully![/bold green]\n\n"
                f"📁 Pipeline: {pipeline_file.name}\n"
                f"📂 Working directory: {work_dir}\n"
                f"⏱️  Execution completed\n\n"
                "Next steps:\n"
                "• Check SageMaker console for pipeline execution status\n"
                "• Monitor CloudWatch logs for detailed execution logs\n"
                "• Review any generated artifacts in S3",
                style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[bold red]❌ Pipeline execution failed![/bold red]\n\n"
                f"📁 Pipeline: {pipeline_file.name}\n"
                f"📂 Working directory: {work_dir}\n"
                f"🔢 Exit code: {return_code}\n\n"
                "Troubleshooting:\n"
                "• Check the error output above\n"
                "• Verify AWS credentials and permissions\n"
                "• Ensure all dependencies are installed\n"
                "• Check SageMaker service quotas and limits",
                style="red"
            ))
            raise click.ClickException(f"Pipeline execution failed with exit code {return_code}")
            
    except subprocess.TimeoutExpired:
        console.print(f"\n[red]❌ Pipeline execution timed out after {timeout} seconds[/red]")
        raise click.ClickException(f"Pipeline execution timed out")
        
    except FileNotFoundError:
        console.print(f"[red]❌ Python executable not found:[/red] {python_executable}")
        raise click.ClickException(f"Python executable not found")
        
    except Exception as e:
        console.print(f"[red]❌ Unexpected error during execution:[/red] {str(e)}")
        raise click.ClickException(f"Pipeline execution failed: {str(e)}")


if __name__ == '__main__':
    cli()