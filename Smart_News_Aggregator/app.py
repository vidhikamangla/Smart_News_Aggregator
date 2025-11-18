import streamlit as st
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List

# ADK imports
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from agent import root_agent

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Smart News Aggregator",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .stChatMessage {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .quick-action-btn {
        width: 100%;
        margin: 5px 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    
    # ADK Session variables
    if "adk_session_id" not in st.session_state:
        st.session_state.adk_session_id = str(uuid.uuid4())
    
    if "user_id" not in st.session_state:
        st.session_state.user_id = "streamlit_user_" + str(uuid.uuid4())[:8]
    
    if "app_name" not in st.session_state:
        st.session_state.app_name = "SmartNewsAggregator"
    
    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # ADK components
    if "adk_session_service" not in st.session_state:
        st.session_state.adk_session_service = InMemorySessionService()
    
    if "runner" not in st.session_state:
        st.session_state.runner = Runner(
            agent=root_agent,
            session_service=st.session_state.adk_session_service,
            app_name=st.session_state.app_name
        )
    
    if "adk_session_initialized" not in st.session_state:
        st.session_state.adk_session_initialized = False
    
    # User preferences
    if "user_preferences" not in st.session_state:
        st.session_state.user_preferences = {
            "language": "en",
            "style": "professional",
            "email": "vidhika.mangla.22cse@bmu.edu.in"
        }
    
    # UI state
    if "processing" not in st.session_state:
        st.session_state.processing = False
    
    if "quick_query" not in st.session_state:
        st.session_state.quick_query = None

# ============================================================================
# ADK SESSION MANAGEMENT
# ============================================================================

async def init_adk_session():
    """Initialize or retrieve ADK session"""
    try:
        if not st.session_state.adk_session_initialized:
            # Create new session with initial state
            state_context = {
                "user_preferences": st.session_state.user_preferences,
                "conversation_history": [],
                "run_counter": 0,
                "news_cache": {},
                "total_queries": 0
            }
            
            session = await st.session_state.adk_session_service.create_session(
                app_name=st.session_state.app_name,
                user_id=st.session_state.user_id,
                session_id=st.session_state.adk_session_id,
                state=state_context
            )
            
            st.session_state.adk_session_initialized = True
            return session
        else:
            # Get existing session
            return await st.session_state.adk_session_service.get_session(
                st.session_state.app_name,
                st.session_state.user_id,
                st.session_state.adk_session_id
            )
    except Exception as e:
        st.error(f"❌ Failed to initialize session: {e}")
        return None

async def update_user_preferences():
    """Update user preferences in ADK session"""
    try:
        session = await init_adk_session()
        if session:
            session.state["user_preferences"] = st.session_state.user_preferences
    except Exception as e:
        st.error(f"Failed to update preferences: {e}")

