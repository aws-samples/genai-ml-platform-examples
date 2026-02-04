""" 
Program: sagemaker_migration_advisor_cli.py 

Description: An agentic AI advisory application that streamlines platform modernization by first interpreting the current-state architecture directly from diagrams or descriptive inputs, 
proactively asking clarifying questions to resolve ambiguities and ensure accuracy. It then designs a modern, layered target architecture with clear explanations of each component and its role, 
while delivering a concise comparison of costs and a summary of key technical and operational improvements. The application produces a pragmatic migration roadmap, complemented 
by a detailed total cost of ownership (TCO) analysis, and provides step-by-step guidance for executing a phased migration to the SageMaker platform—enabling teams to move 
from assessment to execution with confidence, clarity, and measurable business impact. 
"""

# Import necessary libraries
from strands import Agent
from strands_tools import http_request, image_reader, use_llm, load_tool

from tools import user_prompt as user_input
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import http_request, image_reader, use_llm, load_tool
from mcp import stdio_client, StdioServerParameters
from logger_config import logger
from strands.agent.conversation_manager import SlidingWindowConversationManager
import datetime
import os


conversation_manager = SlidingWindowConversationManager(
    window_size=20,
)

from prompts import (
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

# Capture agent inputs/outputs for troubleshooting

output_file = "agent_inputs_outputs.txt"

def write_agent_interaction(agent_name, input_prompt, output, append_to_file=True):
    """Write agent input and output to file with timestamp and formatting"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 80
    input_separator = "-" * 40
    
    formatted_interaction = f"""
{separator}
[{timestamp}] {agent_name.upper()} INTERACTION
{separator}

INPUT:
{input_separator}
{input_prompt}

OUTPUT:
{input_separator}
{output}

"""
    
    mode = "a" if append_to_file and os.path.exists(output_file) else "w"
    with open(output_file, mode, encoding="utf-8") as f:
        f.write(formatted_interaction)
    
    print(f"✓ {agent_name} input/output saved to {output_file}")

def write_user_prompt(prompt_type, user_input_text, append_to_file=True):
    """Write user prompts to file with timestamp and formatting"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 80
    
    formatted_prompt = f"""
{separator}
[{timestamp}] USER INPUT - {prompt_type.upper()}
{separator}
{user_input_text}

"""
    
    mode = "a" if append_to_file and os.path.exists(output_file) else "w"
    with open(output_file, mode, encoding="utf-8") as f:
        f.write(formatted_prompt)
    
    print(f"✓ User {prompt_type} saved to {output_file}")

logger.info("Starting the architecture workflow...")

# Write workflow start to output file
write_user_prompt("Workflow Start", f"Architecture workflow started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# Setup bedrock model instance for using with
try:
    # First try Claude 3 Haiku (most widely available with on-demand)
    bedrock_model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",  
        region_name='us-west-2',
        temperature=0.0
    )
    logger.info("Using Claude 4.5 Sonnet model")
except Exception as e:
    logger.warning(f"Claude 4.5 Sonnet not available: {e}")
    try:
        # Fallback to Claude 3 Sonnet
        bedrock_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",  
            region_name='us-west-2',
            temperature=0.0
        )
        logger.info("Using Claude 4 Sonnet model")
        
    except Exception as e2:
        logger.warning(f"Claude 4 Sonnet not available: {e2}")
        try:
            # Try different region as final fallback
            bedrock_model = BedrockModel(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  
                region_name='us-west-2',
                temperature=0.0
            )
            logger.info("Using Claude 3.7 Sonnet model in us-west-2")
        except Exception as e3:
            logger.error(f"All Claude models failed: {e3}")
            raise Exception("No Claude models available. Please check your AWS Bedrock access and model permissions.")

#setup Q&A Agent for user interfaction
question_answer_agent = Agent(
        tools=[user_input],
        model=bedrock_model,
        system_prompt=QUESTION_SYSTEM_PROMPT,
        load_tools_from_directory=False,
        conversation_manager=conversation_manager
)

#setup perspectives agent for knowledge base articles 
aws_perspective_agent = Agent(
    tools=[http_request, image_reader, use_llm, load_tool],
    model=bedrock_model,
    system_prompt=AWS_PERSPECTIVES_SYSTEM_PROMPT,
    load_tools_from_directory=False,
    conversation_manager=conversation_manager
)

#setup architecture diagram interpreter agent
architecture_description_system_agent = Agent(
        tools=[http_request, image_reader, load_tool, use_llm, user_input],
        model=bedrock_model,
        system_prompt=architecture_description_system_prompt,
        load_tools_from_directory=False,
        conversation_manager=conversation_manager
)


# Capture architecture description from user

USER_PROMPT = """
Please describe your GenAI/ML migration use case in detail:
"""
has_diagram = input("Do you have an architecture diagram? (yes/no)").lower()
write_user_prompt("Diagram Question Response", f"Has diagram: {has_diagram}")

