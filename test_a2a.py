"""
Test A2A integration between ADK and CrewAI
"""

import asyncio
from Smart_News_Aggregator.agent import root_agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import uuid

async def test_crewai_analysis():
    """Test ADK agent calling CrewAI for analysis"""
    
    print("🤖 Testing A2A: ADK → CrewAI Integration\n")
    
    # Initialize ADK session
    session_service = InMemorySessionService()
    session_id = str(uuid.uuid4())
    user_id = "test_user"
    app_name = "A2A_Test"
    
    # Create session
    state_context = {
        "user_preferences": {
            "language": "en",
            "style": "professional",
            "email": "test@example.com"
        }
    }
    
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state=state_context
    )
    
    # Create runner
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name=app_name
    )
    
    # Test queries that trigger CrewAI analysis
    test_queries = [
        "Get sports news and analyze trends",
        "Fetch national news and fact-check the articles",
        "Show me entertainment news with comprehensive analysis"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        
        user_message = types.Content(parts=[types.Part(text=query)])
        
        # Run agent
        for event in runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            if event.content and event.content.parts:
                msg = event.content.parts[0].text
                print(f"Agent Response: {msg[:200]}...")
                
                if event.is_final_response():
                    print(f"\n✅ Final Response Received")
        
        # Check state for CrewAI analysis
        final_session = await session_service.get_session(app_name, user_id, session_id)
        if "crewai_analysis" in final_session.state:
            print(f"\n🎯 CrewAI Analysis:")
            print(final_session.state["crewai_analysis"])
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_crewai_analysis())