async def send_message_to_agent(user_message: str) -> str:
    """Send message to ADK agent and get response"""
    try:
        # Initialize session
        await init_adk_session()
        
        # Create ADK message
        user_content = types.Content(parts=[types.Part(text=user_message)])
        
        # Collect all responses
        responses = []
        final_response = None
        
        # Run agent
        for event in st.session_state.runner.run(
            user_id=st.session_state.user_id,
            session_id=st.session_state.adk_session_id,
            new_message=user_content
        ):
            if event.content and event.content.parts:
                msg = event.content.parts[0].text
                responses.append(msg)
                
                if event.is_final_response():
                    final_response = msg
                    break
        
        # Return final response or concatenated responses
        return final_response if final_response else "\n\n".join(responses) if responses else "No response from agent"
        
    except Exception as e:
        return f"❌ Error processing request: {str(e)}\n\nPlease check your configuration and try again."

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render sidebar with preferences and controls"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Language mapping
        language_map = {
            "English": "en",
            "Hindi": "hi",
            "French": "fr",
            "Spanish": "es",
            "Tamil": "ta"
        }
        
        style_map = {
            "Professional": "professional",
            "Sarcastic": "sarcastic",
            "Casual": "casual",
            "Formal": "formal"
        }
        
        # Current values
        current_lang_key = [k for k, v in language_map.items() 
                           if v == st.session_state.user_preferences.get("language", "en")][0]
        current_style_key = [k for k, v in style_map.items() 
                            if v == st.session_state.user_preferences.get("style", "professional")][0]
        
        # User Preferences Section
        with st.expander("👤 User Preferences", expanded=True):
            language = st.selectbox(
                "🌍 Language",
                options=list(language_map.keys()),
                index=list(language_map.keys()).index(current_lang_key),
                help="Target language for news translation"
            )
            
            style = st.selectbox(
                "✍️ Writing Style",
                options=list(style_map.keys()),
                index=list(style_map.keys()).index(current_style_key),
                help="Tone for news summaries"
            )
            
            email = st.text_input(
                "📧 Email Address",
                value=st.session_state.user_preferences.get("email", ""),
                help="Email for news delivery"
            )
            
            if st.button("💾 Save Preferences", use_container_width=True):
                st.session_state.user_preferences.update({
                    "language": language_map[language],
                    "style": style_map[style],
                    "email": email
                })
                asyncio.run(update_user_preferences())
                st.success("✅ Preferences saved!")
                st.rerun()
        
        st.divider()
        
        # Quick Actions
        st.markdown("## ⚡ Quick Actions")
        
        quick_actions = {
            "🏏 Sports News": "Get me the latest sports news",
            "🎬 Entertainment": "Show me entertainment news",
            "🇮🇳 National News": "Get national news headlines",
            "🌍 International": "Show international news",
            "🏙️ Mumbai News": "What's happening in Mumbai?",
            "💼 Business News": "Get business news updates"
        }
        
        for label, query in quick_actions.items():
            if st.button(label, use_container_width=True):
                st.session_state.quick_query = query
                st.rerun()
        
        st.divider()
        
        # Session Info
        with st.expander("📊 Session Info"):
            st.text(f"Session ID: {st.session_state.adk_session_id[:12]}...")
            st.text(f"User ID: {st.session_state.user_id}")
            st.text(f"Messages: {len(st.session_state.chat_history)}")
            st.text(f"Language: {st.session_state.user_preferences['language']}")
            st.text(f"Style: {st.session_state.user_preferences['style']}")
        
        # Clear Chat
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.adk_session_id = str(uuid.uuid4())
            st.session_state.adk_session_initialized = False
            st.success("Chat cleared!")
            st.rerun()
        
        st.divider()
        
        # Export Chat
        if st.session_state.chat_history:
            if st.button("💾 Export Chat", use_container_width=True):
                chat_json = json.dumps(st.session_state.chat_history, indent=2)
                st.download_button(
                    label="📥 Download JSON",
                    data=chat_json,
                    file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

def render_chat_message(role: str, content: str, timestamp: str = None):
    """Render a single chat message"""
    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
            if timestamp:
                st.caption(f"🕒 {timestamp}")
    else:
        with st.chat_message("assistant", avatar="📰"):
            st.markdown(content)
            if timestamp:
                st.caption(f"🕒 {timestamp}")

def render_chat_history():
    """Render all chat messages from history"""
    for message in st.session_state.chat_history:
        timestamp = message.get("timestamp", "")
        if timestamp:
            # Format timestamp nicely
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%I:%M %p")
            except:
                timestamp = ""
        
        render_chat_message(
            message["role"], 
            message["content"],
            timestamp
        )

def render_example_queries():
    """Render example query buttons at the bottom"""
    st.markdown("### 💡 Try these examples:")
    
    col1, col2, col3 = st.columns(3)
    
    examples = [
        ("🏏 Sports", "Get me sports news today"),
        ("🌍 Mumbai", "What's happening in Mumbai?"),
        ("🎬 Movies", "Show me entertainment news"),
    ]
    
    for col, (label, query) in zip([col1, col2, col3], examples):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.quick_query = query
                st.rerun()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main Streamlit application"""
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
    st.markdown('<div class="main-header">📰 Smart News Aggregator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI-powered news fetching, summarization, translation & delivery</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Display chat history
    render_chat_history()
    
    # Handle quick query from sidebar or examples
    user_input = None
    if st.session_state.quick_query:
        user_input = st.session_state.quick_query
        st.session_state.quick_query = None
    
    # Chat input
    if prompt := st.chat_input("💬 Ask me for news (e.g., 'Get sports news' or 'Mumbai headlines')"):
        user_input = prompt
    
    # Process user input
    if user_input and not st.session_state.processing:
        st.session_state.processing = True
        
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # Display user message
        render_chat_message("user", user_input, datetime.now().strftime("%I:%M %p"))
        
        # Show processing status
        with st.chat_message("assistant", avatar="📰"):
            with st.spinner("🔄 Processing your request..."):
                # Progress indicators
                status_placeholder = st.empty()
                progress_bar = st.progress(0)
                
                status_placeholder.text("📥 Fetching news articles...")
                progress_bar.progress(25)
                
                # Get response from agent
                try:
                    response = asyncio.run(send_message_to_agent(user_input))
                    
                    status_placeholder.text("📝 Summarizing content...")
                    progress_bar.progress(50)
                    
                    status_placeholder.text("🌍 Translating to your language...")
                    progress_bar.progress(75)
                    
                    status_placeholder.text("📧 Preparing email...")
                    progress_bar.progress(90)
                    
                    # Add assistant response to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    status_placeholder.text("✅ Complete!")
                    progress_bar.progress(100)
                    
                    # Clear progress indicators
                    status_placeholder.empty()
                    progress_bar.empty()
                    
                    # Display response
                    st.markdown(response)
                    st.caption(f"🕒 {datetime.now().strftime('%I:%M %p')}")
                    
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                        "timestamp": datetime.now().isoformat()
                    })
        
        st.session_state.processing = False
        st.rerun()
    
    # Show example queries if no chat history
    if not st.session_state.chat_history:
        st.divider()
        render_example_queries()
    
    # Footer
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.caption("💬 Natural language queries")
    with col2:
        st.caption("🌍 Multi-language support")
    with col3:
        st.caption("📧 Email delivery")
    with col4:
        st.caption("⚡ Quick actions")

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()