import streamlit as st
import os
import re
import logging
import time
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Load environment variables
load_dotenv()

# Configure logging once at the application level
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache the Mistral client to prevent re-initialization on every rerun
@st.cache_resource
def get_mistral_client():
    """Initialize and cache the Mistral client."""
    return MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

# Define avatars and their personalities
AVATARS = {
    "Therapist": {
        "icon": "🧘",
        "description": "A compassionate therapist who provides professional guidance and support",
        "system_prompt": "You are a compassionate and professional therapist. Your role is to:\n1. Provide empathetic support and guidance\n2. Help users develop coping strategies\n3. Encourage professional help when needed\n4. Maintain appropriate boundaries\n5. Focus on evidence-based therapeutic approaches",
        "suggestions": [
            "How can I deal with my anxiety?",
            "I've been feeling low lately.",
            "Can you help me with a coping strategy?"
        ]
    },
    "Life Coach": {
        "icon": "⚡",
        "description": "An energetic life coach focused on personal growth and achievement",
        "system_prompt": "You are an enthusiastic life coach. Your role is to:\n1. Help users set and achieve personal goals\n2. Provide motivation and accountability\n3. Share practical strategies for self-improvement\n4. Focus on building confidence and resilience\n5. Encourage positive thinking and action",
        "suggestions": [
            "How can I stay motivated today?",
            "I want to set some personal goals.",
            "How can I build more resilience?"
        ]
    },
    "Friend": {
        "icon": "🤗",
        "description": "A supportive friend who listens and offers understanding",
        "system_prompt": "You are a caring and understanding friend. Your role is to:\n1. Provide emotional support and validation\n2. Listen actively and show empathy\n3. Share personal experiences when relevant\n4. Offer practical advice from a friend's perspective\n5. Maintain a warm and casual conversation style",
        "suggestions": [
            "I just need someone to talk to.",
            "I had a rough day at work.",
            "Can you tell me something positive?"
        ]
    }
}

# Pre-calculate avatar options, system messages, and icons for performance
AVATAR_OPTIONS = list(AVATARS.keys())
SYSTEM_MESSAGES = {
    name: ChatMessage(role="system", content=data["system_prompt"])
    for name, data in AVATARS.items()
}
AVATAR_ICONS = {
    name: data["icon"]
    for name, data in AVATARS.items()
}

# Crisis detection keywords and pre-compiled regex for performance
CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end it all", "ending it all", "no reason to live",
    "want to die", "better off dead", "hurt myself", "take my life", "self-harm",
    "don't want to be here anymore", "slit my wrists", "overdose",
    "hopeless", "can't go on", "end my life"
]
# Pre-compiled regex for faster crisis detection
CRISIS_PATTERN = re.compile(r'|'.join(map(re.escape, CRISIS_KEYWORDS)), re.IGNORECASE)

def detect_crisis(message):
    """Detect if the message indicates a crisis situation using regex."""
    return bool(CRISIS_PATTERN.search(message))

def get_crisis_response():
    """Return emergency resources and crisis response."""
    return """
    I'm concerned about your safety. Please know that you're not alone, and help is available:
    
    1. **National Suicide Prevention Lifeline**: [988](tel:988)
    2. **Crisis Text Line**: [Text HOME to 741741](sms:741741)
    3. **Emergency Services**: [911](tel:911)
    
    These services are available 24/7 and are free and confidential.
    Would you like me to help you connect with any of these resources?
    """

def get_bot_response(messages):
    """Get streaming response from Mistral AI model."""
    try:
        client = get_mistral_client()
        if not client._api_key:
            logger.error("Mistral API key is missing.")
            yield "I'm sorry, but there's a configuration issue. Please contact support."
            return

        total_chars = 0
        MAX_RESPONSE_CHARS = 4000
        for chunk in client.chat_stream(
            model="mistral-tiny",
            messages=messages
        ):
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                total_chars += len(content)
                if total_chars > MAX_RESPONSE_CHARS:
                    yield "... [Response truncated for length]"
                    break
                yield content
    except Exception as e:
        # Log the full error server-side for debugging
        logger.error(f"Error in get_bot_response: {str(e)}", exc_info=True)
        # Return a generic error message to the user to prevent information leakage
        yield "I apologize, but I'm having trouble connecting right now. Please try again later."

