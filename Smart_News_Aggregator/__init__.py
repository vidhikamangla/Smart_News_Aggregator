from . import agent_old
# Original agent
# from .agent import root_agent

#Enhanced agent with MCP & A2A
from .agent import root_agent as enhanced_root_agent
from .agent  import get__agent_async

# NEW: MCP server (for external exposure)
from . import mcp_server

# NEW: CrewAI bridge
from . import crewai_bridge_agent

__all__ = [
    'root_agent',              # Original
    'enhanced_root_agent',     # Enhanced version
    'get_agent_async', # MCP consumer
    'mcp_server',
    'crewai_bridge_agent'
]