"""
Streamlit Application for SageMaker Migration Advisor
Interactive web interface for architecture migration workflow with state management and error recovery
"""

import sys
import os

# Fix Windows encoding issues - set UTF-8 as default encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import streamlit as st
import json
import datetime
import traceback
from typing import Dict, Any, Optional
import base64
from io import BytesIO
from PIL import Image

# Import the existing advisor components
from strands import Agent
from strands_tools import http_request, image_reader, use_llm, load_tool
from tools import user_prompt as user_input
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from logger_config import logger
from strands.agent.conversation_manager import SlidingWindowConversationManager
from botocore.config import Config as BotocoreConfig
from strands.types.exceptions import MaxTokensReachedException

from prompts_lite import (
    architecture_description_system_prompt,
    QUESTION_SYSTEM_PROMPT,
    SAGEMAKER_SYSTEM_PROMPT,
    DIAGRAM_GENERATION_SYSTEM_PROMPT,
    SAGEMAKER_USER_PROMPT,
    DIAGRAM_GENERATION_USER_PROMPT,
    CLOUDFORMATION_SYSTEM_PROMPT,
    CLOUDFORMATION_USER_PROMPT,
    ARCHITECTURE_NAVIGATOR_SYSTEM_PROMPT,
    ARCHITECTURE_NAVIGATOR_USER_PROMPT,
    AWS_PERSPECTIVES_SYSTEM_PROMPT,
    AWS_PERSPECTIVES_USER_PROMPT,
    AWS_TCO_SYSTEM_PROMPT,
    AWS_TCO_USER_PROMPT
)

