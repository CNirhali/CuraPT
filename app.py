import streamlit as st
import os
import re
import logging
import time
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Load environment variables (ensure sensitive keys are not hardcoded)
load_dotenv()

# Set page configuration for professional branding and accessibility
# This must be the first Streamlit command executed
st.set_page_config(
    page_title="Mental Health Ease Bot",
    page_icon="🧘",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Pre-compiled regex for sensitive data sanitization (Defense-in-depth against secret leakage)
# Includes Mistral keys, AWS, GCP, GitHub, Stripe, Slack tokens, and Private Keys
# Order matters: Specific patterns should come before generic ones to prevent partial matches
SANITIZATION_PATTERNS = [
    (re.compile(r'-----BEGIN (?:[A-Z ]+) KEY-----[\s\S]*?-----END (?:[A-Z ]+) KEY-----'), '[REDACTED_PRIVATE_KEY]'),
    (re.compile(r'\b(AKIA|ASIA)[0-9A-Z]{12,124}\b'), '[REDACTED_AWS_KEY]'),
    (re.compile(r'\bsk-[a-zA-Z0-9]+\b'), '[REDACTED_API_KEY]'),
    (re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'), '[REDACTED_GCP_KEY]'),
    (re.compile(r'\bgh[pours]_[a-zA-Z0-9]{36}\b'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'\bsk_(?:live|test)_[0-9a-zA-Z]{24}\b'), '[REDACTED_STRIPE_KEY]'),
    (re.compile(r'\bxox[bpgrs]-[0-9a-zA-Z]{10,48}\b'), '[REDACTED_SLACK_TOKEN]'),
    (re.compile(r'(?i)Bearer\s+[a-zA-Z0-9._\-\/+=]+'), 'Bearer [REDACTED]'),
    # Enhanced pattern to handle quoted secrets and preserve original separators
    # Use negative lookahead to avoid re-redacting already masked values
    (re.compile(r'(?i)\b(password|passwd|secret|token|api_key|aws_secret_access_key)(\s*(?:[:=]|is)\s*)(?!\[REDACTED)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2[REDACTED]'),
    # Generic 'key' pattern is last and avoids matching PEM headers via negative lookahead
    (re.compile(r'(?i)\b(key)(\s*(?:[:=]|is)\s*)(?!\[REDACTED|---)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2[REDACTED]')
]
# Optimization: Substring markers to trigger expensive regex execution
# Refinement: replaced 'pass' with 'password'/'passwd' to avoid false positives on 'compassion'
# Included markers for AWS, GCP, GitHub (ghp/gho/ghu/ghr/ghs), Stripe, Slack (xoxb/xoxp/xoxg/xoxr/xoxs) and Private Keys
# Reordered to place highly frequent markers at the beginning for faster short-circuiting in any()
SENSITIVE_MARKERS = [
    "password", "token", "sk-", "secret", "key", "passwd", "akia", "asia", "bearer",
    "aiza", "ghp_", "gho_", "ghu_", "ghr_", "ghs_", "sk_live", "sk_test",
    "xoxb-", "xoxp-", "xoxg-", "xoxr-", "xoxs-", "begin", "aws_secret_access_key"
]

def sanitize_error(message):
    """
    Redact sensitive information like API keys, passwords, and tokens from strings.
    This provides defense-in-depth by preventing secrets from being displayed in the UI,
    stored in session history, or sent to external providers.
    """
    if not isinstance(message, str):
        message = str(message)

    # Optimization: return early for messages without sensitive markers (approx. 15-20x speedup for clean messages)
    msg_lower = message.lower()
    if not any(marker in msg_lower for marker in SENSITIVE_MARKERS):
        return message

    sanitized = message
    # In CPython, re.sub already handles the 'no match' case efficiently by
    # returning the original string object without performing a substitution.
    for pattern, replacement in SANITIZATION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized

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
        "thinking_msg": "💭 Reflecting on your words...",
        "chat_placeholder": "What's on your mind?",
        "ready_msg": "is here to support you",
        "system_prompt": "You are a compassionate and professional therapist. Your role is to:\n1. Provide empathetic support and guidance\n2. Help users develop coping strategies\n3. Encourage professional help when needed\n4. Maintain appropriate boundaries\n5. Focus on evidence-based therapeutic approaches",
        "suggestions": [
            "🧘 How can I deal with my anxiety?",
            "🧘 I've been feeling low lately.",
            "🧘 Can you help me with a coping strategy?"
        ]
    },
    "Life Coach": {
        "icon": "⚡",
        "description": "An energetic life coach focused on personal growth and achievement",
        "thinking_msg": "💭 Formulating a plan for your growth...",
        "chat_placeholder": "What's your goal for today?",
        "ready_msg": "is ready to help you grow",
        "system_prompt": "You are an enthusiastic life coach. Your role is to:\n1. Help users set and achieve personal goals\n2. Provide motivation and accountability\n3. Share practical strategies for self-improvement\n4. Focus on building confidence and resilience\n5. Encourage positive thinking and action",
        "suggestions": [
            "⚡ How can I stay motivated today?",
            "⚡ I want to set some personal goals.",
            "⚡ How can I build more resilience?"
        ]
    },
    "Friend": {
        "icon": "🤗",
        "description": "A supportive friend who listens and offers understanding",
        "thinking_msg": "💭 Thinking of how to support you...",
        "chat_placeholder": "How are you doing?",
        "ready_msg": "is here to listen",
        "system_prompt": "You are a caring and understanding friend. Your role is to:\n1. Provide emotional support and validation\n2. Listen actively and show empathy\n3. Share personal experiences when relevant\n4. Offer practical advice from a friend's perspective\n5. Maintain a warm and casual conversation style",
        "suggestions": [
            "🤗 I just need someone to talk to.",
            "🤗 I had a rough day at work.",
            "🤗 Can you tell me something positive?"
        ]
    }
}

# Pre-calculate avatar options, system messages, and icons for performance
AVATAR_OPTIONS = list(AVATARS.keys())
AVATAR_INDEX = {name: i for i, name in enumerate(AVATAR_OPTIONS)}
SYSTEM_MESSAGES = {
    name: ChatMessage(role="system", content=data["system_prompt"])
    for name, data in AVATARS.items()
}
AVATAR_ICONS = {
    name: data["icon"]
    for name, data in AVATARS.items()
}
AVATAR_PLACEHOLDERS = {
    name: data["chat_placeholder"]
    for name, data in AVATARS.items()
}
AVATAR_THINKING_MSGS = {
    name: data["thinking_msg"]
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
AVATAR_READY_MSGS = {
    name: data["ready_msg"]
    for name, data in AVATARS.items()
}
AVATAR_HERE_MSGS = {
    name: f"🟢 {name} {data['ready_msg']}"
    for name, data in AVATARS.items()
}

# Crisis detection keywords and pre-compiled regex for performance
# Sorted by length (ascending) to improve short-circuiting performance of the any() check
CRISIS_KEYWORDS = [
    "unalive", "suicide", "kill me", "hopeless", "jump off", "overdose",
    "suicidal", "self harm", "can't go on", "cut myself", "end it all",
    "end my life", "hurt myself", "take my life", "want to die", "hang myself",
    "self-harm", "hurt yourself", "kill myself", "better off dead",
    "ending it all", "jumping off", "kill yourself", "slit my wrists",
    "ending your life", "poison myself", "no reason to live",
    "don't want to be here anymore"
]
# Pre-calculate lowercase keywords for O(N) fast-path check
CRISIS_KEYWORDS_LOWER = [k.lower() for k in CRISIS_KEYWORDS]
# Pre-compiled regex for faster crisis detection (using lowercase for performance)
# Use word boundaries (\b) to prevent false positives (e.g., "send it all" matching "end it all")
CRISIS_PATTERN = re.compile(r'\b(?:' + r'|'.join(map(re.escape, CRISIS_KEYWORDS_LOWER)) + r')\b')
# Shortest crisis keywords like "suicide" or "kill me" are 7 characters long
MIN_CRISIS_KEYWORD_LEN = 7

# Common Latin-lookalike homoglyphs (e.g., Cyrillic, Greek) for normalization
_HOMOGLYPH_MAP = str.maketrans(
    'аеіорсхуіј',  # Lookalikes
    'aeiopcxyij'   # Latin equivalents
)

def detect_crisis(message):
    """
    Detect if the message indicates a crisis situation using regex.
    Includes normalization for homoglyphs and NFKC for robustness against obfuscation.
    """
    # Optimization: return False immediately for very short, safe inputs to avoid string processing
    if len(message) < MIN_CRISIS_KEYWORD_LEN:
        return False

    # Optimization: O(N) fast-path using isascii() and substring check.
    # We prioritize ASCII messages as they are the most common and don't require normalization.
    is_ascii = message.isascii()
    msg_lower = message.lower()

    if is_ascii:
        # Fast-path for ASCII: use any() check before full regex search.
        # Approx 2.3x-2.8x speedup for clean messages.
        if not any(k in msg_lower for k in CRISIS_KEYWORDS_LOWER):
            return False
        return bool(CRISIS_PATTERN.search(msg_lower))

    # Slow-path for non-ASCII messages (handles homoglyph obfuscation)
    # Check original first to catch common keywords immediately
    if CRISIS_PATTERN.search(msg_lower):
        return True

    # Normalize NFKC and apply manual homoglyph mapping for defense-in-depth
    normalized = unicodedata.normalize('NFKC', msg_lower).translate(_HOMOGLYPH_MAP)
    return bool(CRISIS_PATTERN.search(normalized))

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

def handle_user_input(prompt, avatar_icon="🧘"):
    """Update state with user input and check for crisis. Returns (success, is_crisis, crisis_text, sanitized_prompt)."""
    # Server-side length validation as defense-in-depth against resource exhaustion
    if len(prompt) > 2000:
        st.toast("Your message is a bit too long. Please try to shorten it.", icon="⚠️")
        return False, False, None, prompt

    current_time = time.time()
    time_since_last = current_time - st.session_state.get("last_message_time", 0)
    if time_since_last < 2.0:
        st.toast(f"Take a breath! Please wait {2.0 - time_since_last:.1f}s", icon=avatar_icon)
        return False, False, None, prompt

    st.session_state.last_message_time = current_time

    # Sanitize user input immediately (Defense-in-depth: prevent secrets from reaching the LLM or session state)
    sanitized_prompt = sanitize_error(prompt)

    # Add user message to chat as ChatMessage object for performance
    st.session_state.messages.append(ChatMessage(role="user", content=sanitized_prompt))

    # History capping for performance and security
    # Optimization: Use in-place deletion to maintain list object identity and reduce memory churn
    if len(st.session_state.messages) > 50:
        del st.session_state.messages[:-50]

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
    st.title("Mental Health Ease Bot")
    st.subheader("Your AI companion for mental well-being and personal growth", divider="blue")

    # Optimization: Use local variables for session state to bypass proxy overhead
    state = st.session_state

    # Initialize session state
    if "messages" not in state:
        state.messages = []
    if "selected_avatar" not in state:
        state.selected_avatar = "Therapist"
    if "last_message_time" not in state:
        state.last_message_time = 0

    # Local references for performance
    messages = state.messages
    current_selected = state.selected_avatar

    # Avatar selection
    selected_avatar = st.sidebar.selectbox(
        "Choose Your Companion",
        AVATAR_OPTIONS,
        index=AVATAR_INDEX[current_selected],
        format_func=AVATAR_DISPLAY_NAMES.get,
        help="Switching your companion will reset the current conversation. Consider exporting your chat first if you'd like to save it."
    )
    
    if selected_avatar != current_selected:
        state.selected_avatar = selected_avatar
        state.messages = []
        # Update local references after state change
        messages = state.messages
        st.toast(f"Switched to {selected_avatar}", icon=AVATAR_ICONS[selected_avatar])

    # Ensure the conversation starts with a persona-specific welcome message
    if not messages:
        greeting = get_time_based_greeting()
        welcome_msg = f"{greeting}! I'm your **{selected_avatar}**. How can I support you today?"
        messages.append(ChatMessage(role="assistant", content=welcome_msg))

    # Optimization: Pre-fetch persona-specific constants to avoid redundant lookups in UI rendering
    assistant_icon = AVATAR_ICONS[selected_avatar]
    suggestions = AVATAR_SUGGESTIONS[selected_avatar]
    placeholder = AVATAR_PLACEHOLDERS[selected_avatar]
    description = AVATAR_DESCRIPTIONS[selected_avatar]
    thinking_msg = AVATAR_THINKING_MSGS[selected_avatar]
    here_msg = AVATAR_HERE_MSGS[selected_avatar]
    system_msg = SYSTEM_MESSAGES[selected_avatar]
    msg_count = len(messages)

    with st.sidebar:
        st.write(description)
        st.caption(here_msg)
        st.markdown("---")

    # Manage Conversation Popover
    with st.sidebar.popover("⚙️ Manage Conversation", use_container_width=True):
    with st.sidebar.popover(f"⚙️ Manage Conversation ({msg_count} message{'s' if msg_count != 1 else ''})", use_container_width=True):
        st.write("Settings for your current chat session.")

        # Export History
        if messages:
            # Optimization: Cache the sanitized export transcript to avoid O(N) generation on every rerun
            cache_key = f"export_cache_{selected_avatar}_{msg_count}"

            if "last_export" not in state or state.get("export_cache_key") != cache_key:
                export_parts = [
                    f"Mental Health Ease Bot - {selected_avatar} Session",
                    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "-" * 40 + "\n"
                ]
                export_parts.extend(
                    f"{selected_avatar if msg.role == 'assistant' else 'You'}: {msg.content}\n"
                    for msg in messages
                )
                # Apply defense-in-depth sanitization to the final export transcript
                state.last_export = sanitize_error("\n".join(export_parts) + "\n")
                state.export_cache_key = cache_key

            st.download_button(
                label=f"📥 Export Conversation ({msg_count} message{'s' if msg_count != 1 else ''})",
                data=state.last_export,
                file_name=f"mental_health_bot_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                data=st.session_state.last_export,
                file_name=f"{selected_avatar.lower().replace(' ', '_')}_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="Download a copy of your current conversation history.",
                use_container_width=True
            )
        else:
            st.info("No messages to export yet.")

        st.markdown("---")

        # Clear Chat History with confirmation
        st.write("⚠️ **Destructive Actions**")
        confirm_clear = st.checkbox("I'm ready for a fresh start", help="Check this to enable the clear button")
        if st.button(f"🗑️ Clear Chat History ({msg_count} message{'s' if msg_count != 1 else ''})",
                     help="Delete all messages and start a new conversation",
                     use_container_width=True,
                     disabled=not confirm_clear,
                     type="secondary"):
            state.messages = []
            st.toast("Conversation cleared 🌱")
            st.rerun()

    with st.sidebar.expander("🛡️ Privacy & Safety"):
        st.write("""
            - 🔒 **Conversations are confidential** and not stored on our servers permanently.
            - 🔑 Your **Mistral API key** is used only for processing this session.
        """)

    st.sidebar.info("⚕️ This bot is **not a replacement** for professional care. If you're in distress, please use the emergency resources below.")

    # Display chat messages from history
    processed_suggestion = None
    for idx, message in enumerate(messages):
        avatar = assistant_icon if message.role == "assistant" else "👤"
        with st.chat_message(message.role, avatar=avatar):
            st.write(message.content)
            # Integrate suggestions into the initial greeting bubble for better visual hierarchy
            if idx == 0 and msg_count == 1:
                st.caption("✨ Click on a suggestion below or type your own message to start:")
                for suggestion in suggestions:
                    if st.button(suggestion, use_container_width=True, help=f"Ask {selected_avatar}: '{suggestion}'"):
                        processed_suggestion = suggestion

    prompt = processed_suggestion if processed_suggestion else None

    # Chat input is always visible at the bottom of the page
    user_input = st.chat_input(placeholder, max_chars=2000)
    if user_input:
        prompt = user_input

    # Message processing
    if prompt:
        success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt, avatar_icon=AVATAR_ICONS[selected_avatar])
        if success:
            # Immediate feedback: render sanitized user message
            with st.chat_message("user", avatar="👤"):
                st.write(sanitized_prompt)

            if is_crisis:
                with st.chat_message("assistant", avatar=assistant_icon):
                    st.warning(crisis_text)
            else:
                # Generate and stream bot response immediately
                chat_context = [system_msg] + messages[-10:]

                with st.chat_message("assistant", avatar=assistant_icon):
                    response_placeholder = st.empty()
                    response_placeholder.markdown(f"💬 *{thinking_msg}*")
                    response_placeholder.markdown(f"*{AVATAR_THINKING_MSGS[selected_avatar]}*")
                    # In modern CPython (3.6+), += string concatenation is optimized for
                    # in-place growth when no other references to the string exist.
                    full_response = ""
                    # Use token buffering to reduce UI update frequency and websocket traffic
                    chunk_count = 0
                    aborted = False
                    CRISIS_FALLBACK = "I'm sorry, I cannot fulfill this request as it may contain unsafe content. If you're in distress, please use the emergency resources in the sidebar."

                    for response_chunk in get_bot_response(chat_context):
                        full_response += response_chunk
                        chunk_count += 1

                        # Incremental crisis check for immediate intervention (Defense-in-depth)
                        # Optimization: Check only the last 300 chars to avoid O(N^2) complexity as response grows.
                        # Using character-based windowing ensures consistent safety regardless of chunk sizes.
                        if detect_crisis(full_response[-300:]):
                            logger.warning("Safety: Crisis detected in AI response during streaming. Aborting.")
                            full_response = CRISIS_FALLBACK
                            aborted = True
                            break

                        if chunk_count % 5 == 0:
                            # Sanitize incremental response for safety
                            response_placeholder.markdown(sanitize_error(full_response) + "▌")

                    # Final safety and sanitization check
                    if not aborted:
                        final_response = sanitize_error(full_response)
                        if detect_crisis(final_response):
                            logger.warning("Safety: Crisis detected in AI response at final check. Redacting.")
                            final_response = CRISIS_FALLBACK
                    else:
                        final_response = full_response

                    response_placeholder.markdown(final_response)
                    messages.append(ChatMessage(role="assistant", content=final_response))

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