def handle_user_input(prompt):
    """Centralized handler for user input to ensure safety and security."""
    # Implement a simple rate limiter to prevent DoS/API abuse
    current_time = time.time()
    time_since_last = current_time - st.session_state.get("last_message_time", 0)
    if time_since_last < 2.0:
        st.warning(f"Please wait {2.0 - time_since_last:.1f} more seconds before sending another message.")
        return False

    st.session_state.last_message_time = current_time

    # Add user message to chat as ChatMessage object for performance
    st.session_state.messages.append(ChatMessage(role="user", content=prompt))

    # Cap message history to prevent memory-based DoS (e.g., last 50 messages)
    if len(st.session_state.messages) > 50:
        st.session_state.messages = st.session_state.messages[-50:]

    # Check for crisis situation
    if detect_crisis(prompt):
        crisis_response = get_crisis_response()
        st.session_state.messages.append(ChatMessage(role="assistant", content=crisis_response))

    return True

def main():
    st.title("Mental Health Ease Bot")
    st.write("Your AI companion for mental well-being and personal growth")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_avatar" not in st.session_state:
        st.session_state.selected_avatar = "Therapist"
    if "last_message_time" not in st.session_state:
        st.session_state.last_message_time = 0

    # Avatar selection using pre-calculated options
    st.sidebar.title("Choose Your Companion")
    selected_avatar = st.sidebar.selectbox(
        "Select an avatar",
        AVATAR_OPTIONS,
        index=AVATAR_OPTIONS.index(st.session_state.selected_avatar)
    )
    
    if selected_avatar != st.session_state.selected_avatar:
        st.session_state.selected_avatar = selected_avatar
        st.session_state.messages = []

    # Display avatar description
    st.sidebar.write(AVATARS[selected_avatar]["description"])

    # Clear chat history button for privacy and security
    st.sidebar.markdown("---")
    if st.sidebar.button("Clear Chat History", help="Delete all messages and start a new conversation"):
        st.session_state.messages = []
        st.rerun()

    # Display chat messages
    if not st.session_state.messages:
        # Welcome Screen for Empty State
        st.info(f"Welcome! I'm your **{selected_avatar}**. How can I support you today?")
        st.write("Click on a suggestion below or type your own message to start:")

        # Display suggestion buttons in columns
        suggestions = AVATARS[selected_avatar]["suggestions"]
        cols = st.columns(len(suggestions))
        for idx, suggestion in enumerate(suggestions):
            if cols[idx].button(suggestion, use_container_width=True):
                if handle_user_input(suggestion):
                    st.rerun()
    else:
        for message in st.session_state.messages:
            with st.chat_message(message.role, avatar=AVATAR_ICONS[st.session_state.selected_avatar] if message.role == "assistant" else None):
                st.write(message.content)

    # Chat input with length limit for performance and security
    if prompt := st.chat_input("How are you feeling today?", max_chars=2000):
        if handle_user_input(prompt):
            st.rerun()

    # Automatically generate bot response if the last message is from user
    if st.session_state.messages and st.session_state.messages[-1].role == "user":
        # Prepare messages for the model, truncating history for performance
        # Limit to the 10 most recent messages to reduce token count and improve latency
        # Expected impact: Eliminates redundant ChatMessage object creation and list comprehensions.
        messages = [SYSTEM_MESSAGES[selected_avatar]] + st.session_state.messages[-10:]

        # Get and display bot response with streaming
        with st.chat_message("assistant", avatar=AVATAR_ICONS[selected_avatar]):
            response_placeholder = st.empty()
            full_response = ""
            # Use token buffering to reduce UI update frequency and websocket traffic
            chunk_count = 0
            for response_chunk in get_bot_response(messages):
                full_response += response_chunk
                chunk_count += 1
                if chunk_count % 5 == 0:
                    response_placeholder.markdown(full_response + "▌")
            response_placeholder.markdown(full_response)
            st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))

    # Display emergency resources
    st.sidebar.markdown("---")
    st.sidebar.error("""
        🚨 **Emergency Resources**

        If you're in crisis, please contact:
        - National Suicide Prevention Lifeline: [988](tel:988)
        - Crisis Text Line: [Text HOME to 741741](sms:741741)
        - Emergency Services: [911](tel:911)
    """)

if __name__ == "__main__":
    main()