# Configure Streamlit page
st.set_page_config(
    page_title="SageMaker Migration Advisor Lite",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #FF6B35;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        font-size: 1.5rem;
        color: #2E86AB;
        margin: 1rem 0;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        margin: 1rem 0;
    }
    .agent-response {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class SageMakerAdvisorApp:
    def __init__(self):
        self.initialize_session_state()
        self.setup_bedrock_model()
        self.setup_agents()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state variables"""
        if 'workflow_state' not in st.session_state:
            st.session_state.workflow_state = {
                'current_step': 'input',
                'completed_steps': [],
                'agent_responses': {},
                'user_inputs': {},
                'errors': {},
                'conversation_history': [],
                'qa_session': None
            }
        
        if 'conversation_manager' not in st.session_state:
            st.session_state.conversation_manager = SlidingWindowConversationManager(window_size=20)
    
    def setup_bedrock_model(self):
        """Setup Bedrock model with fallback options - Lite mode uses lower max_tokens for faster responses"""
        if 'bedrock_model' not in st.session_state:
            bedrock_timeout_config = BotocoreConfig(read_timeout=300)
            lite_max_tokens = 12288  # ~3x of 4096, balanced for speed + completeness
            try:
                st.session_state.bedrock_model = BedrockModel(
                    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    region_name='us-west-2',
                    temperature=0.0,
                    max_tokens=lite_max_tokens,
                    boto_client_config=bedrock_timeout_config
                )
                st.session_state.model_name = "Claude 4.5 Sonnet"
            except Exception as e:
                try:
                    st.session_state.bedrock_model = BedrockModel(
                        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                        region_name='us-west-2',
                        temperature=0.0,
                        max_tokens=lite_max_tokens,
                        boto_client_config=bedrock_timeout_config
                    )
                    st.session_state.model_name = "Claude 4 Sonnet"
                except Exception as e2:
                    try:
                        st.session_state.bedrock_model = BedrockModel(
                            model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                            region_name='us-west-2',
                            temperature=0.0,
                            max_tokens=lite_max_tokens,
                            boto_client_config=bedrock_timeout_config
                        )
                        st.session_state.model_name = "Claude 3.7 Sonnet"
                    except Exception as e3:
                        st.error(f"Failed to initialize Bedrock model: {e3}")
                        st.stop()
    
    def setup_agents(self):
        """Setup all agents used in the workflow"""
        if 'agents' not in st.session_state:
            st.session_state.agents = {}
            
            # Architecture description agent (keep user_input for diagram analysis)
            st.session_state.agents['architecture'] = Agent(
                tools=[http_request, image_reader, load_tool, use_llm],
                model=st.session_state.bedrock_model,
                system_prompt=architecture_description_system_prompt,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
            
            # Q&A Agent (no user_input - handled in UI)
            st.session_state.agents['qa'] = Agent(
                model=st.session_state.bedrock_model,
                system_prompt=QUESTION_SYSTEM_PROMPT,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
            
            # SageMaker Agent
            st.session_state.agents['sagemaker'] = Agent(
                model=st.session_state.bedrock_model,
                system_prompt=SAGEMAKER_SYSTEM_PROMPT,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
            
            # TCO Analysis Agent (no user_input - handled in UI)
            st.session_state.agents['tco'] = Agent(
                model=st.session_state.bedrock_model,
                system_prompt=AWS_TCO_SYSTEM_PROMPT,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
            
            # Architecture Navigator Agent (no user_input - handled in UI)
            st.session_state.agents['navigator'] = Agent(
                model=st.session_state.bedrock_model,
                system_prompt=ARCHITECTURE_NAVIGATOR_SYSTEM_PROMPT,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
    
    def save_interaction(self, agent_name: str, input_prompt: str, output: str, step: str):
        """Save agent interaction to session state and file"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        interaction = {
            'timestamp': timestamp,
            'agent': agent_name,
            'step': step,
            'input': input_prompt,
            'output': output
        }
        
        # Save to session state
        st.session_state.workflow_state['agent_responses'][step] = interaction
        st.session_state.workflow_state['conversation_history'].append(interaction)
        
        # Save to file for persistence
        self.write_to_file(interaction)
    
    def write_to_file(self, interaction: Dict[str, Any]):
        """Write interaction to file"""
        output_file = "advisor_agent_interactions.txt"
        separator = "=" * 80
        
        formatted_interaction = f"""
{separator}
[{interaction['timestamp']}] {interaction['agent'].upper()} - {interaction['step'].upper()}
{separator}

INPUT:
{'-' * 40}
{interaction['input']}

OUTPUT:
{'-' * 40}
{interaction['output']}

"""
        
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(formatted_interaction)
    
    def display_sidebar(self):
        """Display sidebar with workflow progress and controls"""
        with st.sidebar:
            st.markdown("## 🚀 Migration Workflow")
            
            # Display current model
            st.info(f"**Model:** {st.session_state.model_name}")
            
            # Workflow steps with navigation
            steps = [
                ('input', 'Architecture Input'),
                ('description', 'Architecture Analysis'),
                ('qa', 'Clarification Q&A'),
                ('sagemaker', 'SageMaker Design'),
                ('diagram', 'Diagram Generation'),
                ('tco', 'TCO Analysis'),
                ('navigator', 'Migration Roadmap')
            ]
            
            current_step = st.session_state.workflow_state['current_step']
            completed_steps = st.session_state.workflow_state['completed_steps']
            
            st.markdown("### 📍 Navigation")
            st.markdown("*Click on completed steps to revisit*")
            
            for step_id, step_name in steps:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if step_id in completed_steps:
                        st.success(f"✅ {step_name}")
                    elif step_id == current_step:
                        st.warning(f"🔄 {step_name}")
                    else:
                        st.info(f"⏳ {step_name}")
                
                with col2:
                    # Add navigation button for completed steps
                    if step_id in completed_steps and step_id != current_step:
                        if st.button("👁️", key=f"nav_{step_id}", help=f"View {step_name}"):
                            st.session_state.workflow_state['current_step'] = step_id
                            st.rerun()
            
            st.markdown("---")
            
            # Control buttons
            if st.button("🔄 Reset Workflow"):
                self.reset_workflow()
                st.rerun()
            
            # Download section
            st.markdown("### 📥 Download Reports")
            if st.button("💾 Generate Reports", help="Generate PDF report and JSON data"):
                with st.spinner("Generating reports..."):
                    self.download_results()
            
            # Error recovery
            if st.session_state.workflow_state['errors']:
                st.markdown("### ⚠️ Error Recovery")
                for step, error in st.session_state.workflow_state['errors'].items():
                    if st.button(f"Retry {step}"):
                        self.retry_step(step)
                        st.rerun()
    
    def reset_workflow(self):
        """Reset the entire workflow"""
        st.session_state.workflow_state = {
            'current_step': 'input',
            'completed_steps': [],
            'agent_responses': {},
            'user_inputs': {},
            'errors': {},
            'conversation_history': [],
            'qa_session': None
        }
        st.success("Workflow reset successfully!")
    
    def retry_step(self, step: str):
        """Retry a failed step"""
        if step in st.session_state.workflow_state['errors']:
            del st.session_state.workflow_state['errors'][step]
        
        # Remove step from completed steps if it was there
        if step in st.session_state.workflow_state['completed_steps']:
            st.session_state.workflow_state['completed_steps'].remove(step)
        
        # Set current step to the failed step
        st.session_state.workflow_state['current_step'] = step
        st.success(f"Retrying step: {step}")
    
    def download_results(self):
        """Generate downloadable results in multiple formats using PDFReportGenerator"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate JSON results
        results = {
            'workflow_state': st.session_state.workflow_state,
            'timestamp': datetime.datetime.now().isoformat(),
            'model_used': st.session_state.model_name
        }
        json_str = json.dumps(results, indent=2)
        
        # Generate PDF report using PDFReportGenerator
        pdf_buffer = None
        try:
            from pdf_report_generator import PDFReportGenerator
            
            # Get diagram folder path - handles both local and ECS/Fargate
            from path_utils import get_diagram_folder
            diagram_folder = get_diagram_folder()
            
            # Create PDF generator
            pdf_gen = PDFReportGenerator(
                workflow_state=st.session_state.workflow_state,
                diagram_folder=diagram_folder,
                model_name=st.session_state.model_name
            )
            
            # Generate PDF
            with st.spinner("Generating PDF report..."):
                pdf_buffer = pdf_gen.generate_report()
            
            if pdf_buffer:
                logger.info("PDF report generated successfully")
            else:
                logger.warning("PDF generation returned None")
                st.warning("⚠️ PDF generation completed but returned no data. Check logs for details.")
                
        except ImportError as e:
            logger.error(f"Missing reportlab dependency: {e}")
            st.error("❌ PDF generation requires reportlab library.")
            st.info("💡 **To fix this issue:**\n\n"
                   "1. Install reportlab: `pip install reportlab>=3.6.0`\n"
                   "2. Or install all requirements: `pip install -r requirements.txt`\n"
                   "3. Restart the application after installation")
        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            st.error(f"❌ PDF generation failed: {str(e)}")
            st.info("💡 Check the logs for more details. You can still download the JSON data below.")
        
        # Show report preview
        st.markdown("### 📋 Report Contents")
        
        completed_steps = st.session_state.workflow_state.get('completed_steps', [])
        report_sections = []
        
        if 'description' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Current Architecture Analysis")
        if 'qa' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Clarification Q&A Session")
        if 'sagemaker' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Proposed SageMaker Architecture")
        if 'diagram' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Architecture Diagrams Reference")
        if 'tco' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Total Cost of Ownership Analysis")
        if 'navigator' in st.session_state.workflow_state.get('agent_responses', {}):
            report_sections.append("✅ Migration Roadmap")
        
        report_sections.extend([
            "✅ Executive Summary",
            "✅ Implementation Recommendations",
            "✅ Success Criteria & Best Practices"
        ])
        
        for section in report_sections:
            st.markdown(f"• {section}")
        
        st.markdown("---")
        
        # Create download buttons
        if pdf_buffer:
            col1, col2 = st.columns(2)
            
            with col1:
                # Ensure PDF buffer is properly positioned for Firefox compatibility
                pdf_data = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_data,
                    file_name=f"SageMaker_Migration_Report_{timestamp}.pdf",
                    mime="application/pdf",
                    help="Comprehensive migration report for implementation",
                    key="pdf_download_btn"
                )
            
            with col2:
                st.download_button(
                    label="📥 Download JSON Data",
                    data=json_str,
                    file_name=f"sagemaker_migration_data_{timestamp}.json",
                    mime="application/json",
                    help="Raw data for further processing",
                    key="json_download_btn"
                )
        else:
            st.warning("PDF generation failed. Downloading JSON data only.")
            st.info("💡 To enable PDF generation, ensure reportlab is installed: pip install reportlab")
            st.download_button(
                label="📥 Download JSON Data",
                data=json_str,
                file_name=f"sagemaker_migration_data_{timestamp}.json",
                mime="application/json",
                help="Raw data for further processing"
            )
    
    
    def handle_architecture_input(self):
        """Handle architecture input step"""
        st.markdown('<div class="step-header">📋 Step 1: Architecture Input</div>', unsafe_allow_html=True)
        
        # Show previous input if navigating back
        user_inputs = st.session_state.workflow_state.get('user_inputs', {})
        if 'description' in user_inputs or 'diagram_path' in user_inputs:
            with st.expander("📝 View Previous Input", expanded=False):
                if 'description' in user_inputs:
                    st.markdown("**Previous Text Description:**")
                    st.text_area("", user_inputs['description'], height=150, disabled=True, key="prev_desc_view")
                elif 'diagram_path' in user_inputs:
                    st.markdown("**Previous Diagram:**")
                    try:
                        img = Image.open(user_inputs['diagram_path'])
                        st.image(img, caption="Previously uploaded diagram", width=400)
                    except:
                        st.info(f"Diagram path: {user_inputs['diagram_path']}")
            st.markdown("---")
        
        # Check if we have a diagram
        has_diagram = st.radio(
            "Do you have an architecture diagram?",
            ["No", "Yes"],
            key="has_diagram"
        )
        
        if has_diagram == "Yes":
            uploaded_file = st.file_uploader(
                "Upload your architecture diagram",
                type=['png', 'jpg', 'jpeg', 'gif', 'bmp'],
                key="diagram_upload"
            )
            
            if uploaded_file is not None:
                # Open and process the uploaded image
                image = Image.open(uploaded_file)
                
                # Check image dimensions and resize if necessary
                from advisor_config import MAX_IMAGE_DIMENSION
                max_dimension = MAX_IMAGE_DIMENSION
                width, height = image.size
                
                if width > max_dimension or height > max_dimension:
                    st.warning(f"⚠️ Image is too large ({width}x{height}). Resizing to fit Bedrock limits...")
                    
                    # Calculate new dimensions maintaining aspect ratio
                    if width > height:
                        new_width = max_dimension
                        new_height = int((height * max_dimension) / width)
                    else:
                        new_height = max_dimension
                        new_width = int((width * max_dimension) / height)
                    
                    # Resize the image
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    st.info(f"✅ Image resized to {new_width}x{new_height} pixels")
                
                # Display the (possibly resized) image
                st.image(image, caption="Uploaded Architecture Diagram")
                
                # Save the image temporarily
                temp_path = f"temp_diagram_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                image.save(temp_path)
                
                if st.button("🔍 Analyze Diagram"):
                    try:
                        # Use st.status for better connection handling during long operations
                        with st.status("🤖 Analyzing architecture diagram...", expanded=True) as status:
                            st.write("📸 Processing your architecture diagram...")
                            st.write("⏳ This may take 45-90 seconds...")
                            
                            prompt = f"""Read the diagram from location {temp_path} and analyze the architecture.