if "yes" in has_diagram:
    diagram_path = input("\nPlease provide the full path to the architecture diagram image:")
    write_user_prompt("Diagram Path", diagram_path)
    user_prompt = f"Read the diagram from location {diagram_path} and describe the architecture in detail, focusing on components, interactions, and patterns. Use bullet points for clarity."
    logger.info(f"Received diagram path: {diagram_path}")
    description = architecture_description_system_agent(user_prompt)
    logger.info(f"Architecture description generated from diagram. {description}")
    write_agent_interaction("Architecture Description Agent (Diagram)", user_prompt, description)
else:
    logger.info("User does not have an architecture diagram.")
    arch_description = input("\nPlease describe your GenAI/ML migration use case in detail:")
    write_user_prompt("Architecture Description", arch_description)
    description = architecture_description_system_agent(arch_description)
    logger.info(f"Architecture description generated from text. {description}")
    write_agent_interaction("Architecture Description Agent (Text)", arch_description, description)


print("******")
description1 = str(description)+ "\n With the above description,  if any ambiguous or unclear elements ask questions answer the following questions:\n" + USER_PROMPT 
description2 = question_answer_agent(description1)
write_agent_interaction("Question Answer Agent", description1, description2)


#SageMaker Modernization Agent

sagemaker_agent = Agent(
    model=bedrock_model,
    system_prompt=SAGEMAKER_SYSTEM_PROMPT,
    load_tools_from_directory=False,
    conversation_manager=conversation_manager
)
sagemaker_input = str(description2)+ "\n"+SAGEMAKER_USER_PROMPT
sagemaker_description = sagemaker_agent(sagemaker_input)
write_agent_interaction("SageMaker Agent", sagemaker_input, sagemaker_description)


#Arch diagram generation Agent

domain_name_tools = MCPClient(lambda: stdio_client(
    StdioServerParameters(command="uvx", args=["awslabs.aws-diagram-mcp-server"])
))
try:
    with domain_name_tools:
        tools = domain_name_tools.list_tools_sync()+[image_reader, use_llm, load_tool]
        diagram_generation_agent = Agent(
            model=bedrock_model,
            tools=tools,
            system_prompt=DIAGRAM_GENERATION_SYSTEM_PROMPT,
            load_tools_from_directory=False
        )
        diagram_input = str(sagemaker_description)+ "\n"+DIAGRAM_GENERATION_USER_PROMPT
        diagram = diagram_generation_agent(diagram_input)
        write_agent_interaction("Diagram Generation Agent", diagram_input, diagram)
except Exception as e:
    logger.error(f"Diagram generation failed: {e}")
    diagram = "Diagram generation failed due to image size constraints or model limitations. Please check the generated-diagrams folder for any partial outputs."
    write_agent_interaction("Diagram Generation Agent", diagram_input, f"ERROR: {diagram}")
    print(f"⚠️ Diagram generation failed: {e}")
    print("Continuing with remaining agents...")

#TCO Agent

tco_analysis_agent = Agent(
    model=bedrock_model,
    tools=[user_input],
    system_prompt=AWS_TCO_SYSTEM_PROMPT,
    load_tools_from_directory=False,
    conversation_manager=conversation_manager
)
tco_input = str(description2)+"\n"+str(sagemaker_description)+ "\n"+AWS_TCO_USER_PROMPT
tco_analysis = tco_analysis_agent(tco_input)
write_agent_interaction("TCO Analysis Agent", tco_input, tco_analysis)
print("TCO Analysis:", tco_analysis)
logger.info("TCO Analysis response: %s", tco_analysis)

#architecture navigator agent for step by step modernization journey

architecture_navigator_agent = Agent(
    model=bedrock_model,
    tools=[user_input],
    system_prompt=ARCHITECTURE_NAVIGATOR_SYSTEM_PROMPT,
    load_tools_from_directory=False,
    conversation_manager=conversation_manager
)
navigator_input = str(sagemaker_description)+ "\n"+ARCHITECTURE_NAVIGATOR_USER_PROMPT
architecture_navigator = architecture_navigator_agent(navigator_input)
write_agent_interaction("Architecture Navigator Agent", navigator_input, architecture_navigator)
print("Architecture Navigator:", architecture_navigator)
logger.info("Architecture Navigator response: %s", architecture_navigator)


#Optional:  Uncomment the following section if you need to generated cloudformationt template

"""

cloudformation_agent = Agent(
    model=bedrock_model,
    system_prompt=CLOUDFORMATION_SYSTEM_PROMPT,
    load_tools_from_directory=False,
    conversation_manager=conversation_manager
)
cloudformation_input = str(sagemaker_description)+ "\n"+CLOUDFORMATION_USER_PROMPT
cloudformation_template = cloudformation_agent(cloudformation_input)
write_agent_interaction("CloudFormation Agent", cloudformation_input, cloudformation_template)
with open("generated_template.yaml", "w", encoding="utf-8") as f:
    f.write(str(cloudformation_template))
print("CloudFormation template generated and saved to 'generated_template.yaml")
logger.info("CloudFormation template generated and saved to 'generated_template.yaml'.")

"""
