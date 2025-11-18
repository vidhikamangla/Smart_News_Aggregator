# crewai_bridge_agent.py
"""
Agent-to-Agent (A2A) Bridge for CrewAI Integration
This allows your ADK agent to communicate with a CrewAI-based agent
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# CrewAI imports
try:
    from crewai import Agent, Task, Crew, Process, LLM
    from langchain_groq import ChatGroq
    CREWAI_AVAILABLE = True
except ImportError:
    print("WARNING: CrewAI not installed. Install with: pip install crewai langchain-google-genai")
    CREWAI_AVAILABLE = False

# ADK imports
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

# --- CrewAI Agent Configuration ---
class NewsAnalysisCrewAI:
    """CrewAI-based agent for advanced news analysis and insights"""
    
    def __init__(self):
        if not CREWAI_AVAILABLE:
            raise ImportError("CrewAI is required but not installed")
        
        # Initialize LLM for CrewAI
        self.llm = ChatGroq(
            model="mixtral-8x7b-32768",   # or llama-3.1-70B-versatile
            api_key=os.getenv("GROQ_API_KEY")
        )
        
        # Define CrewAI agents
        self.news_analyst = Agent(
            role='Senior News Analyst',
            goal='Analyze news articles and provide deep insights',
            backstory="""You are an expert news analyst with years of experience 
            in identifying trends, biases, and key insights from news articles. 
            You excel at providing context and connecting different news stories.""",
            verbose=True,
            allow_delegation=False,
        )
        
        self.fact_checker = Agent(
            role='Fact Checker',
            goal='Verify claims and identify potential misinformation',
            backstory="""You are a meticulous fact-checker who cross-references 
            information and identifies potential inaccuracies or misleading claims 
            in news articles.""",
            verbose=True,
            allow_delegation=False,
        )
        
        self.trend_spotter = Agent(
            role='Trend Analyst',
            goal='Identify emerging trends and patterns in news',
            backstory="""You specialize in spotting emerging trends across multiple 
            news sources and categories. You can identify what's gaining momentum 
            and what's important.""",
            verbose=True,
            allow_delegation=False,
        )
    
    def analyze_news_batch(self, articles: List[Dict[str, Any]], 
                          analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Analyze a batch of news articles using CrewAI agents
        
        Args:
            articles: List of news article dictionaries
            analysis_type: Type of analysis (comprehensive, trends, fact_check)
        
        Returns:
            Analysis results from CrewAI crew
        """
        if not articles:
            return {"status": "error", "message": "No articles provided"}
        
        # Prepare article summaries for analysis
        article_text = "\n\n".join([
            f"Title: {a.get('title', 'N/A')}\n"
            f"Date: {a.get('date', 'N/A')}\n"
            f"Content: {a.get('article', 'N/A')[:500]}..."
            for a in articles[:10]  # Limit to 10 articles to avoid token limits
        ])
        
        # Define tasks based on analysis type
        if analysis_type == "comprehensive":
            tasks = [
                Task(
                    description=f"""Analyze these news articles and provide:
                    1. Main themes and topics
                    2. Sentiment analysis
                    3. Key takeaways
                    4. Notable quotes or claims
                    
                    Articles:
                    {article_text}
                    """,
                    agent=self.news_analyst,
                    expected_output="Detailed analysis with themes, sentiment, and key takeaways"
                ),
                Task(
                    description=f"""Review these articles for:
                    1. Factual accuracy concerns
                    2. Potential biases
                    3. Unverified claims
                    4. Recommendations for verification
                    
                    Articles:
                    {article_text}
                    """,
                    agent=self.fact_checker,
                    expected_output="Fact-checking report with concerns and recommendations"
                ),
                Task(
                    description=f"""Identify trends from these articles:
                    1. Emerging patterns
                    2. Topic momentum
                    3. Cross-category connections
                    4. Predictive insights
                    
                    Articles:
                    {article_text}
                    """,
                    agent=self.trend_spotter,
                    expected_output="Trend analysis with patterns and predictions"
                )
            ]
        elif analysis_type == "trends":
            tasks = [
                Task(
                    description=f"""Identify trends from these articles:
                    {article_text}
                    """,
                    agent=self.trend_spotter,
                    expected_output="Trend analysis report"
                )
            ]
        elif analysis_type == "fact_check":
            tasks = [
                Task(
                    description=f"""Fact-check these articles:
                    {article_text}
                    """,
                    agent=self.fact_checker,
                    expected_output="Fact-checking report"
                )
            ]
        else:
            return {"status": "error", "message": f"Unknown analysis type: {analysis_type}"}
        
        # Create and run crew
        crew = Crew(
            agents=[self.news_analyst, self.fact_checker, self.trend_spotter] 
                   if analysis_type == "comprehensive" 
                   else [tasks[0].agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            return {
                "status": "success",
                "analysis_type": analysis_type,
                "articles_analyzed": len(articles),
                "result": str(result)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"CrewAI analysis failed: {str(e)}"
            }


# --- A2A Bridge Functions (for ADK to call CrewAI) ---

# Global CrewAI instance (lazy initialization)
_crewai_instance: Optional[NewsAnalysisCrewAI] = None

def get_crewai_instance() -> NewsAnalysisCrewAI:
    """Lazy initialization of CrewAI instance"""
    global _crewai_instance
    if _crewai_instance is None:
        _crewai_instance = NewsAnalysisCrewAI()
    return _crewai_instance


def analyze_news_with_crewai(
    articles: List[Dict[str, Any]], 
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    A2A Bridge function: ADK calls this to get CrewAI analysis
    
    Args:
        articles: List of news articles to analyze
        analysis_type: Type of analysis to perform
    
    Returns:
        Analysis results from CrewAI
    """
    if not CREWAI_AVAILABLE:
        return {
            "status": "error",
            "message": "CrewAI is not installed. Install with: pip install crewai langchain-google-genai"
        }
    
    try:
        crew = get_crewai_instance()
        result = crew.analyze_news_batch(articles, analysis_type)
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to analyze with CrewAI: {str(e)}"
        }


def get_trend_analysis(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Quick trend analysis using CrewAI"""
    return analyze_news_with_crewai(articles, analysis_type="trends")


def fact_check_articles(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fact-check articles using CrewAI"""
    return analyze_news_with_crewai(articles, analysis_type="fact_check")


# --- Async wrapper for ADK compatibility ---
async def analyze_news_with_crewai_async(
    articles: List[Dict[str, Any]], 
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """Async wrapper for CrewAI analysis (ADK prefers async tools)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        analyze_news_with_crewai, 
        articles, 
        analysis_type
    )


# --- Example: Standalone CrewAI execution ---
async def test_crewai_standalone():
    """Test CrewAI agent independently"""
    print("Testing CrewAI News Analysis Agent...")
    
    # Sample articles
    sample_articles = [
        {
            "title": "Tech Giants Invest in AI",
            "date": "2025-01-15",
            "article": "Major technology companies announced significant investments in artificial intelligence research and development..."
        },
        {
            "title": "Climate Summit Concludes",
            "date": "2025-01-14",
            "article": "World leaders concluded the annual climate summit with new commitments to reduce carbon emissions..."
        }
    ]
    
    result = await analyze_news_with_crewai_async(sample_articles, "comprehensive")
    print("\nCrewAI Analysis Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if CREWAI_AVAILABLE:
        asyncio.run(test_crewai_standalone())
    else:
        print("Please install CrewAI: pip install crewai langchain-google-genai")