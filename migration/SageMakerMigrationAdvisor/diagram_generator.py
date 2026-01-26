"""
Diagram Generator Component for SageMaker Migration Advisor
Handles architecture diagram generation using AWS Diagram MCP Server
"""

import os
from typing import Dict, Any, List
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands_tools import image_reader, use_llm, load_tool
from logger_config import logger


class DiagramGenerator:
    """Handles diagram generation using MCP server with proper workspace management"""
    
    def __init__(self, workspace_dir: str, bedrock_model, system_prompt: str, user_prompt: str):
        """
        Initialize DiagramGenerator with workspace directory
        
        Args:
            workspace_dir: Base directory for the application workspace
            bedrock_model: Bedrock model instance for AI generation
            system_prompt: System prompt for diagram generation agent
            user_prompt: User prompt template for diagram generation
        """
        self.workspace_dir = workspace_dir
        self.bedrock_model = bedrock_model
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.diagram_folder = os.path.join(workspace_dir, 'generated-diagrams')
        self._ensure_diagram_folder()
    
    def _ensure_diagram_folder(self):
        """Create diagram folder if it doesn't exist"""
        try:
            os.makedirs(self.diagram_folder, exist_ok=True)
            logger.info(f"Diagram folder ready: {os.path.abspath(self.diagram_folder)}")
        except Exception as e:
            logger.error(f"Failed to create diagram folder: {e}", exc_info=True)
            raise
    
    def generate_diagram(self, architecture_design: str) -> Dict[str, Any]:
        """
        Generate architecture diagram from design
        
        Args:
            architecture_design: SageMaker architecture design text
            
        Returns:
            Dict with status, diagram_paths, response, and any errors
        """
        try:
            logger.info("Starting diagram generation process")
            logger.info(f"Workspace directory: {self.workspace_dir}")
            logger.info(f"Diagram folder: {self.diagram_folder}")
            
            # Setup MCP client with proper configuration
            logger.info("Initializing MCP client for diagram generation")
            mcp_client = MCPClient(lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=["awslabs.aws-diagram-mcp-server"]
                )
            ))
            
            with mcp_client:
                # Get available tools from MCP server
                tools = mcp_client.list_tools_sync() + [image_reader, use_llm, load_tool]
                logger.info(f"Available tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]}")
                
                # Create diagram agent
                diagram_agent = Agent(
                    model=self.bedrock_model,
                    tools=tools,
                    system_prompt=self.system_prompt,
                    load_tools_from_directory=False
                )
                
                # Build prompt with workspace directory
                prompt = f"""
{architecture_design}

{self.user_prompt}

CRITICAL INSTRUCTIONS:
- Save all diagrams to the workspace directory: {self.workspace_dir}
- Use the workspace_dir parameter when calling diagram generation tools
- Ensure diagrams are saved to: {self.diagram_folder}
- Generate clear, professional architecture diagrams
"""
                
                logger.info(f"Sending prompt to diagram agent (length: {len(prompt)} chars)")
                
                # Generate diagram
                response = diagram_agent(prompt)
                response_str = str(response)
                
                logger.info(f"Diagram agent response received (length: {len(response_str)} chars)")
                logger.info(f"Response preview: {response_str[:200]}...")
                
                # Verify diagrams were created
                diagram_files = self._list_diagram_files()
                
                if diagram_files:
                    logger.info(f"Successfully generated {len(diagram_files)} diagram(s)")
                    for file_path in diagram_files:
                        file_size = os.path.getsize(file_path)
                        logger.info(f"  - {os.path.basename(file_path)} ({file_size:,} bytes)")
                else:
                    logger.warning("No diagram files found after generation")
                
                return {
                    'status': 'success' if diagram_files else 'no_files',
                    'diagram_paths': diagram_files,
                    'response': response_str,
                    'folder': self.diagram_folder,
                    'error': None
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Diagram generation failed: {error_msg}", exc_info=True)
            
            return {
                'status': 'error',
                'diagram_paths': [],
                'response': '',
                'folder': self.diagram_folder,
                'error': error_msg
            }
    
    def _list_diagram_files(self) -> List[str]:
        """
        List all diagram files in the diagram folder
        
        Returns:
            List of full paths to diagram files
        """
        if not os.path.exists(self.diagram_folder):
            logger.warning(f"Diagram folder does not exist: {self.diagram_folder}")
            return []
        
        files = []
        try:
            for filename in os.listdir(self.diagram_folder):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                    full_path = os.path.join(self.diagram_folder, filename)
                    
                    # Only include files with non-zero size
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        files.append(full_path)
                        logger.debug(f"Found diagram file: {filename} ({os.path.getsize(full_path)} bytes)")
                    else:
                        logger.warning(f"Skipping empty or missing file: {filename}")
        
        except Exception as e:
            logger.error(f"Error listing diagram files: {e}", exc_info=True)
        
        return files
    
    def get_diagram_count(self) -> int:
        """
        Get the count of generated diagrams
        
        Returns:
            Number of diagram files in the folder
        """
        return len(self._list_diagram_files())
    
    def clear_diagrams(self):
        """Clear all diagrams from the diagram folder"""
        try:
            diagram_files = self._list_diagram_files()
            for file_path in diagram_files:
                os.remove(file_path)
                logger.info(f"Removed diagram: {os.path.basename(file_path)}")
            
            logger.info(f"Cleared {len(diagram_files)} diagram(s)")
        except Exception as e:
            logger.error(f"Error clearing diagrams: {e}", exc_info=True)
