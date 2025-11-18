"""
Test MCP Server - Verify tools are exposed correctly
"""

import asyncio
import json
from Smart_News_Aggregator.mcp_server import (
    get_sports_news_mcp,
    get_national_news_mcp,
    get_entertainment_news_mcp
)

async def test_mcp_tools():
    """Test MCP-wrapped news tools"""
    
    print("🔧 Testing MCP Tools\n")
    
    # Test 1: Sports News
    print("Test 1: Fetching sports news via MCP...")
    result = get_sports_news_mcp(limit=5)
    print(json.dumps(result, indent=2))
    print()
    
    # Test 2: National News
    print("Test 2: Fetching national news via MCP...")
    result = get_national_news_mcp(limit=5)
    print(json.dumps(result, indent=2))
    print()
    
    # Test 3: Entertainment News
    print("Test 3: Fetching entertainment news via MCP...")
    result = get_entertainment_news_mcp(limit=5)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(test_mcp_tools())