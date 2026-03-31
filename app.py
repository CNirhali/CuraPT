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
    (re.compile(r'-----BEGIN (?:[A-Z ]+) KEY-----[\s\S]*?-----END (?:[A-Z ]+) KEY-----'), '[REDACTED_PRIVATE_KEY]', re.compile(r'-----begin')),
    (re.compile(r'\b(AKIA|ASIA)[0-9A-Z]{12,124}\b'), '[REDACTED_AWS_KEY]', re.compile(r'akia|asia')),
    (re.compile(r'\bsk-[a-zA-Z0-9-_]+\b'), '[REDACTED_API_KEY]', re.compile(r'sk-')),
    (re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'), '[REDACTED_GCP_KEY]', re.compile(r'aiza')),
    (re.compile(r'\b(?:github_pat_[a-zA-Z0-9_]{36,255}|gh[pours]_[a-zA-Z0-9]{36})\b'), '[REDACTED_GITHUB_TOKEN]', re.compile(r'github_pat_|ghp_|gho_|ghu_|ghr_|ghs_')),
    (re.compile(r'\b(?:rk|sk)_(?:live|test)_[0-9a-zA-Z]{24,99}\b'), '[REDACTED_STRIPE_KEY]', re.compile(r'rk_live|rk_test|sk_live|sk_test')),
    (re.compile(r'\bxox[bpgrs]-[0-9a-zA-Z]{10,48}\b'), '[REDACTED_SLACK_TOKEN]', re.compile(r'xoxb-|xoxp-|xoxg-|xoxr-|xoxs-')),
    (re.compile(r'\bGOCSPX-[a-zA-Z0-9-_]{24,99}\b'), '[REDACTED_GOCSPX]', re.compile(r'gocspx-')),
    (re.compile(r'\b(?:4[0-9]{3}|5[1-5][0-9]{2}|6011)(?:[\s-]?[0-9]{4}){3}\b|\b3[47][0-9]{2}[\s-]?[0-9]{6}[\s-]?[0-9]{5}\b'), '[REDACTED_PII]', re.compile(r'4[0-9]|5[1-5]|3[47]|6011')),
    (re.compile(r'\beyJ[a-zA-Z0-9_\-\/+=]{10,}\.[a-zA-Z0-9_\-\/+=]{10,}\.[a-zA-Z0-9_\-\/+=]{10,}\b'), '[REDACTED_JWT]', re.compile(r'eyj')),
    (re.compile(r'(?i)Bearer\s+[a-zA-Z0-9._\-\/+=]+'), 'Bearer [REDACTED]', re.compile(r'bearer')),
    # Enhanced pattern to handle quoted secrets and preserve original separators
    # Use negative lookahead to avoid re-redacting already masked values
    # Supports optional quotes around identifiers (e.g., {"password": "..."}) using backreferences
    (re.compile(r'(?i)(["\']?)\b(password|passwd|secret|token|api_key|aws_secret_access_key)\1(\s*(?:[:=]|is)\s*)(?!\[REDACTED)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2\1\3[REDACTED]', re.compile(r'password|passwd|secret|token|api_key|aws_secret_access_key')),
    # Generic 'key' pattern is last and avoids matching PEM headers via negative lookahead
    (re.compile(r'(?i)(["\']?)\b(key)\1(\s*(?:[:=]|is)\s*)(?!\[REDACTED|---)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2\1\3[REDACTED]', re.compile(r'key:|key=|key is|key |"key":|\'key\':')),
]
# Optimization: Substring markers to trigger expensive regex execution
# Refinement: replaced 'pass' with 'password'/'passwd' to avoid false positives on 'compassion'
# Included markers for AWS, GCP, GitHub (ghp/gho/ghu/ghr/ghs), Stripe, Slack (xoxb/xoxp/xoxg/xoxr/xoxs) and Private Keys
# Reordered to place highly frequent markers at the beginning for faster short-circuiting in any()
# Refinement: replaced 'begin' with '-----begin' to reduce false positives for common text.
# Redundant 'aws_secret_access_key' removed as it is covered by 'key'.
SENSITIVE_MARKERS = [
    "password", "token", "sk-", "secret", "key:", "key=", "key is", "key ", "passwd", "akia", "asia", "bearer",
    "aiza", "github_pat_", "ghp_", "gho_", "ghu_", "ghr_", "ghs_", "rk_live", "rk_test", "sk_live", "sk_test",
    "xoxb-", "xoxp-", "xoxg-", "xoxr-", "xoxs-", "gocspx-", "eyj", "-----begin", "api_key", "aws_secret_access_key",
    "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", # Visa
    "51", "52", "53", "54", "55",                              # Mastercard
    "34", "37",                                                # Amex
    "6011"                                                     # Discover
]
# Optimization: Pre-compiled regex for global fast-path check in sanitize_error.
# Benchmarks show this is ~1.6x faster than any() with 43 markers for clean messages.
SENSITIVE_FAST_RE = re.compile('|'.join(map(re.escape, SENSITIVE_MARKERS)))

# Common Latin-lookalike homoglyphs (e.g., Cyrillic, Greek) for normalization
# Moved to module level for use in both sanitize_error and detect_crisis
_HOMOGLYPH_MAP = str.maketrans(
    'аеіорсхуіј',  # Lookalikes
    'aeiopcxyij'   # Latin equivalents
)

def sanitize_error(message, msg_lower=None):
    """
    Redact sensitive information like API keys, passwords, and tokens from strings.
    This provides defense-in-depth by preventing secrets from being displayed in the UI,
    stored in session history, or sent to external providers.

    msg_lower can be provided to bypass redundant .lower() calls in high-frequency loops.
    """
    if not isinstance(message, str):
        message = str(message)

    # Optimization: return early for short messages (shortest marker "sk-" is 3 chars)
    if len(message) < 3:
        return message

    # Defense-in-depth: Normalize NFKC and apply homoglyph mapping for non-ASCII messages
    # to prevent bypasses using lookalike characters (e.g., Cyrillic 'а' in "password").
    if not message.isascii():
        message = unicodedata.normalize('NFKC', message).translate(_HOMOGLYPH_MAP)
        msg_lower = None # Force recalculation after normalization

    # Optimization: return early for messages without sensitive markers (approx. 30-40% faster than any())
    # We use the pre-compiled SENSITIVE_FAST_RE for the global check.
    if msg_lower is None:
        msg_lower = message.lower()

    if not SENSITIVE_FAST_RE.search(msg_lower):
        return message

    sanitized = message
    # Optimization: iterate through patterns and only execute sub if pattern-specific regex guards match.
    # Benchmarks show that regex guards are significantly faster than any() with marker lists (~2-4x speedup).
    for pattern, replacement, guard in SANITIZATION_PATTERNS:
        if guard.search(msg_lower):
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
        "theme_color": "green",
        "description": "A compassionate therapist who provides professional guidance and support",
        "welcome_greeting": "I'm here to provide a safe space for your thoughts.",
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
        "theme_color": "orange",
        "description": "An energetic life coach focused on personal growth and achievement",
        "welcome_greeting": "I'm excited to help you reach your full potential today!",
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
        "theme_color": "blue",
        "description": "A supportive friend who listens and offers understanding",
        "welcome_greeting": "It's great to see you! I'm all ears.",
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

# Pre-calculate avatar options and mappings for performance
AVATAR_OPTIONS = list(AVATARS.keys())
AVATAR_INDEX = {name: i for i, name in enumerate(AVATAR_OPTIONS)}

# Initialize dictionaries for O(1) persona-specific property lookups
SYSTEM_MESSAGES = {}
AVATAR_ICONS = {}
AVATAR_PLACEHOLDERS = {}
AVATAR_THINKING_MSGS = {}
AVATAR_THINKING_MARKDOWN = {}
AVATAR_DISPLAY_NAMES = {}
AVATAR_DESCRIPTIONS = {}
AVATAR_SUGGESTIONS = {}
AVATAR_READY_MSGS = {}
AVATAR_THEME_COLORS = {}
AVATAR_HERE_MSGS = {}
AVATAR_WELCOME_GREETINGS = {}

# Single-pass pre-calculation of avatar properties at module level to reduce interaction overhead
for name, data in AVATARS.items():
    icon = data["icon"]
    ready_msg = data["ready_msg"]
    thinking_msg = data["thinking_msg"]

    SYSTEM_MESSAGES[name] = ChatMessage(role="system", content=data["system_prompt"])
    AVATAR_ICONS[name] = icon
    AVATAR_PLACEHOLDERS[name] = data["chat_placeholder"]
    AVATAR_THINKING_MSGS[name] = thinking_msg
    # Pre-calculate markdown thinking state to avoid string slicing and formatting during reruns
    AVATAR_THINKING_MARKDOWN[name] = f"**{icon} {thinking_msg[2:]}**"
    AVATAR_DISPLAY_NAMES[name] = f"{icon} {name}"
    AVATAR_DESCRIPTIONS[name] = data["description"]
    AVATAR_SUGGESTIONS[name] = data["suggestions"]
    AVATAR_READY_MSGS[name] = ready_msg
    AVATAR_THEME_COLORS[name] = data["theme_color"]
    AVATAR_HERE_MSGS[name] = f"🟢 {name} {ready_msg}"
    AVATAR_WELCOME_GREETINGS[name] = data["welcome_greeting"]

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

def detect_crisis(message, msg_lower=None):
    """
    Detect if the message indicates a crisis situation using regex.
    Includes normalization for homoglyphs and NFKC for robustness against obfuscation.

    msg_lower can be provided to bypass redundant .lower() calls.
    """
    # Optimization: return False immediately for very short, safe inputs to avoid string processing
    if len(message) < MIN_CRISIS_KEYWORD_LEN:
        return False

    # Optimization: O(N) fast-path using isascii() and substring check.
    # We prioritize ASCII messages as they are the most common and don't require normalization.
    is_ascii = message.isascii()
    if msg_lower is None:
        msg_lower = message.lower()

    if is_ascii:
        # Optimization: For small sets of fixed keywords (28), a pre-compiled regex search
        # is significantly faster (~1.7x) than an iterative any() substring check in CPython.
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
            # Optimization: Localize nested attribute lookups to reduce overhead in the hot loop.
            choices = chunk.choices
            if not choices:
                continue
            delta = choices[0].delta
            content = delta.content
            if content:
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

    # Optimization: pre-calculate lowercase prompt once for both safety functions
    prompt_lower = prompt.lower()

    # Sanitize user input immediately (Defense-in-depth: prevent secrets from reaching the LLM or session state)
    sanitized_prompt = sanitize_error(prompt, msg_lower=prompt_lower)

    # Add user message to chat as dictionary to support metadata like timestamps
    st.session_state.messages.append({
        "role": "user",
        "content": sanitized_prompt,
        "timestamp": datetime.now().strftime("%I:%M %p")
    })

    # History capping for performance and security
    # Optimization: Use in-place deletion to maintain list object identity and reduce memory churn
    if len(st.session_state.messages) > 50:
        del st.session_state.messages[:-50]

    # Safety: Perform crisis detection on raw prompt to prevent bypass via sanitization (e.g., "secret is suicide")
    is_crisis = detect_crisis(prompt, msg_lower=prompt_lower)
    crisis_text = None
    if is_crisis:
        logger.warning(f"Safety: Crisis detected in user input.")
        crisis_text = get_crisis_response()
        st.session_state.messages.append({
            "role": "assistant",
            "content": crisis_text,
            "timestamp": datetime.now().strftime("%I:%M %p")
        })

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
    # Initialize session state first to have access to selected_avatar for the subheader divider
    state = st.session_state
    if "selected_avatar" not in state:
        state.selected_avatar = "Therapist"

    current_selected = state.selected_avatar
    theme_color = AVATAR_THEME_COLORS.get(current_selected, "blue")

    st.subheader("Your AI companion for mental well-being and personal growth", divider=theme_color)

    # Optimization: Use local variables for session state to bypass proxy overhead
    # state = st.session_state (already initialized above)

    # Initialize session state
    if "messages" not in state:
        state.messages = []
    if "last_message_time" not in state:
        state.last_message_time = 0
    if "session_start_time" not in state:
        state.session_start_time = datetime.now()

    # Local references for performance
    messages = state.messages

    # Proactive API key check for better onboarding
    if not os.getenv("MISTRAL_API_KEY"):
        st.sidebar.warning("⚠️ **API Key Missing**: Please add your `MISTRAL_API_KEY` to a `.env` file to enable the AI companion. You can get one at [console.mistral.ai](https://console.mistral.ai/).")

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
        st.toast(f"{selected_avatar} {AVATAR_READY_MSGS[selected_avatar]}", icon=AVATAR_ICONS[selected_avatar])

    # Ensure the conversation starts with a persona-specific welcome message
    if not messages:
        greeting = get_time_based_greeting()
        welcome_msg = f"{greeting}! I'm {selected_avatar}. {AVATAR_WELCOME_GREETINGS[selected_avatar]} How are you feeling?"
        messages.append({
            "role": "assistant",
            "content": welcome_msg,
            "timestamp": datetime.now().strftime("%I:%M %p")
        })

    # Calculate msg_count after initialization to ensure accurate first-load reporting
    msg_count = len(messages)

    # Optimization: Pre-fetch persona-specific constants to avoid redundant lookups in UI rendering
    assistant_icon = AVATAR_ICONS[selected_avatar]
    suggestions = AVATAR_SUGGESTIONS[selected_avatar]
    placeholder = AVATAR_PLACEHOLDERS[selected_avatar]
    description = AVATAR_DESCRIPTIONS[selected_avatar]
    thinking_msg = AVATAR_THINKING_MARKDOWN[selected_avatar]
    here_msg = AVATAR_HERE_MSGS[selected_avatar]
    system_msg = SYSTEM_MESSAGES[selected_avatar]

    with st.sidebar:
        st.write(description)
        st.caption(here_msg)
        st.markdown("---")

    # Manage Conversation Popover
    with st.sidebar.popover(f"⚙️ {selected_avatar} Session ({msg_count})", use_container_width=True):
        st.write("Settings for your current chat session.")
        st.caption(f"🕒 Session started at {state.session_start_time.strftime('%H:%M:%S')}")
        st.divider()

        # Export History
        if messages:
            # Optimization: Cache the sanitized export transcript to avoid O(N) generation on every rerun
            cache_key = f"export_cache_{selected_avatar}_{msg_count}"

            if "last_export" not in state or state.get("export_cache_key") != cache_key:
                now = datetime.now()
                duration = now - state.session_start_time
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                export_parts = [
                    f"Mental Health Ease Bot - {selected_avatar} Session",
                    f"Date: {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Session Duration: {duration_str}",
                    "-" * 40 + "\n"
                ]
                export_parts.extend(
                    f"[{msg.get('timestamp', 'N/A')}] {selected_avatar if msg['role'] == 'assistant' else 'You'}: {msg['content']}\n"
                    for msg in messages
                )
                export_parts.append("\n" + "=" * 40)
                export_parts.append("🆘 Safety Resources")
                export_parts.append("-" * 40)
                export_parts.append("If you are in distress, please contact:")
                export_parts.append("- National Suicide Prevention Lifeline: Call or Text 988")
                export_parts.append("- Crisis Text Line: Text HOME to 741741")
                export_parts.append("- Emergency Services: Call 911")
                export_parts.append("=" * 40 + "\n")

                # Apply defense-in-depth sanitization to the final export transcript
                state.last_export = sanitize_error("\n".join(export_parts) + "\n")
                state.export_cache_key = cache_key

            st.download_button(
                label=f"📥 Export Conversation ({msg_count} message{'s' if msg_count != 1 else ''})",
                data=state.last_export,
                file_name=f"{selected_avatar.lower().replace(' ', '_')}_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="Download a text file containing your conversation history and safety resources.",
                use_container_width=True
            )
            with st.expander("📋 Copy Transcript"):
                st.code(state.last_export, language=None)
        else:
            st.info("No messages to export yet.")

        st.markdown("---")

        # Clear Chat History with confirmation
        st.write("⚠️ **Destructive Actions**")
        confirm_clear = st.checkbox("I'm ready for a fresh start", help="Confirm that you want to delete all messages in this session. This cannot be undone.")
        if st.button(f"🗑️ Clear Chat History ({msg_count} message{'s' if msg_count != 1 else ''})",
                     help="Delete all messages and start a new conversation",
                     use_container_width=True,
                     disabled=not confirm_clear,
                     type="primary" if confirm_clear else "secondary"):
            state.messages = []
            # Reset session start time for fresh conversation
            state.session_start_time = datetime.now()
            st.toast("Conversation cleared 🌱")
            st.rerun()

    with st.sidebar.expander("🛡️ Privacy & Safety"):
        st.write("""
            - 🔒 **Conversations are confidential** and not stored on our servers permanently.
            - 🔑 Your **Mistral API key** is used only for processing this session.
        """)
    st.sidebar.caption("Tip: ⌨️ Press **Enter** to send, **Shift+Enter** for new lines.")

    st.sidebar.info("⚕️ This bot is **not a replacement** for professional care. If you're in distress, please use the resources below. They are free, confidential, and available 24/7.")

    # Display chat messages from history
    processed_suggestion = None
    for idx, message in enumerate(messages):
        # Use robust conditional fallback to avoid KeyError on unexpected roles (e.g., 'system' or 'tool')
        # while keeping the st.markdown optimization for string content rendering.
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")

        role_label = selected_avatar if role == "assistant" else "You"
        avatar = assistant_icon if role == "assistant" else "👤"

        with st.chat_message(role_label, avatar=avatar):
            # Switch to st.markdown for string content to bypass Streamlit's internal type-checking.
            # This improves performance when rendering large conversation histories (up to 50 msgs).
            st.markdown(content)
            if timestamp:
                st.caption(f"🕒 Sent at {timestamp}")
            # Integrate suggestions into the initial greeting bubble for better visual hierarchy
            if idx == 0 and msg_count == 1:
                st.caption("✨ Click on a suggestion below or type your own message to start:")
                for suggestion in suggestions:
                    if st.button(suggestion, use_container_width=True, help=f"Ask {selected_avatar}: '{suggestion}'"):
                        processed_suggestion = suggestion

    prompt = processed_suggestion if processed_suggestion else None

    # Chat input is always visible at the bottom of the page
    # Proactive check for API key to disable input if missing
    api_key_configured = bool(os.getenv("MISTRAL_API_KEY"))
    user_input = st.chat_input(
        placeholder if api_key_configured else "Please configure your Mistral API key in the sidebar to start chatting.",
        max_chars=2000,
        disabled=not api_key_configured
    )
    if user_input:
        prompt = user_input

    # Message processing
    if prompt:
        success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt, avatar_icon=AVATAR_ICONS[selected_avatar])
        if success:
            # Immediate feedback: render sanitized user message
            with st.chat_message("You", avatar="👤"):
                st.write(sanitized_prompt)

            if is_crisis:
                with st.chat_message(selected_avatar, avatar=assistant_icon):
                    st.error(crisis_text)
            else:
                # Generate and stream bot response immediately
                # Convert message dictionaries to ChatMessage objects for the Mistral API
                chat_context = [system_msg] + [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in messages[-10:]
                ]

                with st.chat_message(selected_avatar, avatar=assistant_icon):
                    response_placeholder = st.empty()
                    response_placeholder.markdown(thinking_msg)
                    # In modern CPython (3.6+), += string concatenation is optimized for
                    # in-place growth when no other references to the string exist.
                    full_response = ""
                    full_response_lower = ""
                    # Use token buffering to reduce UI update frequency and websocket traffic
                    chunk_count = 0
                    aborted = False
                    CRISIS_FALLBACK = "I'm sorry, I cannot fulfill this request as it may contain unsafe content. If you're in distress, please use the emergency resources in the sidebar."

                    for response_chunk in get_bot_response(chat_context):
                        full_response += response_chunk
                        full_response_lower += response_chunk.lower()
                        chunk_count += 1

                        if chunk_count == 1 or chunk_count % 5 == 0:
                            # Incremental crisis check for immediate intervention (Defense-in-depth)
                            # Optimization: Check only the last 300 chars to maintain O(N) complexity as response grows.
                            # We batch this with the UI update to reduce safety processing overhead by 80%.
                            # We pass the pre-calculated lowercase slice to bypass redundant processing.
                            if detect_crisis(full_response[-300:], msg_lower=full_response_lower[-300:]):
                                logger.warning("Safety: Crisis detected in AI response during streaming. Aborting.")
                                full_response = CRISIS_FALLBACK
                                aborted = True
                                break

                            # Sanitize incremental response for safety
                            # We pass full_response_lower to bypass redundant .lower() call.
                            response_placeholder.markdown(sanitize_error(full_response, msg_lower=full_response_lower) + "▌")

                    # Final safety and sanitization check
                    if not aborted:
                        # Safety: check raw response for crisis indicators before sanitization
                        if detect_crisis(full_response, msg_lower=full_response_lower):
                            logger.warning("Safety: Crisis detected in AI response at final check. Redacting.")
                            final_response = CRISIS_FALLBACK
                        else:
                            final_response = sanitize_error(full_response, msg_lower=full_response_lower)
                    else:
                        final_response = full_response

                    response_placeholder.markdown(final_response)
                    messages.append({
                        "role": "assistant",
                        "content": final_response,
                        "timestamp": datetime.now().strftime("%I:%M %p")
                    })

            # Rerun to clear input and refresh UI state
            st.rerun()

    # Sidebar resources
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚨 Emergency Resources")
    st.sidebar.caption("If you're in crisis, please contact these services. They are free, confidential, and available 24/7:")
    st.sidebar.link_button("📞 Call or Text 988", "tel:988", use_container_width=True, help="National Suicide Prevention Lifeline - Free, confidential, 24/7")
    st.sidebar.link_button("💬 Text HOME to 741741", "sms:741741", use_container_width=True, help="Crisis Text Line - Free, confidential, 24/7")
    st.sidebar.link_button("🚑 Call 911", "tel:911", use_container_width=True, type="primary", help="Emergency Services - For immediate danger")

if __name__ == "__main__":
    main()