Provide a CONCISE analysis with bullet points:
1. Components list (compute, storage, networking, ML tools)
2. One-line purpose per component
3. Data flow summary
4. Architecture patterns
5. Security & scalability highlights
6. Opportunity Qualification (MRR and ARR estimates)

Keep each section to 2-3 bullet points max."""
                            
                            st.write("🔄 Calling AI model with vision capabilities...")
                            response = st.session_state.agents['architecture'](prompt)
                            
                            st.write("💾 Saving analysis...")
                            self.save_interaction('Architecture Agent', prompt, str(response), 'description')
                            st.session_state.workflow_state['user_inputs']['diagram_path'] = temp_path
                            st.session_state.workflow_state['completed_steps'].append('input')
                            st.session_state.workflow_state['completed_steps'].append('description')
                            st.session_state.workflow_state['current_step'] = 'qa'
                            
                            status.update(label="✅ Analysis complete!", state="complete")
                            st.success("Diagram analysis completed successfully!")
                            
                            # Small delay to show success message
                            import time
                            time.sleep(1)
                            
                            st.rerun()
                    
                    except MaxTokensReachedException as e:
                        # Gracefully handle truncation — use whatever partial response the agent produced
                        logger.warning(f"Diagram analysis hit max_tokens limit, using partial response")
                        partial = str(getattr(e, 'message', '')) or "Analysis was truncated due to response length limits."
                        self.save_interaction('Architecture Agent', prompt, partial, 'description')
                        st.session_state.workflow_state['user_inputs']['diagram_path'] = temp_path
                        st.session_state.workflow_state['completed_steps'].append('input')
                        st.session_state.workflow_state['completed_steps'].append('description')
                        st.session_state.workflow_state['current_step'] = 'qa'
                        st.warning("⚠️ Analysis was slightly truncated but still usable. Proceeding...")
                        import time
                        time.sleep(1)
                        st.rerun()
                    
                    except Exception as e:
                        st.error(f"Error analyzing diagram: {str(e)}")
                        st.session_state.workflow_state['errors']['description'] = str(e)
        else:
            # Text description input
            arch_description = st.text_area(
                "Please describe your GenAI/ML migration use case in detail:",
                height=200,
                key="arch_description"
            )
            
            if arch_description and st.button("🔍 Analyze Description"):
                try:
                    # Use st.status for better connection handling during long operations
                    with st.status("🤖 Analyzing architecture description...", expanded=True) as status:
                        st.write("📝 Processing your architecture description...")
                        st.write("⏳ This may take 30-60 seconds...")
                        
                        # Create a clear prompt for text-based architecture description
                        analysis_prompt = f"""Analyze this ML/GenAI architecture description concisely.

ARCHITECTURE DESCRIPTION:
{arch_description}

Provide a CONCISE analysis with bullet points:
1. Components list
2. One-line purpose per component
3. Data flow summary
4. Architecture patterns
5. Security & scalability highlights
6. Opportunity Qualification (MRR and ARR estimates)

Keep each section to 2-3 bullet points max."""
                        
                        st.write("🔄 Calling AI model...")
                        response = st.session_state.agents['architecture'](analysis_prompt)
                        
                        st.write("💾 Saving analysis...")
                        self.save_interaction('Architecture Agent', arch_description, str(response), 'description')
                        st.session_state.workflow_state['user_inputs']['description'] = arch_description
                        st.session_state.workflow_state['completed_steps'].append('input')
                        st.session_state.workflow_state['completed_steps'].append('description')
                        st.session_state.workflow_state['current_step'] = 'qa'
                        
                        status.update(label="✅ Analysis complete!", state="complete")
                        st.success("Architecture analysis completed successfully!")
                        
                        # Small delay to show success message
                        import time
                        time.sleep(1)
                        
                        st.rerun()
                
                except MaxTokensReachedException as e:
                    logger.warning(f"Text analysis hit max_tokens limit, using partial response")
                    partial = str(getattr(e, 'message', '')) or "Analysis was truncated due to response length limits."
                    self.save_interaction('Architecture Agent', arch_description, partial, 'description')
                    st.session_state.workflow_state['user_inputs']['description'] = arch_description
                    st.session_state.workflow_state['completed_steps'].append('input')
                    st.session_state.workflow_state['completed_steps'].append('description')
                    st.session_state.workflow_state['current_step'] = 'qa'
                    st.warning("⚠️ Analysis was slightly truncated but still usable. Proceeding...")
                    import time
                    time.sleep(1)
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error analyzing description: {str(e)}")
                    st.session_state.workflow_state['errors']['description'] = str(e)
    
    def handle_qa_step(self):
        """Handle Q&A clarification step with interactive conversation"""
        st.markdown('<div class="step-header">❓ Step 2: Interactive Clarification Q&A</div>', unsafe_allow_html=True)
        
        # Get the architecture description from previous step
        arch_response = st.session_state.workflow_state['agent_responses'].get('description', {})
        
        if arch_response:
            # Only show architecture analysis in an expander to avoid clutter
            with st.expander("📋 View Architecture Analysis", expanded=False):
                st.markdown('<div class="agent-response">', unsafe_allow_html=True)
                st.markdown("**Architecture Analysis:**")
                st.write(arch_response.get('output', ''))
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Initialize Q&A session state
            if 'qa_session' not in st.session_state.workflow_state or st.session_state.workflow_state['qa_session'] is None:
                st.session_state.workflow_state['qa_session'] = {
                    'conversation': [],
                    'current_question': None,
                    'questions_asked': 0,
                    'context_built': str(arch_response.get('output', '')),
                    'session_active': False
                }
            
            qa_session = st.session_state.workflow_state['qa_session']
            
            # Additional safety check
            if qa_session is None:
                qa_session = {
                    'conversation': [],
                    'current_question': None,
                    'questions_asked': 0,
                    'context_built': str(arch_response.get('output', '')),
                    'session_active': False
                }
                st.session_state.workflow_state['qa_session'] = qa_session
            
            # Start Q&A session
            if not qa_session.get('session_active', False):
                if st.button("🤔 Start Interactive Q&A Session"):
                    with st.spinner("🤔 Generating first clarification question..."):
                        qa_session['session_active'] = True
                        self.ask_next_question()
                    st.rerun()
            
            # Display conversation history
            if qa_session.get('conversation', []):
                st.markdown("### 💬 Q&A Conversation")
                for i, exchange in enumerate(qa_session['conversation']):
                    with st.container():
                        st.markdown(f"**🤖 Question {i+1}:**")
                        st.markdown(f'<div class="agent-response">{exchange.get("question", "")}</div>', unsafe_allow_html=True)
                        
                        if exchange.get('answer'):
                            st.markdown(f"**👤 Your Answer:**")
                            st.markdown(f'<div class="info-box">{exchange["answer"]}</div>', unsafe_allow_html=True)
                        
                        # Display AI synthesis of the answer
                        if exchange.get('synthesis'):
                            st.markdown(f"**🧠 AI Understanding:**")
                            st.markdown(f'<div class="success-box">✓ {exchange["synthesis"]}</div>', unsafe_allow_html=True)
                        
                        st.markdown("---")
            
            # Handle current question
            if qa_session.get('session_active', False) and qa_session.get('current_question'):
                st.markdown("### 🎯 Current Question")
                st.markdown('<div class="agent-response">', unsafe_allow_html=True)
                st.markdown(f"**Question {qa_session.get('questions_asked', 0)}:**")
                st.write(qa_session['current_question'])
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Answer input
                answer_key = f"qa_answer_{qa_session.get('questions_asked', 0)}"
                user_answer = st.text_area(
                    "Your answer:",
                    height=100,
                    key=answer_key,
                    placeholder="Please provide a detailed answer..."
                )
                
                col1, col2, col3 = st.columns([1, 1, 3])
                
                with col1:
                    if user_answer and st.button("✅ Submit Answer"):
                        # Use st.status for better connection handling
                        with st.status("🧠 Processing your answer...", expanded=True) as status:
                            st.write("📝 Analyzing your response...")
                            st.write("⏳ Generating next question...")
                            
                            self.process_qa_answer(user_answer)
                            
                            status.update(label="✅ Answer processed!", state="complete")
                            
                            # Small delay
                            import time
                            time.sleep(0.5)
                        st.rerun()
                
                with col2:
                    if st.button("⏭️ Skip Question"):
                        self.process_qa_answer("No additional information provided.")
                        st.rerun()
            
            # Session controls
            if qa_session.get('session_active', False):
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("🏁 Complete Q&A Session"):
                        with st.spinner("📝 Generating comprehensive Q&A analysis..."):
                            self.complete_qa_session()
                        st.rerun()
                
                with col2:
                    if st.button("🔄 Reset Q&A"):
                        self.reset_qa_session()
                        st.rerun()
                
                with col3:
                    st.info(f"Questions asked: {qa_session.get('questions_asked', 0)}")
        
        # Display final Q&A response if available
        qa_response = st.session_state.workflow_state['agent_responses'].get('qa', {})
        if qa_response:
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.markdown("**✅ Q&A Session Completed!**")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="agent-response">', unsafe_allow_html=True)
            st.markdown("**Final Comprehensive Analysis:**")
            st.write(qa_response.get('output', ''))
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Navigation buttons
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("⬅️ Back to Analysis"):
                    st.session_state.workflow_state['current_step'] = 'description'
                    st.rerun()
            with col2:
                if st.button("➡️ Continue to SageMaker Design"):
                    st.session_state.workflow_state['current_step'] = 'sagemaker'
                    st.rerun()
    
    def ask_next_question(self):
        """Generate and ask the next clarification question"""
        try:
            qa_session = st.session_state.workflow_state.get('qa_session')
            if qa_session is None:
                st.error("Q&A session not initialized properly")
                return
            
            # Create Q&A agent
            qa_agent = Agent(
                model=st.session_state.bedrock_model,
                system_prompt=QUESTION_SYSTEM_PROMPT,
                load_tools_from_directory=False,
                conversation_manager=st.session_state.conversation_manager
            )
            
            # Build context for next question
            conversation_context = ""
            if qa_session.get('conversation', []):
                conversation_context = "\n\nPREVIOUS Q&A:\n"
                for i, exchange in enumerate(qa_session['conversation']):
                    conversation_context += f"Q{i+1}: {exchange.get('question', '')}\nA{i+1}: {exchange.get('answer', 'No answer provided')}\n\n"
            
            # Generate next question
            prompt = f"""
{qa_session.get('context_built', '')}
{conversation_context}

