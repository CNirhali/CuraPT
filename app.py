import streamlit as st
import os
import re
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Load environment variables (ensure sensitive keys are not hardcoded)
load_dotenv()

# Pre-compiled regex for API key sanitization (Defense-in-depth against secret leakage)
SANITIZATION_PATTERN = re.compile(r'\bsk-[a-zA-Z0-9]+\b')

def sanitize_error(message):
    """
    Redact sensitive information like API keys from strings.
    This provides defense-in-depth by preventing secrets from being displayed in the UI,
    stored in session history, or sent to external providers.
    """
    if not isinstance(message, str):
        message = str(message)
    # Optimization: fast-path check to avoid regex if no potential key is present
    if "sk-" not in message:
        return message
    # Mask Mistral API keys with word boundaries to avoid false positives: \bsk-[a-zA-Z0-9]+\b
    return SANITIZATION_PATTERN.sub('[REDACTED_API_KEY]', message)

class SanitizedFormatter(logging.Formatter):
    """Custom formatter to redact sensitive information from all log output, including tracebacks."""
    def format(self, record):
        return sanitize_error(super().format(record))

# Configure logging once at the application level
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Apply custom sanitized formatter to all root handlers to ensure defense-in-depth
for handler in logging.root.handlers:
    handler.setFormatter(SanitizedFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

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
AVATAR_DISPLAY_NAMES = {
    name: f"{data['icon']} {name}"
    for name, data in AVATARS.items()
}
AVATAR_DESCRIPTIONS = {
    name: data["description"]
    for name, data in AVATARS.items()
}
AVATAR_SUGGESTIONS = {
    name: data["suggestions"]
    for name, data in AVATARS.items()
}

# Crisis detection keywords and pre-compiled regex for performance
CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end it all", "ending it all", "no reason to live",
    "want to die", "better off dead", "hurt myself", "take my life", "self-harm",
    "don't want to be here anymore", "slit my wrists", "overdose",
    "hopeless", "can't go on", "end my life", "suicidal", "kill me",
    "jumping off", "jump off", "cut myself", "hang myself", "poison myself",
    "kill yourself", "ending your life", "hurt yourself"
]
# Pre-compiled regex for faster crisis detection (using lowercase for performance)
# Use word boundaries (\b) to prevent false positives (e.g., "send it all" matching "end it all")
CRISIS_PATTERN = re.compile(r'\b(?:' + r'|'.join(map(re.escape, [k.lower() for k in CRISIS_KEYWORDS])) + r')\b')
# Shortest crisis keywords like "suicide" or "kill me" are 7 characters long
MIN_CRISIS_KEYWORD_LEN = 7

def detect_crisis(message):
    """Detect if the message indicates a crisis situation using regex."""
    # Optimization: return False immediately for very short, safe inputs to avoid string processing
    if len(message) < MIN_CRISIS_KEYWORD_LEN:
        return False
    # Optimization: manual lowercase search is faster than re.IGNORECASE for many alternations
    return bool(CRISIS_PATTERN.search(message.lower()))

