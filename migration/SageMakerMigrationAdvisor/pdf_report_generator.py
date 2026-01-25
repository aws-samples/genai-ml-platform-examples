"""
PDF Report Generator Component for SageMaker Migration Advisor
Generates comprehensive PDF migration reports with embedded diagrams
"""

import os
from typing import Dict, Any, Optional, List
from io import BytesIO
from logger_config import logger


class PDFReportGenerator:
    """Generates comprehensive PDF migration reports"""
    
    def __init__(self, workflow_state: Dict[str, Any], diagram_folder: str, model_name: str = "Claude AI"):
        """
        Initialize PDFReportGenerator
        
        Args:
            workflow_state: Complete workflow state with all agent responses
            diagram_folder: Path to folder containing generated diagrams
            model_name: Name of the AI model used for generation
        """
        self.workflow_state = workflow_state
        self.diagram_folder = diagram_folder
        self.model_name = model_name
    
    def generate_report(self) -> Optional[bytes]:
        """
        Generate complete PDF report
        
        Returns:
            PDF bytes if successful, None if failed
        """
        try:
            # Import reportlab components
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                Table, TableStyle
            )
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            import datetime
            
            logger.info("Starting PDF report generation")
            
            # Create PDF buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Get and customize styles
            styles = self._create_styles(getSampleStyleSheet())
            story = []
            
            # Build report sections
            logger.info("Adding title page")
            self._add_title_page(story, styles)
            
            logger.info("Adding table of contents")
            self._add_table_of_contents(story, styles)
            
            logger.info("Adding executive summary")
            self._add_executive_summary(story, styles)
            
            logger.info("Adding architecture analysis")
            self._add_architecture_analysis(story, styles)
            
            logger.info("Adding Q&A section")
            self._add_qa_section(story, styles)
            
            logger.info("Adding SageMaker design")
            self._add_sagemaker_design(story, styles)
            
            logger.info("Adding diagrams")
            self._add_diagrams(story, styles)
            
            logger.info("Adding TCO analysis")
            self._add_tco_analysis(story, styles)
            
            logger.info("Adding migration roadmap")
            self._add_migration_roadmap(story, styles)
            
            logger.info("Adding implementation recommendations")
            self._add_implementation_recommendations(story, styles)
            
            # Build PDF
            logger.info("Building PDF document")
            doc.build(story)
            buffer.seek(0)
            
            pdf_bytes = buffer.getvalue()
            logger.info(f"PDF generated successfully ({len(pdf_bytes):,} bytes)")
            
            return pdf_bytes
            
        except ImportError as e:
            logger.error(f"Missing reportlab dependency: {e}")
            return None
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            return None
    
    def _create_styles(self, base_styles) -> Dict:
        """Create custom PDF styles"""
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.styles import ParagraphStyle
        
        return {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#2E86AB')
            ),
            'heading': ParagraphStyle(
                'CustomHeading',
                parent=base_styles['Heading2'],
                fontSize=16,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#FF6B35')
            ),
            'subheading': ParagraphStyle(
                'CustomSubHeading',
                parent=base_styles['Heading3'],
                fontSize=14,
                spaceAfter=8,
                spaceBefore=12,
                textColor=colors.HexColor('#2E86AB')
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=base_styles['Normal'],
                fontSize=11,
                spaceAfter=8,
                alignment=TA_JUSTIFY
            )
        }
    
    def _add_title_page(self, story: List, styles: Dict):
        """Add title page to PDF"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        import datetime
        
        story.append(Paragraph("SageMaker Migration Advisory Report", styles['title']))
        story.append(Spacer(1, 0.5*inch))
        
        # Executive summary table
        exec_data = [
            ['Report Generated', datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')],
            ['AI Model Used', self.model_name],
            ['Analysis Scope', 'Complete Architecture Migration Assessment'],
            ['Report Status', 'Ready for Implementation']
        ]
        
        exec_table = Table(exec_data, colWidths=[2*inch, 3*inch])
        exec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DEE2E6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(exec_table)
        story.append(PageBreak())
    
    def _add_table_of_contents(self, story: List, styles: Dict):
        """Add table of contents"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("Table of Contents", styles['heading']))
        toc_data = [
            "1. Executive Summary",
            "2. Current Architecture Analysis",
            "3. Clarification Questions & Answers",
            "4. Proposed SageMaker Architecture",
            "   4.1 Architecture Design",
            "   4.2 Architecture Diagrams",
            "5. Total Cost of Ownership Analysis",
            "6. Migration Roadmap",
            "7. Implementation Recommendations",
            "8. Appendices"
        ]
        
        for item in toc_data:
            story.append(Paragraph(item, styles['body']))
        
        story.append(PageBreak())
    
    def _add_executive_summary(self, story: List, styles: Dict):
        """Add executive summary section"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("1. Executive Summary", styles['heading']))
        
        completed_steps = len(self.workflow_state.get('completed_steps', []))
        
        summary_text = f"""
        This comprehensive migration advisory report provides a detailed analysis and roadmap for migrating your current 
        ML/GenAI architecture to Amazon SageMaker. The assessment includes {completed_steps} completed analysis phases, 
        covering current state architecture, clarification requirements, proposed SageMaker design, cost analysis, 
        and a detailed implementation roadmap.
        <br/><br/>
        <b>Key Findings:</b><br/>
        • Current architecture has been thoroughly analyzed and documented<br/>
        • Migration requirements and constraints have been clarified through interactive Q&A<br/>
        • A modern SageMaker-based architecture has been designed to address current limitations<br/>
        • Total cost of ownership analysis shows projected benefits and investment requirements<br/>
        • A step-by-step migration roadmap provides clear implementation guidance<br/><br/>
        
        <b>Recommendation:</b><br/>
        Proceed with the proposed SageMaker migration following the detailed roadmap provided in this report. 
        The migration will improve scalability, reduce operational overhead, and provide better ML lifecycle management.
        """
        
        story.append(Paragraph(summary_text, styles['body']))
        story.append(PageBreak())
    
    def _add_architecture_analysis(self, story: List, styles: Dict):
        """Add current architecture analysis section"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("2. Current Architecture Analysis", styles['heading']))
        
        arch_response = self.workflow_state['agent_responses'].get('description', {})
        if arch_response:
            story.append(Paragraph("2.1 Architecture Overview", styles['subheading']))
            
            analysis_text = str(arch_response.get('output', 'No architecture analysis available.'))
            analysis_text = analysis_text.replace('\n', '<br/>')
            
            story.append(Paragraph(analysis_text, styles['body']))
        else:
            story.append(Paragraph("No architecture analysis data available.", styles['body']))
        
        story.append(PageBreak())
    
    def _add_qa_section(self, story: List, styles: Dict):
        """Add Q&A section to PDF"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        from reportlab.lib.units import inch
        
        story.append(Paragraph("3. Clarification Questions & Answers", styles['heading']))
        
        qa_session = self.workflow_state.get('qa_session', {})
        qa_response = self.workflow_state['agent_responses'].get('qa', {})
        
        if qa_session and qa_session.get('conversation', []):
            story.append(Paragraph("3.1 Interactive Q&A Session", styles['subheading']))
            
            for i, exchange in enumerate(qa_session['conversation']):
                story.append(Paragraph(f"<b>Question {i+1}:</b>", styles['subheading']))
                question_text = exchange.get('question', '').replace('\n', '<br/>')
                story.append(Paragraph(question_text, styles['body']))
                
                story.append(Paragraph(f"<b>Answer {i+1}:</b>", styles['subheading']))
                answer_text = exchange.get('answer', 'No answer provided').replace('\n', '<br/>')
                story.append(Paragraph(answer_text, styles['body']))
                
                if exchange.get('synthesis'):
                    story.append(Paragraph(f"<b>AI Understanding:</b>", styles['subheading']))
                    synthesis_text = exchange.get('synthesis', '').replace('\n', '<br/>')
                    story.append(Paragraph(f"✓ {synthesis_text}", styles['body']))
                
                story.append(Spacer(1, 0.2*inch))
        
        if qa_response:
            story.append(Paragraph("3.2 Comprehensive Analysis", styles['subheading']))
            final_analysis = str(qa_response.get('output', '')).replace('\n', '<br/>')
            story.append(Paragraph(final_analysis, styles['body']))
        
        story.append(PageBreak())
    
    def _add_sagemaker_design(self, story: List, styles: Dict):
        """Add SageMaker design section"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("4. Proposed SageMaker Architecture", styles['heading']))
        
        sagemaker_response = self.workflow_state['agent_responses'].get('sagemaker', {})
        if sagemaker_response:
            story.append(Paragraph("4.1 Architecture Design", styles['subheading']))
            
            design_text = str(sagemaker_response.get('output', 'No SageMaker design available.')).replace('\n', '<br/>')
            story.append(Paragraph(design_text, styles['body']))
        else:
            story.append(Paragraph("No SageMaker architecture design available.", styles['body']))
        
        story.append(PageBreak())
    
    def _add_diagrams(self, story: List, styles: Dict):
        """Add architecture diagrams with robust error handling"""
        from reportlab.platypus import Paragraph, Spacer, Image as RLImage
        from reportlab.lib.units import inch
        from PIL import Image
        
        story.append(Paragraph("4.2 Architecture Diagrams", styles['subheading']))
        
        # Check if diagram folder exists
        if not os.path.exists(self.diagram_folder):
            logger.warning(f"Diagram folder not found: {self.diagram_folder}")
            story.append(Paragraph(
                "No diagrams folder found. Diagrams may not have been generated.",
                styles['body']
            ))
            return
        
        # Get list of diagram files
        diagram_files = [
            f for f in os.listdir(self.diagram_folder)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ]
        
        if not diagram_files:
            logger.info("No diagram files found in folder")
            story.append(Paragraph(
                "No diagram files found in the diagrams folder.",
                styles['body']
            ))
            return
        
        logger.info(f"Found {len(diagram_files)} diagram file(s) to embed")
        
        # Limit to 4 diagrams to avoid PDF bloat
        for idx, diagram_file in enumerate(diagram_files[:4], 1):
            try:
                img_path = os.path.join(self.diagram_folder, diagram_file)
                
                # Verify file exists and has content
                if not os.path.exists(img_path):
                    logger.warning(f"Diagram file not found: {diagram_file}")
                    continue
                
                file_size = os.path.getsize(img_path)
                if file_size == 0:
                    logger.warning(f"Skipping empty file: {diagram_file}")
                    continue
                
                logger.info(f"Embedding diagram {idx}: {diagram_file} ({file_size:,} bytes)")
                
                # Open with PIL to get dimensions and verify it's a valid image
                try:
                    pil_img = Image.open(img_path)
                    img_width, img_height = pil_img.size
                    logger.debug(f"Image dimensions: {img_width}x{img_height}")
                except Exception as e:
                    logger.error(f"Failed to open image with PIL: {e}")
                    story.append(Paragraph(
                        f"<i>Note: Could not process {diagram_file} - invalid image format</i>",
                        styles['body']
                    ))
                    continue
                
                # Calculate dimensions to fit on page (max 6 inches wide, 4 inches high)
                max_width = 6 * inch
                max_height = 4 * inch
                
                # Calculate aspect ratio
                aspect_ratio = img_width / img_height
                
                # Determine display dimensions while maintaining aspect ratio
                if img_width > img_height:
                    # Landscape orientation
                    display_width = min(max_width, img_width)
                    display_height = display_width / aspect_ratio
                    
                    # Ensure height doesn't exceed max
                    if display_height > max_height:
                        display_height = max_height
                        display_width = display_height * aspect_ratio
                else:
                    # Portrait orientation
                    display_height = min(max_height, img_height)
                    display_width = display_height * aspect_ratio
                    
                    # Ensure width doesn't exceed max
                    if display_width > max_width:
                        display_width = max_width
                        display_height = display_width / aspect_ratio
                
                logger.debug(f"Display dimensions: {display_width/inch:.2f}x{display_height/inch:.2f} inches")
                
                # Verify aspect ratio is preserved (within 1% tolerance)
                original_ratio = img_width / img_height
                display_ratio = display_width / display_height
                ratio_diff = abs(original_ratio - display_ratio) / original_ratio
                
                if ratio_diff > 0.01:
                    logger.warning(f"Aspect ratio deviation: {ratio_diff*100:.2f}%")
                
                # Add diagram title
                diagram_title = diagram_file.replace('_', ' ').replace('.png', '').replace('.jpg', '').replace('.jpeg', '').title()
                story.append(Paragraph(
                    f"<b>Diagram {idx}: {diagram_title}</b>",
                    styles['subheading']
                ))
                
                # Add the image
                rl_img = RLImage(img_path, width=display_width, height=display_height)
                story.append(rl_img)
                story.append(Spacer(1, 0.2 * inch))
                
                # Add caption
                story.append(Paragraph(
                    f"<i>Figure {idx}: {diagram_title}</i>",
                    styles['body']
                ))
                story.append(Spacer(1, 0.3 * inch))
                
                logger.info(f"Successfully embedded diagram {idx}")
                
            except Exception as e:
                logger.error(f"Failed to embed diagram {diagram_file}: {e}", exc_info=True)
                story.append(Paragraph(
                    f"<i>Note: Could not embed {diagram_file} - {str(e)}</i>",
                    styles['body']
                ))
                story.append(Spacer(1, 0.1 * inch))
        
        # Note about additional diagrams
        if len(diagram_files) > 4:
            story.append(Paragraph(
                f"<i>Note: {len(diagram_files) - 4} additional diagram(s) available in the generated-diagrams folder.</i>",
                styles['body']
            ))
            logger.info(f"Skipped {len(diagram_files) - 4} additional diagrams")
        
        story.append(Spacer(1, 0.2 * inch))
    
    def _add_tco_analysis(self, story: List, styles: Dict):
        """Add TCO analysis section"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("5. Total Cost of Ownership Analysis", styles['heading']))
        
        tco_response = self.workflow_state['agent_responses'].get('tco', {})
        if tco_response:
            story.append(Paragraph("5.1 Cost Analysis", styles['subheading']))
            
            tco_text = str(tco_response.get('output', 'No TCO analysis available.')).replace('\n', '<br/>')
            story.append(Paragraph(tco_text, styles['body']))
        else:
            story.append(Paragraph("No TCO analysis data available.", styles['body']))
        
        story.append(PageBreak())
    
    def _add_migration_roadmap(self, story: List, styles: Dict):
        """Add migration roadmap section"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("6. Migration Roadmap", styles['heading']))
        
        navigator_response = self.workflow_state['agent_responses'].get('navigator', {})
        if navigator_response:
            story.append(Paragraph("6.1 Implementation Steps", styles['subheading']))
            
            roadmap_text = str(navigator_response.get('output', 'No migration roadmap available.')).replace('\n', '<br/>')
            story.append(Paragraph(roadmap_text, styles['body']))
        else:
            story.append(Paragraph("No migration roadmap data available.", styles['body']))
        
        story.append(PageBreak())
    
    def _add_implementation_recommendations(self, story: List, styles: Dict):
        """Add implementation recommendations"""
        from reportlab.platypus import Paragraph, Spacer
        
        story.append(Paragraph("7. Implementation Recommendations", styles['heading']))
        
        recommendations = """
        <b>7.1 Pre-Migration Checklist</b><br/>
        • Ensure all team members have appropriate AWS training<br/>
        • Set up development and testing environments<br/>
        • Establish backup and rollback procedures<br/>
        • Create detailed project timeline with milestones<br/>
        • Identify and mitigate potential risks<br/><br/>
        
        <b>7.2 Success Criteria</b><br/>
        • All ML models successfully migrated to SageMaker<br/>
        • Performance metrics meet or exceed current benchmarks<br/>
        • Cost targets achieved as outlined in TCO analysis<br/>
        • Team productivity maintained or improved<br/>
        • Security and compliance requirements satisfied<br/><br/>
        
        <b>7.3 Post-Migration Activities</b><br/>
        • Monitor system performance and costs<br/>
        • Optimize resource utilization<br/>
        • Implement advanced SageMaker features<br/>
        • Conduct team training on new workflows<br/>
        • Document lessons learned and best practices<br/><br/>
        
        <b>7.4 Support and Resources</b><br/>
        • AWS Support: Consider upgrading to Business or Enterprise support<br/>
        • AWS Professional Services: Engage for complex migration scenarios<br/>
        • AWS Training: Enroll team in SageMaker certification programs<br/>
        • Community: Join AWS ML community forums and user groups
        """
        
        story.append(Paragraph(recommendations, styles['body']))