Based on the architecture analysis and previous Q&A exchanges, ask ONE specific clarification question that will help better understand the migration requirements. 

Focus on areas like:
- Technical specifications and constraints
- Performance and scalability requirements  
- Data volume and processing patterns
- Integration requirements
- Security and compliance needs
- Timeline and resource constraints
- Current pain points and challenges

Ask only ONE focused question. Make it specific and actionable. Restrict total number of questions to less than 3. However, attempt to collect multiple data points in each question.
If you believe sufficient information has been gathered after {qa_session.get('questions_asked', 0)} questions, respond with "SUFFICIENT_INFO_GATHERED".
"""
            
            response = qa_agent(prompt)
            response_text = str(response).strip()
            
            if "SUFFICIENT_INFO_GATHERED" in response_text.upper():
                # AI thinks we have enough information
                qa_session['current_question'] = None
                self.complete_qa_session()
            else:
                # Increment question count first, then store the question
                qa_session['questions_asked'] = qa_session.get('questions_asked', 0) + 1
                qa_session['current_question'] = response_text
        
        except Exception as e:
            st.error(f"Error generating question: {str(e)}")
            qa_session['current_question'] = "Could you provide any additional details about your current architecture that might be important for the migration?"
    
    def process_qa_answer(self, answer: str):
        """Process the user's answer and prepare for next question"""
        qa_session = st.session_state.workflow_state.get('qa_session')
        if qa_session is None:
            st.error("Q&A session not initialized properly")
            return
        
        # Generate AI synthesis of the answer
        synthesis = self.synthesize_answer(qa_session.get('current_question', ''), answer)
        
        # Add to conversation history with synthesis
        if 'conversation' not in qa_session:
            qa_session['conversation'] = []
        
        qa_session['conversation'].append({
            'question': qa_session.get('current_question', ''),
            'answer': answer,
            'synthesis': synthesis
        })
        
        # Update context with synthesis
        current_context = qa_session.get('context_built', '')
        qa_session['context_built'] = current_context + f"\n\nQ: {qa_session.get('current_question', '')}\nA: {answer}\nSynthesis: {synthesis}"
        
        # Clear current question
        qa_session['current_question'] = None
        
        # Decide whether to ask another question
        questions_asked = qa_session.get('questions_asked', 0)
        if questions_asked < 8:  # Maximum 8 questions
            self.ask_next_question()
        else:
            # Automatically complete after 8 questions
            self.complete_qa_session()
    
    def synthesize_answer(self, question: str, answer: str) -> str:
        """Generate AI synthesis of user's answer"""
        try:
            # Create a synthesis agent
            synthesis_agent = Agent(
                model=st.session_state.bedrock_model,
                system_prompt="""You are an expert at synthesizing and summarizing technical information. 
                Your job is to take a user's answer to a question and provide a clear, concise synthesis that:
                1. Confirms your understanding of what the user said
                2. Extracts key technical details and requirements
                3. Identifies any implications for the migration
                4. Is written in 2-3 sentences maximum
                
                Be specific and technical. Focus on actionable insights.""",
                load_tools_from_directory=False
            )
            
            synthesis_prompt = f"""
Question asked: {question}

User's answer: {answer}

Please provide a concise synthesis of this answer that confirms your understanding and highlights key points relevant to the SageMaker migration. Keep it to 2-3 sentences.
"""
            
            response = synthesis_agent(synthesis_prompt)
            return str(response).strip()
            
        except Exception as e:
            logger.error(f"Error generating synthesis: {e}")
            return f"Understood: {answer[:100]}..." if len(answer) > 100 else f"Understood: {answer}"
    
    def complete_qa_session(self):
        """Complete the Q&A session and move to next step"""
        try:
            qa_session = st.session_state.workflow_state.get('qa_session')
            if qa_session is None:
                st.error("Q&A session not initialized properly")
                return
            
            # Build final comprehensive response
            conversation_summary = ""
            conversation_list = qa_session.get('conversation', [])
            for i, exchange in enumerate(conversation_list):
                conversation_summary += f"Q{i+1}: {exchange.get('question', '')}\n"
                conversation_summary += f"A{i+1}: {exchange.get('answer', 'No answer provided')}\n"
                if exchange.get('synthesis'):
                    conversation_summary += f"Understanding: {exchange.get('synthesis')}\n"
                conversation_summary += "\n"
            
            context_built = qa_session.get('context_built', '')
            original_context = context_built.split('Q:')[0].strip() if 'Q:' in context_built else context_built
            
            final_analysis = f"""
ORIGINAL ARCHITECTURE ANALYSIS:
{original_context}

CLARIFICATION Q&A SESSION:
{conversation_summary}

COMPREHENSIVE UNDERSTANDING:
Based on the architecture analysis and {len(conversation_list)} clarification exchanges, we now have a comprehensive understanding of:

1. Current Architecture: Detailed technical specifications and components
2. Requirements: Performance, scalability, and functional requirements  
3. Constraints: Technical, business, and operational constraints
4. Migration Goals: Specific objectives and success criteria

This information provides a solid foundation for designing the SageMaker migration strategy.
"""
            
            # Save the complete Q&A session
            self.save_interaction('Q&A Agent', 
                                f"Interactive Q&A Session with {len(conversation_list)} questions", 
                                final_analysis, 'qa')
            
            # Mark Q&A as complete
            st.session_state.workflow_state['completed_steps'].append('qa')
            st.session_state.workflow_state['current_step'] = 'sagemaker'
            qa_session['session_active'] = False
            
        except Exception as e:
            st.error(f"Error completing Q&A session: {str(e)}")
            st.session_state.workflow_state['errors']['qa'] = str(e)
    
    def reset_qa_session(self):
        """Reset the Q&A session"""
        arch_response = st.session_state.workflow_state['agent_responses'].get('description', {})
        st.session_state.workflow_state['qa_session'] = {
            'conversation': [],
            'current_question': None,
            'questions_asked': 0,
            'context_built': str(arch_response.get('output', '')),
            'session_active': False
        }
    
    def handle_sagemaker_step(self):
        """Handle SageMaker modernization step"""
        st.markdown('<div class="step-header">🚀 Step 3: SageMaker Architecture Design</div>', unsafe_allow_html=True)
        
        qa_response = st.session_state.workflow_state['agent_responses'].get('qa', {})
        
        # Check if SageMaker design already exists
        sagemaker_response = st.session_state.workflow_state['agent_responses'].get('sagemaker', {})
        
        if qa_response and not sagemaker_response:
            # Show Q&A summary
            with st.expander("📋 View Q&A Summary", expanded=False):
                st.markdown("**Clarification Q&A Results:**")
                st.write(qa_response.get('output', ''))
            
            st.markdown("---")
            
            # Add option to skip SageMaker design
            st.info("💡 **SageMaker Architecture Design** - Generate a modernized architecture using AWS SageMaker services.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🏗️ Generate SageMaker Architecture", help="Generate modernized SageMaker architecture design", use_container_width=True):
                    try:
                        # Use st.status for better connection handling
                        with st.status("🤖 Generating SageMaker architecture design...", expanded=True) as status:
                            st.write("📋 Analyzing your requirements...")
                            st.write("⏳ This may take 90-150 seconds...")
                            
                            sagemaker_input = str(qa_response.get('output', '')) + "\n" + SAGEMAKER_USER_PROMPT
                            
                            st.write("🔄 Calling AI model to design architecture...")
                            # Call the agent
                            response = st.session_state.agents['sagemaker'](sagemaker_input)
                        
                            st.write("💾 Processing response...")
                            # Convert response to string
                            if hasattr(response, 'content'):
                                response_str = str(response.content).strip()
                            elif hasattr(response, 'text'):
                                response_str = str(response.text).strip()
                            elif hasattr(response, 'output'):
                                response_str = str(response.output).strip()
                            else:
                                response_str = str(response).strip()
                            
                            # Log for debugging
                            logger.info(f"SageMaker response type: {type(response)}")
                            logger.info(f"SageMaker response length: {len(response_str)} characters")
                            
                            if not response_str or response_str == "None":
                                st.error("⚠️ Received empty response from SageMaker agent")
                                logger.error(f"Empty response - Original response: {response}")
                                response_str = "Error: Empty response received from agent"
                            
                            st.write("💾 Saving design...")
                            # Save the interaction
                            self.save_interaction('SageMaker Agent', sagemaker_input, response_str, 'sagemaker')
                            
                            # Mark step as complete
                            if 'sagemaker' not in st.session_state.workflow_state['completed_steps']:
                                st.session_state.workflow_state['completed_steps'].append('sagemaker')
                            st.session_state.workflow_state['current_step'] = 'diagram'
                            
                            status.update(label="✅ Design complete!", state="complete")
                            st.success("✅ SageMaker architecture design completed!")
                            
                            # Small delay to show success message
                            import time
                            time.sleep(1)
                            
                            # Force rerun to display the result
                            st.rerun()
                    
                    except MaxTokensReachedException as e:
                        logger.warning("SageMaker design hit max_tokens limit, using partial response")
                        partial = str(getattr(e, 'message', '')) or "Design was truncated due to response length limits."
                        self.save_interaction('SageMaker Agent', sagemaker_input, partial, 'sagemaker')
                        if 'sagemaker' not in st.session_state.workflow_state['completed_steps']:
                            st.session_state.workflow_state['completed_steps'].append('sagemaker')
                        st.session_state.workflow_state['current_step'] = 'diagram'
                        st.warning("⚠️ Design was slightly truncated but still usable. Proceeding...")
                        import time
                        time.sleep(1)
                        st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ Error generating SageMaker architecture: {str(e)}")
                        st.session_state.workflow_state['errors']['sagemaker'] = str(e)
                        logger.error(f"SageMaker generation error: {e}", exc_info=True)
            
            with col2:
                if st.button("⏭️ Skip SageMaker Design", help="Skip architecture design and proceed to TCO analysis", use_container_width=True):
                    st.info("Skipping SageMaker architecture design. Proceeding directly to TCO analysis.")
                    
                    # Save a note that this was skipped
                    skip_note = "SageMaker architecture design was skipped by user. Proceeding with TCO analysis based on current architecture."
                    self.save_interaction('SageMaker Agent', "User skipped SageMaker design", skip_note, 'sagemaker')
                    
                    # Mark step as complete
                    if 'sagemaker' not in st.session_state.workflow_state['completed_steps']:
                        st.session_state.workflow_state['completed_steps'].append('sagemaker')
                    
                    # Skip diagram and go to TCO
                    if 'diagram' not in st.session_state.workflow_state['completed_steps']:
                        st.session_state.workflow_state['completed_steps'].append('diagram')
                    
                    st.session_state.workflow_state['current_step'] = 'tco'
                    
                    # Small delay to show message
                    import time
                    time.sleep(1)
                    
                    st.rerun()
                    logger.error(f"SageMaker generation error: {e}", exc_info=True)
        
        # Display SageMaker response if available (for page refreshes or navigation back)
        elif sagemaker_response:
            st.markdown("### 🎯 SageMaker Architecture Design")
            
            # Get the output
            output = sagemaker_response.get('output', '')
            
            if output and len(str(output).strip()) > 0:
                # Display the architecture design cleanly
                st.markdown(output)
                
                # Add download option
                st.download_button(
                    label="📥 Download Architecture Design",
                    data=output,
                    file_name=f"sagemaker_architecture_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
                
                # Navigation buttons
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("⬅️ Back to Q&A"):
                        st.session_state.workflow_state['current_step'] = 'qa'
                        st.rerun()
                with col2:
                    if st.button("➡️ Continue to Diagrams"):
                        st.session_state.workflow_state['current_step'] = 'diagram'
                        st.rerun()
            else:
                st.warning("⚠️ No SageMaker architecture design available.")
                
                # Option to regenerate
                if st.button("🔄 Regenerate Architecture Design"):
                    if 'sagemaker' in st.session_state.workflow_state['agent_responses']:
                        del st.session_state.workflow_state['agent_responses']['sagemaker']
                    if 'sagemaker' in st.session_state.workflow_state['completed_steps']:
                        st.session_state.workflow_state['completed_steps'].remove('sagemaker')
                    st.rerun()
            
            # Add a divider before next step button
            st.markdown("---")
            st.info("✅ SageMaker architecture design is complete. You can now proceed to generate architecture diagrams.")
    
    def handle_diagram_step(self):
        """Handle diagram generation step using DiagramGenerator class"""
        st.markdown('<div class="step-header">📊 Step 4: Architecture Diagram Generation</div>', unsafe_allow_html=True)
        
        sagemaker_response = st.session_state.workflow_state['agent_responses'].get('sagemaker', {})
        diagram_response = st.session_state.workflow_state['agent_responses'].get('diagram', {})
        
        # Check if diagram generation was already attempted
        if not diagram_response and sagemaker_response:
            st.info("📊 Architecture diagrams provide visual representation of your SageMaker design.")
            
            st.markdown("**Note:** Diagram generation uses AWS Bedrock and may occasionally experience service issues.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🎨 Generate Architecture Diagram", help="Generate visual architecture diagrams"):
                    try:
                        progress = st.empty()
                        progress.info("🔄 Initializing diagram generation tools...")
                        
                        # Import DiagramGenerator
                        from diagram_generator import DiagramGenerator
                        from path_utils import get_workspace_dir
                        
                        # Get workspace directory - handles both local and ECS/Fargate
                        workspace_dir = get_workspace_dir()
                        logger.info(f"Workspace directory: {workspace_dir}")
                        
                        # Create DiagramGenerator instance
                        diagram_gen = DiagramGenerator(
                            workspace_dir=workspace_dir,
                            bedrock_model=st.session_state.bedrock_model,
                            system_prompt=DIAGRAM_GENERATION_SYSTEM_PROMPT,
                            user_prompt=DIAGRAM_GENERATION_USER_PROMPT
                        )
                        
                        progress.info("🎨 Generating architecture diagrams with AI...")
                        progress.info("⏳ This may take 60-120 seconds...")
                        
                        # Generate diagrams
                        architecture_design = str(sagemaker_response.get('output', ''))
                        result = diagram_gen.generate_diagram(architecture_design)
                        
                        # Show success message with diagram count
                        if result.get('status') == 'success':
                            diagram_count = len(result.get('diagram_paths', []))
                            progress.success(f"✅ Generated {diagram_count} diagram(s) successfully!")
                        
                        progress.info("💾 Saving diagram information...")
                        
                        # Save interaction
                        self.save_interaction(
                            'Diagram Agent',
                            f"Architecture design (length: {len(architecture_design)} chars)",
                            result['response'],
                            'diagram'
                        )
                        
                        # Mark step as complete
                        if 'diagram' not in st.session_state.workflow_state['completed_steps']:
                            st.session_state.workflow_state['completed_steps'].append('diagram')
                        st.session_state.workflow_state['current_step'] = 'tco'
                        
                        progress.empty()
                        
                        # Show result based on status
                        if result['status'] == 'success':
                            st.success(f"✅ Diagram generated! Found {len(result['diagram_paths'])} diagram(s) in {result['folder']}")
                            
                            # Display diagram info
                            for path in result['diagram_paths']:
                                file_size = os.path.getsize(path)
                                st.info(f"📄 {os.path.basename(path)} ({file_size:,} bytes)")
                        
                        elif result['status'] == 'no_files':
                            st.warning("⚠️ Diagram generation completed, but no image files were found. Check the response below for details.")
                        
                        elif result['status'] == 'error':
                            st.error(f"❌ Diagram generation failed: {result['error']}")
                            
                            # Check if it's a Bedrock service error
                            if "serviceUnavailableException" in result['error'] or "Bedrock is unable to process" in result['error']:
                                st.warning("⚠️ AWS Bedrock service is temporarily unavailable. This is a transient issue.")
                                st.info("💡 You can retry later or skip this step to continue with the migration analysis.")
                            
                            # Save error
                            st.session_state.workflow_state['errors']['diagram'] = result['error']
                        
                        # Show the response
                        if result['response']:
                            st.markdown("**Diagram Generation Response:**")
                            st.write(result['response'])
                        
                        st.rerun()
                    
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Diagram generation error: {error_msg}", exc_info=True)
                        
                        st.error(f"❌ Diagram generation failed: {error_msg}")
                        
                        # Save error information
                        self.save_interaction('Diagram Agent', "Diagram generation attempted", f"ERROR: {error_msg}", 'diagram')
                        st.session_state.workflow_state['errors']['diagram'] = error_msg
            
            with col2:
                if st.button("⏭️ Skip Diagram Generation", help="Continue without generating diagrams"):
                    st.info("Skipping diagram generation. You can generate diagrams later if needed.")
                    
                    # Mark as completed with skip note
                    self.save_interaction('Diagram Agent', "User skipped diagram generation", "Diagram generation skipped by user", 'diagram')
                    if 'diagram' not in st.session_state.workflow_state['completed_steps']:
                        st.session_state.workflow_state['completed_steps'].append('diagram')
                    st.session_state.workflow_state['current_step'] = 'tco'
                    
                    st.rerun()
        
        # Display diagram response if available
        diagram_response = st.session_state.workflow_state['agent_responses'].get('diagram', {})
        if diagram_response:
            st.markdown("### 📊 Architecture Diagrams")
            
            st.info("💡 **About these diagrams**: Visual representations of your proposed SageMaker architecture showing components, data flow, and service interactions.")
            
            # Try to display generated diagrams
            try:
                from diagram_generator import DiagramGenerator
                
                # Get workspace directory - handles both local and ECS/Fargate
                from path_utils import get_workspace_dir
                workspace_dir = get_workspace_dir()
                
                diagram_gen = DiagramGenerator(
                    workspace_dir=workspace_dir,
                    bedrock_model=st.session_state.bedrock_model,
                    system_prompt=DIAGRAM_GENERATION_SYSTEM_PROMPT,
                    user_prompt=DIAGRAM_GENERATION_USER_PROMPT
                )
                
                diagram_files = diagram_gen._list_diagram_files()
                
                if diagram_files:
                    st.markdown("**Generated Architecture Diagrams:**")
                    
                    # Display diagrams in a clean grid
                    for idx, img_path in enumerate(diagram_files, 1):
                        try:
                            # Get diagram name for description
                            diagram_name = os.path.basename(img_path).replace('_', ' ').replace('.png', '').title()
                            
                            st.markdown(f"**Diagram {idx}: {diagram_name}**")
                            st.image(img_path, width=700, caption=f"Architecture diagram showing {diagram_name.lower()}")
                            st.markdown("---")
                        except Exception as e:
                            st.warning(f"Could not display diagram: {os.path.basename(img_path)}")
                            logger.error(f"Error displaying diagram {img_path}: {e}", exc_info=True)
                else:
                    st.info("✅ Diagram generation completed. Diagrams will be included in the final PDF report.")
            
            except Exception as e:
                st.info("✅ Diagram generation completed. Diagrams will be included in the final PDF report.")
                logger.error(f"Error in diagram display: {e}", exc_info=True)
            
            # Navigation buttons
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("⬅️ Back to SageMaker Design"):
                    st.session_state.workflow_state['current_step'] = 'sagemaker'
                    st.rerun()
            with col2:
                if st.button("➡️ Continue to TCO Analysis"):
                    st.session_state.workflow_state['current_step'] = 'tco'
                    st.rerun()
    
    def handle_tco_step(self):
        """Handle TCO analysis step"""
        st.markdown('<div class="step-header">💰 Step 5: Total Cost of Ownership Analysis</div>', unsafe_allow_html=True)
        
        qa_response = st.session_state.workflow_state['agent_responses'].get('qa', {})
        sagemaker_response = st.session_state.workflow_state['agent_responses'].get('sagemaker', {})
        
        if qa_response and sagemaker_response:
            # Optional: Collect additional cost parameters
            with st.expander("🔧 Optional: Provide Additional Cost Information"):
                st.markdown("**Current Infrastructure Details (Optional):**")
                
                col1, col2 = st.columns(2)
                with col1:
                    current_monthly_cost = st.number_input("Current monthly infrastructure cost ($)", min_value=0, value=0, key="current_cost")
                    team_size = st.number_input("Team size (developers/data scientists)", min_value=1, value=5, key="team_size")
                
                with col2:
                    data_volume_gb = st.number_input("Monthly data volume (GB)", min_value=0, value=1000, key="data_volume")
                    training_frequency = st.selectbox("Training frequency", 
                                                    ["Daily", "Weekly", "Monthly", "Quarterly"], 
                                                    index=1, key="training_freq")
            
            if st.button("💹 Generate TCO Analysis"):
                try:
                    # Use st.status for better connection handling
                    with st.status("💹 Analyzing total cost of ownership...", expanded=True) as status:
                        st.write("📊 Analyzing current costs...")
                        st.write("⏳ This may take 45-75 seconds...")
                        
                        st.write("🔧 Creating TCO analysis agent...")
                        # Create TCO agent without user_input tool
                        tco_agent_no_input = Agent(
                            model=st.session_state.bedrock_model,
                            system_prompt=AWS_TCO_SYSTEM_PROMPT,
                            load_tools_from_directory=False,
                            conversation_manager=st.session_state.conversation_manager
                        )
                        
                        st.write("📝 Building cost analysis...")
                        # Build comprehensive TCO input
                        additional_info = f"""
ADDITIONAL COST PARAMETERS:
- Current monthly cost: ${current_monthly_cost if current_monthly_cost > 0 else 'Not specified'}
- Team size: {team_size} people
- Data volume: {data_volume_gb} GB/month
- Training frequency: {training_frequency}
"""
                        
                        tco_input = str(qa_response.get('output', '')) + "\n" + str(sagemaker_response.get('output', '')) + "\n" + additional_info + "\n" + AWS_TCO_USER_PROMPT
                        
                        st.write("🔄 Calling AI model for cost analysis...")
                        response = tco_agent_no_input(tco_input)
                        
                        st.write("💾 Saving analysis...")
                        self.save_interaction('TCO Agent', tco_input, str(response), 'tco')
                        st.session_state.workflow_state['completed_steps'].append('tco')
                        st.session_state.workflow_state['current_step'] = 'navigator'
                        
                        status.update(label="✅ TCO analysis complete!", state="complete")
                        st.success("✅ TCO analysis completed successfully!")
                        
                        # Small delay
                        import time
                        time.sleep(1)
                        
                        st.rerun()
                
                except MaxTokensReachedException as e:
                    logger.warning("TCO analysis hit max_tokens limit, using partial response")
                    partial = str(getattr(e, 'message', '')) or "TCO analysis was truncated due to response length limits."
                    self.save_interaction('TCO Agent', tco_input, partial, 'tco')
                    st.session_state.workflow_state['completed_steps'].append('tco')
                    st.session_state.workflow_state['current_step'] = 'navigator'
                    st.warning("⚠️ TCO analysis was slightly truncated but still usable. Proceeding...")
                    import time
                    time.sleep(1)
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error generating TCO analysis: {str(e)}")
                    st.session_state.workflow_state['errors']['tco'] = str(e)
        
        # Display TCO response if available
        tco_response = st.session_state.workflow_state['agent_responses'].get('tco', {})
        if tco_response:
            st.markdown('<div class="agent-response">', unsafe_allow_html=True)
            st.markdown("**TCO Analysis:**")
            st.write(tco_response.get('output', ''))
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Navigation buttons
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("⬅️ Back to Diagrams"):
                    st.session_state.workflow_state['current_step'] = 'diagram'
                    st.rerun()
            with col2:
                if st.button("➡️ Continue to Roadmap"):
                    st.session_state.workflow_state['current_step'] = 'navigator'
                    st.rerun()
    
    def handle_navigator_step(self):
        """Handle migration roadmap step"""
        st.markdown('<div class="step-header">🗺️ Step 6: Migration Roadmap</div>', unsafe_allow_html=True)
        
        sagemaker_response = st.session_state.workflow_state['agent_responses'].get('sagemaker', {})
        
        if sagemaker_response:
            # Migration Roadmap Configuration
            st.markdown("### 🎯 Roadmap Configuration")
            
            # Number of steps input - prominently displayed
            col1, col2 = st.columns([2, 3])
            with col1:
                num_steps = st.selectbox(
                    "**How many steps would you like in your migration roadmap?**",
                    options=[3, 5, 7, 10, 12],
                    index=2,  # Default to 7 steps
                    key="roadmap_steps",
                    help="Choose the level of detail for your migration roadmap. More steps provide more granular guidance."
                )
            
            with col2:
                st.info(f"📋 **Selected: {num_steps} steps**\n\n"
                       f"• **3 steps**: High-level phases\n"
                       f"• **5 steps**: Balanced approach\n"
                       f"• **7 steps**: Detailed guidance (recommended)\n"
                       f"• **10 steps**: Very detailed\n"
                       f"• **12 steps**: Maximum granularity")
            
            # Optional: Collect additional migration preferences
            with st.expander("🔧 Advanced Migration Preferences (Optional)"):
                st.markdown("**Migration Timeline and Constraints:**")
                
                col1, col2 = st.columns(2)
                with col1:
                    timeline = st.selectbox("Preferred migration timeline", 
                                          ["3 months", "6 months", "12 months", "18+ months"], 
                                          index=1, key="migration_timeline")
                    risk_tolerance = st.selectbox("Risk tolerance", 
                                                ["Conservative", "Moderate", "Aggressive"], 
                                                index=1, key="risk_tolerance")
                
                with col2:
                    downtime_tolerance = st.selectbox("Acceptable downtime", 
                                                    ["Zero downtime", "Minimal (< 1 hour)", "Moderate (< 4 hours)", "Flexible"], 
                                                    index=0, key="downtime_tolerance")
                    team_experience = st.selectbox("Team AWS experience", 
                                                 ["Beginner", "Intermediate", "Advanced"], 
                                                 index=1, key="team_experience")
            
            # Display current configuration
            st.markdown("---")
            st.markdown("### 📋 Current Configuration")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Roadmap Steps", num_steps, help="Number of steps in the migration roadmap")
            with col2:
                st.metric("Timeline", timeline, help="Preferred migration timeline")
            with col3:
                st.metric("Risk Level", risk_tolerance, help="Risk tolerance for the migration")
            
            if st.button("🛣️ Generate Migration Roadmap", help=f"Generate a {num_steps}-step migration roadmap"):
                try:
                    with st.spinner("Creating migration roadmap..."):
                        # Create Navigator agent without user_input tool
                        navigator_agent_no_input = Agent(
                            model=st.session_state.bedrock_model,
                            system_prompt=ARCHITECTURE_NAVIGATOR_SYSTEM_PROMPT,
                            load_tools_from_directory=False,
                            conversation_manager=st.session_state.conversation_manager
                        )
                        
                        # Build comprehensive navigator input
                        migration_preferences = f"""
ROADMAP CONFIGURATION:
- Number of steps requested: {num_steps} steps
- Provide exactly {num_steps} distinct, actionable steps in the migration roadmap

MIGRATION PREFERENCES:
- Timeline: {timeline}
- Risk tolerance: {risk_tolerance}
- Downtime tolerance: {downtime_tolerance}
- Team AWS experience: {team_experience}
"""
                        
                        # Enhanced prompt with specific step count
                        enhanced_prompt = f"""
{ARCHITECTURE_NAVIGATOR_USER_PROMPT}

IMPORTANT: Generate exactly {num_steps} steps in your migration roadmap. Each step should be:
1. Clearly numbered (Step 1, Step 2, etc.)
2. Have a descriptive title
3. Include specific actions and deliverables
4. Mention timeline estimates
5. List AWS services involved
6. Explain benefits and impact

Format your response with clear step headers and detailed descriptions for each of the {num_steps} steps.
"""
                        
                        navigator_input = str(sagemaker_response.get('output', '')) + "\n" + migration_preferences + "\n" + enhanced_prompt
                        
                        response = navigator_agent_no_input(navigator_input)
                        
                        self.save_interaction('Navigator Agent', navigator_input, str(response), 'navigator')
                        st.session_state.workflow_state['completed_steps'].append('navigator')
                        st.session_state.workflow_state['current_step'] = 'complete'
                        
                        st.rerun()
                
                except MaxTokensReachedException as e:
                    logger.warning("Navigator hit max_tokens limit, using partial response")
                    partial = str(getattr(e, 'message', '')) or "Migration roadmap was truncated due to response length limits."
                    self.save_interaction('Navigator Agent', navigator_input, partial, 'navigator')
                    st.session_state.workflow_state['completed_steps'].append('navigator')
                    st.session_state.workflow_state['current_step'] = 'complete'
                    st.warning("⚠️ Roadmap was slightly truncated but still usable. Proceeding...")
                    import time
                    time.sleep(1)
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Error generating migration roadmap: {str(e)}")
                    st.session_state.workflow_state['errors']['navigator'] = str(e)
        
        # Display Navigator response if available
        navigator_response = st.session_state.workflow_state['agent_responses'].get('navigator', {})
        if navigator_response:
            st.markdown('<div class="agent-response">', unsafe_allow_html=True)
            st.markdown("**Migration Roadmap:**")
            st.write(navigator_response.get('output', ''))
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Navigation buttons
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("⬅️ Back to TCO Analysis"):
                    st.session_state.workflow_state['current_step'] = 'tco'
                    st.rerun()
            with col2:
                if st.button("➡️ Continue to Summary"):
                    st.session_state.workflow_state['current_step'] = 'complete'
                    st.rerun()
    
    def handle_complete_step(self):
        """Handle workflow completion"""
        st.markdown('<div class="step-header">🎉 Workflow Complete!</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.markdown("**✅ Migration analysis completed successfully!**")
        st.markdown("All steps have been completed. You can now:")
        st.markdown("- Review the results in the sidebar")
        st.markdown("- Download the complete analysis")
        st.markdown("- Start a new workflow")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display summary of all results
        st.markdown("### 📋 Complete Analysis Summary")
        
        for step in ['description', 'qa', 'sagemaker', 'tco', 'navigator']:
            response = st.session_state.workflow_state['agent_responses'].get(step, {})
            if response:
                with st.expander(f"📄 {step.title()} Results"):
                    st.write(response.get('output', ''))
    
    def run(self):
        """Main application runner"""
        # Header
        st.markdown('<div class="main-header">🚀 SageMaker Migration Advisor Lite</div>', unsafe_allow_html=True)
        
        # Sidebar
        self.display_sidebar()
        
        # Main content based on current step
        current_step = st.session_state.workflow_state['current_step']
        
        if current_step == 'input':
            self.handle_architecture_input()
        elif current_step == 'description':
            self.handle_description_view()
        elif current_step == 'qa':
            self.handle_qa_step()
        elif current_step == 'sagemaker':
            self.handle_sagemaker_step()
        elif current_step == 'diagram':
            self.handle_diagram_step()
        elif current_step == 'tco':
            self.handle_tco_step()
        elif current_step == 'navigator':
            self.handle_navigator_step()
        elif current_step == 'complete':
            self.handle_complete_step()
        
        # Display errors if any
        if st.session_state.workflow_state['errors']:
            st.markdown("### ⚠️ Errors Encountered")
            for step, error in st.session_state.workflow_state['errors'].items():
                st.markdown(f'<div class="error-box"><strong>{step.title()} Error:</strong><br>{error}</div>', unsafe_allow_html=True)
    
    def handle_description_view(self):
        """Display the architecture description/analysis when navigating back"""
        st.markdown('<div class="step-header">📋 Architecture Analysis (Review)</div>', unsafe_allow_html=True)
        
        desc_response = st.session_state.workflow_state['agent_responses'].get('description', {})
        
        if desc_response:
            st.markdown('<div class="agent-response">', unsafe_allow_html=True)
            st.markdown("**Architecture Analysis:**")
            st.write(desc_response.get('output', ''))
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Show input that was used
            user_inputs = st.session_state.workflow_state.get('user_inputs', {})
            if 'description' in user_inputs:
                with st.expander("📝 View Original Input"):
                    st.text_area("Original Description:", user_inputs['description'], height=200, disabled=True)
            elif 'diagram_path' in user_inputs:
                with st.expander("🖼️ View Original Diagram"):
                    try:
                        img = Image.open(user_inputs['diagram_path'])
                        st.image(img, caption="Original Architecture Diagram")
                    except:
                        st.info(f"Diagram path: {user_inputs['diagram_path']}")
            
            st.markdown("---")
            
            # Navigation buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("⬅️ Back to Input"):
                    st.session_state.workflow_state['current_step'] = 'input'
                    st.rerun()
            with col2:
                if st.button("➡️ Continue to Q&A"):
                    st.session_state.workflow_state['current_step'] = 'qa'
                    st.rerun()
        else:
            st.warning("No architecture analysis data available.")
            if st.button("⬅️ Back to Input"):
                st.session_state.workflow_state['current_step'] = 'input'
                st.rerun()

def main():
    """Main function to run the Streamlit app"""
    try:
        app = SageMakerAdvisorApp()
        app.run()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.error("Please check your AWS credentials and Bedrock model access.")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()