def get_crisis_response():
    """Return emergency resources and crisis response."""
    return """
    I'm concerned about your safety. Please know that you're not alone, and help is available:
    
    - 📞 **National Suicide Prevention Lifeline**: [Call or Text 988](tel:988)
    - 💬 **Crisis Text Line**: [Text HOME to 741741](sms:741741)
    - 🚑 **Emergency Services**: [Call 911](tel:911)
    
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
            messages=messages,
            max_tokens=1000
        ):
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                total_chars += len(content)
                if total_chars > MAX_RESPONSE_CHARS:
                    yield "... [Response truncated for length]"
                    break
                yield content
    except Exception as e:
        # Log the full error server-side for debugging (SanitizedFormatter masks secrets in logs)
        logger.error(f"Error in get_bot_response: {str(e)}", exc_info=True)
        # Return a generic error message to the user to prevent information leakage (OWASP A03:2021)
        yield "I'm here for you, but I'm having a little trouble connecting right now. Please try again in a moment."

def handle_user_input(prompt):
    """Update state with user input and check for crisis. Returns (success, is_crisis, crisis_text, sanitized_prompt)."""
    # Server-side length validation as defense-in-depth against resource exhaustion
    if len(prompt) > 2000:
        st.toast("Your message is a bit too long. Please try to shorten it.", icon="⚠️")
        return False, False, None, prompt

    current_time = time.time()
    time_since_last = current_time - st.session_state.get("last_message_time", 0)
    if time_since_last < 2.0:
        st.toast(f"Take a breath! Please wait {2.0 - time_since_last:.1f}s", icon="🧘")
        return False, False, None, prompt

    st.session_state.last_message_time = current_time

    # Sanitize user input immediately (Defense-in-depth: prevent secrets from reaching the LLM or session state)
    sanitized_prompt = sanitize_error(prompt)

    # Add user message to chat as ChatMessage object for performance
    st.session_state.messages.append(ChatMessage(role="user", content=sanitized_prompt))

    # History capping for performance and security
    if len(st.session_state.messages) > 50:
        st.session_state.messages = st.session_state.messages[-50:]

    is_crisis = detect_crisis(sanitized_prompt)
    crisis_text = None
    if is_crisis:
        logger.warning(f"Safety: Crisis detected in user input.")
        crisis_text = get_crisis_response()
        st.session_state.messages.append(ChatMessage(role="assistant", content=crisis_text))

    return True, is_crisis, crisis_text, sanitized_prompt

def get_time_based_greeting():
    """Return a time-appropriate greeting for the welcome message."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif 12 <= hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

