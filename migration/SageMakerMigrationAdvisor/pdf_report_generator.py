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
        """Add current architecture analysis section with proper markdown cleaning"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("2. Current Architecture Analysis", styles['heading']))
        
        arch_response = self.workflow_state['agent_responses'].get('description', {})
        if arch_response:
            story.append(Paragraph("2.1 Architecture Overview", styles['subheading']))
            
            analysis_text = str(arch_response.get('output', 'No architecture analysis available.'))
            
            # Clean markdown artifacts
            analysis_text = self._clean_markdown_for_pdf(analysis_text)
            
            # Parse and format the content properly
            self._parse_and_format_content(analysis_text, story, styles)
        else:
            story.append(Paragraph("No architecture analysis data available.", styles['body']))
        
        story.append(PageBreak())
    
    def _add_qa_section(self, story: List, styles: Dict):
        """Add Q&A section to PDF with proper markdown cleaning"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        from reportlab.lib.units import inch
        
        story.append(Paragraph("3. Clarification Questions & Answers", styles['heading']))
        
        qa_session = self.workflow_state.get('qa_session', {})
        qa_response = self.workflow_state['agent_responses'].get('qa', {})
        
        if qa_session and qa_session.get('conversation', []):
            story.append(Paragraph("3.1 Interactive Q&A Session", styles['subheading']))
            
            for i, exchange in enumerate(qa_session['conversation']):
                story.append(Paragraph(f"<b>Question {i+1}:</b>", styles['subheading']))
                question_text = exchange.get('question', '')
                question_text = self._clean_markdown_for_pdf(question_text)
                self._parse_and_format_content(question_text, story, styles)
                
                story.append(Paragraph(f"<b>Answer {i+1}:</b>", styles['subheading']))
                answer_text = exchange.get('answer', 'No answer provided')
                answer_text = self._clean_markdown_for_pdf(answer_text)
                self._parse_and_format_content(answer_text, story, styles)
                
                if exchange.get('synthesis'):
                    story.append(Paragraph(f"<b>AI Understanding:</b>", styles['subheading']))
                    synthesis_text = exchange.get('synthesis', '')
                    synthesis_text = self._clean_markdown_for_pdf(synthesis_text)
                    story.append(Paragraph(f"✓ {synthesis_text}", styles['body']))
                
                story.append(Spacer(1, 0.2*inch))
        
        if qa_response:
            story.append(Paragraph("3.2 Comprehensive Analysis", styles['subheading']))
            final_analysis = str(qa_response.get('output', ''))
            final_analysis = self._clean_markdown_for_pdf(final_analysis)
            self._parse_and_format_content(final_analysis, story, styles)
        
        story.append(PageBreak())
    
    def _add_sagemaker_design(self, story: List, styles: Dict):
        """Add SageMaker design section with proper markdown cleaning"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("4. Proposed SageMaker Architecture", styles['heading']))
        
        sagemaker_response = self.workflow_state['agent_responses'].get('sagemaker', {})
        if sagemaker_response:
            story.append(Paragraph("4.1 Architecture Design", styles['subheading']))
            
            design_text = str(sagemaker_response.get('output', 'No SageMaker design available.'))
            
            # Clean markdown artifacts before converting to PDF
            design_text = self._clean_markdown_for_pdf(design_text)
            
            # Parse and format the content properly
            self._parse_and_format_content(design_text, story, styles)
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
        """Add TCO analysis section with properly formatted tables"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        import re
        
        story.append(Paragraph("5. Total Cost of Ownership Analysis", styles['heading']))
        
        tco_response = self.workflow_state['agent_responses'].get('tco', {})
        if not tco_response:
            story.append(Paragraph("No TCO analysis data available.", styles['body']))
            story.append(PageBreak())
            return
        
        story.append(Paragraph("5.1 Cost Analysis", styles['subheading']))
        
        tco_text = str(tco_response.get('output', 'No TCO analysis available.'))
        
        # Parse and format the TCO content
        self._parse_and_format_tco_content(tco_text, story, styles)
        
        story.append(PageBreak())
    
    def _clean_markdown_for_pdf(self, text: str) -> str:
        """Clean markdown artifacts and normalize text for PDF generation"""
        import re
        
        # DON'T remove code block markers - we'll handle them in parsing
        # Code blocks will be detected and formatted specially
        
        # Remove emojis - these render as ■ in PDFs
        # This is a comprehensive emoji removal that handles:
        # - Basic emojis (U+1F300-U+1F9FF)
        # - Miscellaneous Symbols (U+2600-U+26FF) including ✅ ❌
        # - Dingbats (U+2700-U+27BF)
        # - Variation selectors (U+FE00-U+FE0F) that modify emojis
        # - Emoji modifiers and components
        text = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\uFE00-\uFE0F\U0001F1E0-\U0001F1FF\U0001FA70-\U0001FAFF]+', '', text)
        
        # Remove ALL box drawing characters, bullets, and special symbols
        # Including Unicode ranges for box drawing (U+2500-U+257F) and geometric shapes (U+25A0-U+25FF)
        text = re.sub(r'[\u2500-\u257F\u25A0-\u25FF\u2190-\u21FF]', '', text)
        
        # Also remove specific problematic characters
        text = re.sub(r'[■□▪▫●○◆◇★☆✓✗✘]', '', text)
        
        # DO NOT remove markdown table separator lines here!
        # The _add_formatted_table method needs them to identify headers correctly
        # text = re.sub(r'^\|[\s\-:]+\|[\s\-:|]+$', '', text, flags=re.MULTILINE)
        
        # Remove lines that are just dashes or equals (markdown separators)
        # But NOT table separators (which contain |)
        text = re.sub(r'^[-=]{3,}$', '', text, flags=re.MULTILINE)
        
        # Remove HTML-style comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # Remove bracket notation like [Data Scientists] that are part of diagrams
        text = re.sub(r'\[([^\]]+)\]\s*\n', r'\1\n', text)
        
        # Keep # for headings but remove from other places
        # Process line by line to preserve heading markers
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # If line starts with # and space/another #, it's a heading - keep it
            if stripped.startswith('#') and len(stripped) > 1 and (stripped[1] == ' ' or stripped[1] == '#'):
                cleaned_lines.append(line)
            else:
                # Remove # from non-heading lines
                cleaned_lines.append(line.replace('#', ''))
        text = '\n'.join(cleaned_lines)
        
        # Fix hard line breaks within paragraphs
        # Split into lines and process
        lines = text.split('\n')
        cleaned_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # Skip empty lines - preserve them
            if not line:
                cleaned_lines.append('')
                i += 1
                continue
            
            # Identify lines that should NOT be joined:
            # 1. Headers (start with #)
            # 2. Bullet points (start with •, -, *)
            # 3. Table rows (contain |)
            # 4. Lines ending with punctuation or special markers
            is_header = line.startswith('#')
            is_bullet = line.lstrip().startswith(('•', '- ', '* '))
            is_table = '|' in line
            ends_properly = line.endswith(('.', '!', '?', ')', '"', '**', ':', ','))
            
            if is_header or is_bullet or is_table:
                cleaned_lines.append(line)
                i += 1
                continue
            
            # For regular text lines, join with next line if it's a continuation
            if not ends_properly and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Check if next line is a continuation (not a header, bullet, or table)
                if next_line and not next_line.startswith(('#', '•', '-', '*', '|')):
                    # Join lines
                    combined = line + ' ' + next_line
                    i += 2
                    
                    # Keep joining while we have continuations
                    while i < len(lines):
                        current = lines[i].strip()
                        if not current:
                            break
                        if current.startswith(('#', '•', '-', '*', '|')):
                            break
                        if combined.endswith(('.', '!', '?', ')', '"', '**', ':')):
                            break
                        combined = combined + ' ' + current
                        i += 1
                    
                    cleaned_lines.append(combined)
                else:
                    cleaned_lines.append(line)
                    i += 1
            else:
                cleaned_lines.append(line)
                i += 1
        
        text = '\n'.join(cleaned_lines)
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Clean up multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove empty lines with only whitespace
        text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)
        
        # Remove trailing spaces
        text = re.sub(r' +$', '', text, flags=re.MULTILINE)
        
        # Final pass: ensure no more than 2 consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _parse_and_format_content(self, content: str, story: List, styles: Dict):
        """Parse and format markdown content for PDF with proper structure"""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import inch
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        import re
        
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines but add spacing
            if not line:
                story.append(Spacer(1, 0.1*inch))
                i += 1
                continue
            
            # Check for code blocks (```)
            if line.startswith('```'):
                # Extract code block
                code_lines = []
                language = line[3:].strip()  # Get language if specified
                i += 1  # Skip opening ```
                
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                if i < len(lines):
                    i += 1  # Skip closing ```
                
                # Add code block to PDF using a table with gray background
                if code_lines:
                    # Create a custom style for code with better wrapping
                    code_para_style = ParagraphStyle(
                        'CodeBlock',
                        fontName='Courier',
                        fontSize=7.5,  # Slightly smaller for better fit
                        leading=9,
                        leftIndent=0,
                        rightIndent=0,
                        wordWrap='CJK',  # Enable word wrapping
                        splitLongWords=True,  # Allow breaking long words
                        spaceBefore=0,
                        spaceAfter=0
                    )
                    
                    # Process each line
                    code_paras = []
                    for code_line in code_lines:
                        # Escape HTML characters
                        escaped_line = code_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        
                        # Handle leading spaces for indentation
                        # Count leading spaces
                        leading_spaces = len(code_line) - len(code_line.lstrip())
                        indent_text = '&nbsp;' * leading_spaces
                        content_text = escaped_line.lstrip()
                        
                        # Create paragraph with proper indentation
                        if content_text:
                            para_text = f'{indent_text}{content_text}'
                        else:
                            para_text = '&nbsp;'  # Empty line
                        
                        code_paras.append(Paragraph(para_text, code_para_style))
                    
                    # Create table with gray background for code block
                    # Use slightly wider column to accommodate more text
                    code_table = Table([[para] for para in code_paras], colWidths=[6.3*inch])
                    code_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
                        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
                        ('LEFTPADDING', (0, 0), (-1, -1), 12),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    
                    story.append(Spacer(1, 0.15*inch))
                    story.append(code_table)
                    story.append(Spacer(1, 0.15*inch))
                continue
            
            # Check for tables first (before headings, as tables can contain #)
            if '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
                # Extract the table
                table_lines = []
                j = i
                while j < len(lines) and '|' in lines[j]:
                    table_lines.append(lines[j])
                    j += 1
                
                # Parse and add the table
                if len(table_lines) >= 1:  # At least one row
                    self._add_formatted_table(table_lines, story, styles)
                    story.append(Spacer(1, 0.2*inch))
                
                i = j
            # Check for headings
            elif line.startswith('###'):
                heading_text = line.replace('###', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.15*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['subheading']))
                story.append(Spacer(1, 0.1*inch))
                i += 1
            elif line.startswith('##'):
                heading_text = line.replace('##', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['heading']))
                story.append(Spacer(1, 0.15*inch))
                i += 1
            elif line.startswith('#'):
                heading_text = line.replace('#', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['heading']))
                story.append(Spacer(1, 0.15*inch))
                i += 1
            # Check for bold text
            elif line.startswith('**') and line.endswith('**'):
                bold_text = line.replace('**', '').strip()
                story.append(Paragraph(f"<b>{bold_text}</b>", styles['body']))
                story.append(Spacer(1, 0.08*inch))
                i += 1
            # Check for bullet points
            elif line.startswith('•') or line.startswith('- ') or line.startswith('* '):
                bullet_text = re.sub(r'^[•\-\*]\s*', '', line).strip()
                # Remove any remaining ** markers from bullet text
                bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
                # Handle inline code in bullets
                bullet_text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', bullet_text)
                story.append(Paragraph(f"• {bullet_text}", styles['body']))
                story.append(Spacer(1, 0.05*inch))
                i += 1
            # Regular paragraph
            else:
                # Handle inline bold text - convert ** to HTML bold tags
                line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                # Remove any remaining standalone ** markers
                line = line.replace('**', '')
                # Handle inline code (backticks)
                line = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', line)
                story.append(Paragraph(line, styles['body']))
                story.append(Spacer(1, 0.08*inch))
                i += 1
    
    def _parse_and_format_tco_content(self, content: str, story: List, styles: Dict):
        """Parse TCO content and format tables properly with markdown cleaning"""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        import re
        
        # Clean markdown artifacts first
        content = self._clean_markdown_for_pdf(content)
        
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines but add spacing
            if not line:
                story.append(Spacer(1, 0.1*inch))
                i += 1
                continue
            
            # Check if this is a markdown table (contains |)
            if '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
                # Extract the table
                table_lines = []
                j = i
                while j < len(lines) and '|' in lines[j]:
                    table_lines.append(lines[j])
                    j += 1
                
                # Parse and add the table
                if len(table_lines) >= 2:  # At least header and separator
                    self._add_formatted_table(table_lines, story, styles)
                    story.append(Spacer(1, 0.2*inch))
                
                i = j
            elif line.startswith('###'):
                # Subheading
                heading_text = line.replace('###', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.15*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['subheading']))
                story.append(Spacer(1, 0.1*inch))
                i += 1
            elif line.startswith('##'):
                # Section heading
                heading_text = line.replace('##', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['heading']))
                story.append(Spacer(1, 0.15*inch))
                i += 1
            elif line.startswith('#'):
                # Main heading
                heading_text = line.replace('#', '').strip()
                # Remove ** markers from headings
                heading_text = heading_text.replace('**', '')
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(f"<b>{heading_text}</b>", styles['heading']))
                story.append(Spacer(1, 0.15*inch))
                i += 1
            elif line.startswith('**') and line.endswith('**'):
                # Bold text
                bold_text = line.replace('**', '').strip()
                story.append(Paragraph(f"<b>{bold_text}</b>", styles['body']))
                story.append(Spacer(1, 0.08*inch))
                i += 1
            elif line.startswith('•') or line.startswith('- ') or line.startswith('* '):
                # Bullet point
                bullet_text = re.sub(r'^[•\-\*]\s*', '', line).strip()
                # Remove any remaining ** markers from bullet text
                bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
                story.append(Paragraph(f"• {bullet_text}", styles['body']))
                story.append(Spacer(1, 0.05*inch))
                i += 1
            else:
                # Regular paragraph - handle inline bold
                line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                # Remove any remaining standalone ** markers
                line = line.replace('**', '')
                story.append(Paragraph(line, styles['body']))
                story.append(Spacer(1, 0.08*inch))
                i += 1
    
    def _add_formatted_table(self, table_lines: List[str], story: List, styles: Dict):
        """Convert markdown table to ReportLab table with proper formatting"""
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.lib.styles import ParagraphStyle
        import re
        
        # Create a style for table cells with text wrapping
        cell_style = ParagraphStyle(
            'TableCell',
            fontSize=9,
            leading=11,
            wordWrap='CJK',
            alignment=0  # Left align
        )
        
        cell_style_right = ParagraphStyle(
            'TableCellRight',
            fontSize=9,
            leading=11,
            wordWrap='CJK',
            alignment=2  # Right align
        )
        
        header_style = ParagraphStyle(
            'TableHeader',
            fontSize=10,
            leading=12,
            wordWrap='CJK',
            alignment=1,  # Center align
            textColor=colors.whitesmoke
        )
        
        # Parse table data and track where separator was in original lines
        table_data = []
        separator_line_idx = None
        
        for idx, line in enumerate(table_lines):
            # Split by | and clean up
            cells = [cell.strip() for cell in line.split('|')]
            # Remove empty first/last cells from markdown format
            cells = [c for c in cells if c]
            
            # Skip empty rows
            if not cells or all(not c.strip() for c in cells):
                continue
            
            # Check if this is the separator line (|---|---|)
            if all(c.replace('-', '').replace(':', '').replace(' ', '').strip() == '' for c in cells):
                # Record where the separator was in the original table_lines
                separator_line_idx = idx
                continue  # Skip adding separator to table_data
            
            # Clean each cell of markdown artifacts and special characters
            cleaned_cells = []
            for cell in cells:
                # Remove box drawing characters
                cell = re.sub(r'[─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬■□▪▫●○◆◇★☆✓✗✘]', '', cell)
                # Remove excessive spaces
                cell = re.sub(r' {2,}', ' ', cell)
                # Remove markdown bold markers but keep the text
                cell = re.sub(r'\*\*(.*?)\*\*', r'\1', cell)
                # Remove # from table cells
                cell = cell.replace('#', '')
                # Remove emoji symbols
                cell = re.sub(r'[🟡❌✅]', '', cell)
                cleaned_cells.append(cell.strip())
            
            if cleaned_cells and any(c.strip() for c in cleaned_cells):
                table_data.append(cleaned_cells)
        
        if not table_data or len(table_data) < 1:
            return
        
        # Determine header row based on separator position in original lines
        # Standard markdown format: Header is BEFORE the separator line
        # So if separator was at line 1, header is the first row (index 0) in table_data
        header_row_idx = 0  # Default to first row
        
        if separator_line_idx is not None:
            # The header is the row that came before the separator in the original lines
            # Since we skipped the separator, the first row in table_data is the header
            # if the separator was at position 1 (after the first data line)
            if separator_line_idx == 1:
                header_row_idx = 0
            elif separator_line_idx > 1:
                # If separator was later, we need to count how many data rows came before it
                # But in standard markdown, separator is always right after header (position 1)
                # So this shouldn't happen in well-formed tables
                header_row_idx = 0
        
        # Ensure all rows have the same number of columns
        max_cols = max(len(row) for row in table_data)
        for row in table_data:
            while len(row) < max_cols:
                row.append('')
        
        # Determine column widths based on content
        num_cols = max_cols
        
        # Calculate appropriate column widths with more space
        if num_cols == 5:
            col_widths = [1.6*inch, 1.4*inch, 1.4*inch, 1.3*inch, 1.3*inch]
        elif num_cols == 4:
            col_widths = [2.2*inch, 1.6*inch, 1.6*inch, 1.6*inch]
        elif num_cols == 3:
            col_widths = [2.5*inch, 2*inch, 2*inch]
        elif num_cols == 2:
            col_widths = [3*inch, 3.5*inch]
        else:
            # Equal width for other cases
            available_width = 6.5 * inch
            col_widths = [available_width / num_cols] * num_cols
        
        # Header is always the first row in standard markdown tables
        # No need to reorder since we correctly identified it as row 0
        
        # Convert text to Paragraph objects for proper wrapping
        formatted_data = []
        for row_idx, row in enumerate(table_data):
            formatted_row = []
            for col_idx, cell in enumerate(row):
                if row_idx == header_row_idx:
                    # Header row
                    formatted_row.append(Paragraph(f"<b>{cell}</b>", header_style))
                else:
                    # Data rows - right align numeric columns (except first column)
                    if col_idx == 0:
                        formatted_row.append(Paragraph(cell, cell_style))
                    else:
                        formatted_row.append(Paragraph(cell, cell_style_right))
            formatted_data.append(formatted_row)
        
        # Create table with formatted data
        table = Table(formatted_data, colWidths=col_widths, repeatRows=1)
        
        # Apply styling
        table_style = [
            # Header row styling (always row 0 now after reordering)
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Data rows styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            
            # Grid and borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2E86AB')),
            
            # Padding - increased for better spacing
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]
        
        # Highlight subtotal/total rows
        for row_idx, row in enumerate(table_data):
            if row and any(keyword in str(row[0]).lower() for keyword in ['subtotal', 'total']):
                table_style.extend([
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#F0F0F0')),
                    ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'),
                    ('LINEABOVE', (0, row_idx), (-1, row_idx), 1.5, colors.HexColor('#2E86AB')),
                ])
        
        # Alternate row colors for better readability (skip header and special rows)
        for row_idx in range(1, len(table_data)):
            row = table_data[row_idx]
            if not any(keyword in str(row[0]).lower() for keyword in ['subtotal', 'total']):
                if row_idx % 2 == 0:
                    table_style.append(
                        ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#F8F9FA'))
                    )
        
        table.setStyle(TableStyle(table_style))
        story.append(table)
    
    def _add_migration_roadmap(self, story: List, styles: Dict):
        """Add migration roadmap section with proper markdown cleaning"""
        from reportlab.platypus import Paragraph, Spacer, PageBreak
        
        story.append(Paragraph("6. Migration Roadmap", styles['heading']))
        
        navigator_response = self.workflow_state['agent_responses'].get('navigator', {})
        if navigator_response:
            story.append(Paragraph("6.1 Implementation Steps", styles['subheading']))
            
            roadmap_text = str(navigator_response.get('output', 'No migration roadmap available.'))
            
            # Clean markdown artifacts
            roadmap_text = self._clean_markdown_for_pdf(roadmap_text)
            
            # Parse and format the content properly
            self._parse_and_format_content(roadmap_text, story, styles)
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