def main():
    st.markdown("# Mental Health Ease Bot\nYour AI companion for mental well-being and personal growth")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_avatar" not in st.session_state:
        st.session_state.selected_avatar = "Therapist"
    if "last_message_time" not in st.session_state:
        st.session_state.last_message_time = 0

    # Avatar selection
    st.sidebar.title("Choose Your Companion")
    selected_avatar = st.sidebar.selectbox(
        "Select an avatar",
        AVATAR_OPTIONS,
        index=AVATAR_OPTIONS.index(st.session_state.selected_avatar),
        format_func=AVATAR_DISPLAY_NAMES.get,
        help="Switching your companion will reset the current conversation."
    )
    
    if selected_avatar != st.session_state.selected_avatar:
        st.session_state.selected_avatar = selected_avatar
        st.session_state.messages = []
        st.toast(f"Switched to {selected_avatar}", icon=AVATAR_ICONS[selected_avatar])

    st.sidebar.write(AVATAR_DESCRIPTIONS[selected_avatar])

    st.sidebar.markdown("---")

    # Manage Conversation Popover
    with st.sidebar.popover("⚙️ Manage Conversation", use_container_width=True):
        st.write("Settings for your current chat session.")

        # Export History
        if st.session_state.messages:
            # Optimization: Use list join for O(N) performance instead of iterative string concatenation
            export_parts = [
                f"Mental Health Ease Bot - {st.session_state.selected_avatar} Session",
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "-" * 40 + "\n"
            ]
            export_parts.extend(
                f"{'Assistant' if msg.role == 'assistant' else 'You'}: {msg.content}\n"
                for msg in st.session_state.messages
            )
            chat_text = "\n".join(export_parts) + "\n"

            st.download_button(
                label="📥 Export Conversation",
                data=chat_text,
                file_name=f"mental_health_bot_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="Download a copy of your current conversation history.",
                use_container_width=True
            )
        else:
            st.info("No messages to export yet.")

        st.markdown("---")

        # Clear Chat History with confirmation
        st.write("⚠️ **Destructive Actions**")
        confirm_clear = st.checkbox("I want to clear this conversation", help="Check this to enable the clear button")
        if st.button("🗑️ Clear Chat History",
                     help="Delete all messages and start a new conversation",
                     use_container_width=True,
                     disabled=not confirm_clear,
                     type="secondary"):
            st.session_state.messages = []
            st.toast("Conversation cleared 🌱")
            st.rerun()

    with st.sidebar.expander("🛡️ Privacy & Safety"):
        st.write("""
            - 🔒 **Conversations are confidential** and not stored on our servers permanently.
            - 🔑 Your **Mistral API key** is used only for processing this session.
        """)

    st.sidebar.info("⚕️ This bot is **not a replacement** for professional care. If you're in distress, please use the emergency resources below.")

    # Display chat messages from history
    if not st.session_state.messages:
        # Optimization: use pre-calculated avatar icon and combine write calls to reduce UI traffic
        with st.chat_message("assistant", avatar=AVATAR_ICONS[selected_avatar]):
            greeting = get_time_based_greeting()
            st.write(f"{greeting}! I'm your **{selected_avatar}**. How can I support you today?\n\n"
                     "Click on a suggestion below or type your own message to start:")

        suggestions = AVATAR_SUGGESTIONS[selected_avatar]
        cols = st.columns(len(suggestions))
        processed_suggestion = None
        for idx, suggestion in enumerate(suggestions):
            if cols[idx].button(suggestion, use_container_width=True, help="Click to ask about this"):
                processed_suggestion = suggestion

        if processed_suggestion:
            prompt = processed_suggestion
        else:
            prompt = None
    else:
        # Pre-calculate assistant icon once per rerun to avoid redundant lookups in the loop
        assistant_icon = AVATAR_ICONS[st.session_state.selected_avatar]
        for message in st.session_state.messages:
            avatar = assistant_icon if message.role == "assistant" else "👤"
            with st.chat_message(message.role, avatar=avatar):
                st.write(message.content)
        prompt = None

    # Chat input is always visible unless a suggestion was just clicked
    if not prompt:
        prompt = st.chat_input("How are you feeling today?", max_chars=2000)

    # Message processing
    if prompt:
        success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt)
        if success:
            # Immediate feedback: render sanitized user message
            with st.chat_message("user", avatar="👤"):
                st.write(sanitized_prompt)

            if is_crisis:
                with st.chat_message("assistant", avatar=AVATAR_ICONS[selected_avatar]):
                    st.write(crisis_text)
            else:
                # Generate and stream bot response immediately
                messages = [SYSTEM_MESSAGES[selected_avatar]] + st.session_state.messages[-10:]

                with st.chat_message("assistant", avatar=AVATAR_ICONS[selected_avatar]):
                    response_placeholder = st.empty()
                    response_placeholder.markdown("*(thinking...)*")
                    full_response = ""
                    # Use token buffering to reduce UI update frequency and websocket traffic
                    chunk_count = 0
                    for response_chunk in get_bot_response(messages):
                        full_response += response_chunk
                        chunk_count += 1
                        if chunk_count % 5 == 0:
                            # Sanitize incremental response for safety
                            response_placeholder.markdown(sanitize_error(full_response) + "▌")

                    # Final safety and sanitization check
                    final_response = sanitize_error(full_response)
                    if detect_crisis(final_response):
                        logger.warning("Safety: Crisis detected in AI response. Redacting.")
                        final_response = "I'm sorry, I cannot fulfill this request as it may contain unsafe content. If you're in distress, please use the emergency resources in the sidebar."

                    response_placeholder.markdown(final_response)
                    st.session_state.messages.append(ChatMessage(role="assistant", content=final_response))

            # Rerun to clear input and refresh UI state
            st.rerun()

    # Sidebar resources
    st.sidebar.markdown("---")
    st.sidebar.error("""
        🚨 **Emergency Resources**

        If you're in crisis, please contact:
        - 📞 **National Suicide Prevention Lifeline**: [Call or Text 988](tel:988)
        - 💬 **Crisis Text Line**: [Text HOME to 741741](sms:741741)
        - 🚑 **Emergency Services**: [Call 911](tel:911)
    """)

if __name__ == "__main__":
    main()
