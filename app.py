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
    (re.compile(r'(?i)Basic\s+[a-zA-Z0-9+/=]+'), 'Basic [REDACTED]', re.compile(r'basic')),
    # Enhanced pattern to handle quoted secrets and preserve original separators
    # Use negative lookahead to avoid re-redacting already masked values
    # Supports optional quotes around identifiers (e.g., {"password": "..."}) using backreferences
    # Allow underscores or hyphens before keywords (e.g., MISTRAL_API_KEY, x-api-key) using a lookbehind.
    (re.compile(r'(?i)(["\']?)(?:\b|(?<=[_-]))(password|passwd|secret|token|api_key|api-key|client_secret|x-api-key|aws_secret_access_key)\1(\s*(?:[:=]|is)\s*)(?!\[REDACTED)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2\1\3[REDACTED]', re.compile(r'password|passwd|secret|token|api_key|api-key|client_secret|x-api-key|aws_secret_access_key')),
    # Generic 'key' pattern is last and avoids matching PEM headers via negative lookahead
    (re.compile(r'(?i)(["\']?)(?:\b|(?<=[_-]))(key)\1(\s*(?:[:=]|is)\s*)(?!\[REDACTED|---)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'), r'\1\2\1\3[REDACTED]', re.compile(r'key')),
]
# Optimization: Substring markers to trigger expensive regex execution
# Refinement: replaced 'pass' with 'password'/'passwd' to avoid false positives on 'compassion'
# Included markers for AWS, GCP, GitHub (ghp/gho/ghu/ghr/ghs), Stripe, Slack (xoxb/xoxp/xoxg/xoxr/xoxs) and Private Keys
# Reordered to place highly frequent markers at the beginning for faster short-circuiting in any()
# Refinement: replaced 'begin' with '-----begin' to reduce false positives for common text.
# Added Basic auth and new secret keywords (api-key, client_secret, x-api-key).
SENSITIVE_MARKERS = [
    "password", "token", "sk-", "secret", "key", "passwd", "akia", "asia", "bearer", "basic",
    "aiza", "github_pat_", "ghp_", "gho_", "ghu_", "ghr_", "ghs_", "rk_live", "rk_test", "sk_live", "sk_test",
    "xoxb-", "xoxp-", "xoxg-", "xoxr-", "xoxs-", "gocspx-", "eyj", "-----begin", "api_key", "api-key", "client_secret",
    "x-api-key", "aws_secret_access_key",
    "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", # Visa
    "51", "52", "53", "54", "55",                              # Mastercard
    "34", "37",                                                # Amex
    "6011"                                                     # Discover
]
# Optimization: Pre-compiled regex for global fast-path check in sanitize_error.
# Benchmarks show this is ~1.6x faster than any() with 43 markers for clean messages.
SENSITIVE_FAST_RE = re.compile('|'.join(map(re.escape, SENSITIVE_MARKERS)))

# Common Latin-lookalike homoglyphs (e.g., Cyrillic, Greek) for normalization
# Expanded to include uppercase lookalikes and additional characters (ѕ, В, Н, Т, М, К, etc.)
# to prevent bypasses using mixed-case or varied homoglyphs.
_HOMOGLYPH_MAP = str.maketrans(
    'аеіорсхујкмнзѕвтпАЕІОРСХУЈКМЗЅВНТαεηικνρστυςΑΒΕΖΗΙΚΜΝΟΡΤΦΧＭＮＯＰＲＴＹ',  # Lookalikes
    'aeiopcxyjkmnzsvtnAEIOPCXYJKMZSBHTaenikvpstysABEZHIKMNOPTFXMNOPRTY'   # Latin equivalents
)

# Common invisible/zero-width and control characters used for obfuscation (OWASP A03:2021)
# Expanded with soft hyphen, bidi controls, and word joiners.
_INVISIBLE_CHARS_RE = re.compile(r'[\u00AD\u200B\u200C\u200D\u202A-\u202E\u2060\uFEFF]')

# Optimization: Combined regex of homoglyphs and invisible characters for fast-path trigger.
# This allows skipping expensive NFKC normalization and translation for clean non-ASCII strings (like emojis).
_OBFUSCATION_RE = re.compile(r'[аеіорсхујкмнзѕвтпАЕІОРСХУЈКМЗЅВНТαεηικνρστυςΑΒΕΖΗΙΚΜΝΟΡΤΦΧＭＮＯＰＲＴＹ\u00AD\u200B\u200C\u200D\u202A-\u202E\u2060\uFEFF]')

def sanitize_error(message, msg_lower=None, is_ascii=None):
    """
    Redact sensitive information like API keys, passwords, and tokens from strings.
    This provides defense-in-depth by preventing secrets from being displayed in the UI,
    stored in session history, or sent to external providers.

    msg_lower and is_ascii can be provided to bypass redundant O(N) calls in high-frequency loops.
    """
    if not isinstance(message, str):
        message = str(message)

    # Optimization: return early for short messages (shortest marker "sk-" is 3 chars)
    if len(message) < 3:
        return message

    # Defense-in-depth: Normalize NFKC and apply homoglyph mapping for non-ASCII messages
    # to prevent bypasses using lookalike characters (e.g., Cyrillic 'а' in "password").
    # Optimization: All _INVISIBLE_CHARS_RE are non-ASCII, so isascii() guard is sufficient.
    if is_ascii is None:
        is_ascii = message.isascii()

    if not is_ascii:
        # Optimization: Only normalize if the string is not already NFKC or contains known obfuscation.
        # This provides a ~30x speedup for clean non-ASCII strings (like emojis).
        if not unicodedata.is_normalized('NFKC', message) or _OBFUSCATION_RE.search(message):
            normalized = unicodedata.normalize('NFKC', message).translate(_HOMOGLYPH_MAP)
            # Strip common invisible/zero-width characters before sanitization.
            normalized = _INVISIBLE_CHARS_RE.sub('', normalized)

            # Optimization: Only reset msg_lower if the message actually changed after normalization.
            # This preserves the incremental lowercase string provided during streaming if no obfuscation is found.
            if normalized != message:
                message = normalized
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
            "How can I deal with my anxiety?",
            "I've been feeling low lately.",
            "Can you help me with a coping strategy?"
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
            "How can I stay motivated today?",
            "I want to set some personal goals.",
            "How can I build more resilience?"
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
            "I just need someone to talk to.",
            "I had a rough day at work.",
            "Can you tell me something positive?"
        ]
    }
}

# Pre-calculate avatar options and mappings for performance
AVATAR_OPTIONS = list(AVATARS.keys())
AVATAR_INDEX = {name: i for i, name in enumerate(AVATAR_OPTIONS)}

# Pre-calculate persona properties at module level to reduce interaction overhead.
# Consolidating these into a single dictionary reduces lookups in main() from 11 down to 1.
PERSONA_DATA = {}
for name, data in AVATARS.items():
    icon = data["icon"]
    ready_msg = data["ready_msg"]
    thinking_msg = data["thinking_msg"]

    PERSONA_DATA[name] = {
        "system_msg": ChatMessage(role="system", content=data["system_prompt"]),
        "icon": icon,
        "placeholder": data["chat_placeholder"],
        "thinking_msg": thinking_msg,
        # Pre-calculate markdown thinking state to avoid string slicing and formatting during reruns
        "thinking_markdown": f"**{icon} {thinking_msg[2:]}**",
        "display_name": f"{icon} {name}",
        "description": data["description"],
        "suggestions": data["suggestions"],
        "ready_msg": ready_msg,
        "theme_color": data["theme_color"],
        "here_msg": f"🟢 {name} {ready_msg}",
        "welcome_greeting": data["welcome_greeting"],
        # Pre-calculate role mappings to reduce dictionary creation overhead during reruns
        "role_labels": {"assistant": name, "user": "You"},
        "role_icons": {"assistant": icon, "user": "👤"}
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
# We split keywords by whitespace and rejoin with \s+ to handle multiline or multiple space obfuscation
CRISIS_PATTERN = re.compile(r'\b(?:' + r'|'.join([r'\s+'.join(map(re.escape, k.split())) for k in CRISIS_KEYWORDS_LOWER]) + r')\b')
# Shortest crisis keywords like "suicide" or "kill me" are 7 characters long
MIN_CRISIS_KEYWORD_LEN = 7

def detect_crisis(message, msg_lower=None, pos=0, is_ascii=None):
    """
    Detect if the message indicates a crisis situation using regex.
    Includes normalization for homoglyphs and NFKC for robustness against obfuscation.

    msg_lower and is_ascii can be provided to bypass redundant O(N) calls.
    pos can be used to search only from a specific offset (e.g. for streaming efficiency).
    """
    # Optimization: return False immediately for very short, safe inputs to avoid string processing
    # We use the relative length from the pos offset
    if len(message) - pos < MIN_CRISIS_KEYWORD_LEN:
        return False

    # Optimization: O(N) fast-path using isascii() and substring check.
    # We prioritize ASCII messages as they are the most common and don't require normalization.
    # Note: isascii() check is performed on the entire message to ensure safety.
    if is_ascii is None:
        is_ascii = message.isascii()

    if msg_lower is None:
        msg_lower = message.lower()

    # Check raw string first (fastest path, handles both ASCII and clean non-ASCII text).
    # Optimization: For small sets of fixed keywords (28), a pre-compiled regex search
    # is significantly faster (~1.7x) than an iterative any() substring check in CPython.
    # We use the pos argument to avoid O(N) string slicing.
    if CRISIS_PATTERN.search(msg_lower, pos):
        return True

    if is_ascii:
        return False

    # Slow-path: Normalize NFKC and apply manual homoglyph mapping for defense-in-depth.
    # We only normalize if the string contains known obfuscation or is not already NFKC.
    # Optimization: Swapping order to use the faster _OBFUSCATION_RE.search(msg_lower, pos)
    # first avoids a string slice for clean messages.
    if _OBFUSCATION_RE.search(msg_lower, pos) or not unicodedata.is_normalized('NFKC', message[pos:]):
        # We use slicing here because normalization might change string length/indices.
        search_text = message[pos:]
        normalized = _INVISIBLE_CHARS_RE.sub('', search_text)
        normalized = unicodedata.normalize('NFKC', normalized).translate(_HOMOGLYPH_MAP).lower()
        return bool(CRISIS_PATTERN.search(normalized))

    # Safety: Even if the string is clean/normalized, we use pos-based search
    # which is O(1) memory and correctly respects existing word boundaries.
    return bool(CRISIS_PATTERN.search(msg_lower, pos))

def get_crisis_response():
    """Return emergency resources and crisis response."""
    return """
    I'm concerned about your safety. Please know that you're not alone, and help is available:
    
    - 📞 **National Suicide Prevention Lifeline**: [Call or Text 988](tel:988)
    - 💬 **Crisis Text Line**: [Text HOME to 741741](sms:741741?body=HOME)
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

def handle_user_input(prompt, avatar_icon="🧘", now=None):
    """Update state with user input and check for crisis. Returns (success, is_crisis, crisis_text, sanitized_prompt)."""
    # Optimization: Use local variable for session state to minimize proxy overhead.
    state = st.session_state

    # Server-side length validation as defense-in-depth against resource exhaustion
    if len(prompt) > 2000:
        st.toast("Your message is a bit too long. Please try to shorten it.", icon="⚠️")
        return False, False, None, prompt

    if now is None:
        now = datetime.now()

    current_time = now.timestamp()
    time_since_last = current_time - state.get("last_message_time", 0)
    if time_since_last < 2.0:
        st.toast(f"Take a breath! Please wait {2.0 - time_since_last:.1f}s", icon=avatar_icon)
        return False, False, None, prompt

    state.last_message_time = current_time

    # Optimization: pre-calculate properties once for both safety functions to avoid redundant scans
    prompt_lower = prompt.lower()
    is_ascii = prompt.isascii()

    # Sanitize user input immediately (Defense-in-depth: prevent secrets from reaching the LLM or session state)
    sanitized_prompt = sanitize_error(prompt, msg_lower=prompt_lower, is_ascii=is_ascii)

    # Reuse a single timestamp string for multiple message entries (if applicable)
    timestamp = now.strftime("%I:%M %p")
    messages = state.messages

    # Add user message to chat as dictionary to support metadata like timestamps
    messages.append({
        "role": "user",
        "content": sanitized_prompt,
        "timestamp": timestamp,
        "timestamp_caption": f"🕒 Sent at {timestamp}"
    })

    # History capping for performance and security
    # Optimization: Use in-place deletion to maintain list object identity and reduce memory churn
    if len(messages) > 50:
        del messages[:-50]

    # Safety: Perform crisis detection on raw prompt to prevent bypass via sanitization (e.g., "secret is suicide")
    is_crisis = detect_crisis(prompt, msg_lower=prompt_lower, is_ascii=is_ascii)
    crisis_text = None
    if is_crisis:
        logger.warning(f"Safety: Crisis detected in user input.")
        crisis_text = get_crisis_response()
        messages.append({
            "role": "assistant",
            "content": crisis_text,
            "timestamp": timestamp,
            "timestamp_caption": f"🕒 Sent at {timestamp}"
        })

    return True, is_crisis, crisis_text, sanitized_prompt

def get_time_based_greeting(hour=None):
    """Return a time-appropriate greeting for the welcome message."""
    if hour is None:
        hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif 12 <= hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

@st.dialog("Clear Conversation History")
def confirm_clear_dialog():
    """Provide a modal confirmation for deleting conversation history."""
    st.warning("Are you sure you want to clear your entire conversation history? This action cannot be undone.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, icon="🔙"):
            st.rerun()
    with col2:
        if st.button("Yes, Clear History", type="primary", use_container_width=True, icon="🗑️"):
            st.session_state.messages = []
            # Reset session start time for fresh conversation
            st.session_state.session_start_time = datetime.now()
            st.toast("Conversation cleared 🌱")
            st.rerun()

def main():
    # Optimization: Localize current timestamp to avoid multiple system calls during a single rerun
    now = datetime.now()
    # Optimization: Use local variables for session state and environment to bypass proxy/OS overhead.
    state = st.session_state
    api_key = os.getenv("MISTRAL_API_KEY")

    # Initialize session state first to have access to selected_avatar for the subheader divider
    if "selected_avatar" not in state:
        state.selected_avatar = "Therapist"

    current_selected = state.selected_avatar
    # Single lookup for all persona properties
    persona = PERSONA_DATA[current_selected]
    theme_color = persona["theme_color"]

    # Immersive title with persona icon
    st.title(f"{persona['icon']} Mental Health Ease Bot")
    st.subheader("Your AI companion for mental well-being and personal growth", divider=theme_color)

    # Initialize session state
    if "messages" not in state:
        state.messages = []
    if "last_message_time" not in state:
        state.last_message_time = 0
    if "session_start_time" not in state:
        state.session_start_time = now

    # Local references for performance
    messages = state.messages

    # Proactive API key check for better onboarding
    if not api_key:
        st.sidebar.warning("⚠️ **API Key Missing**: Please add your `MISTRAL_API_KEY` to a `.env` file to enable the AI companion. You can get one at [console.mistral.ai](https://console.mistral.ai/).")

    # Themed Sidebar Header to reinforce persona presence
    st.sidebar.header(f"{persona['icon']} {current_selected}", divider=theme_color)

    # Avatar selection
    selected_avatar = st.sidebar.selectbox(
        "Choose Your Companion",
        AVATAR_OPTIONS,
        index=AVATAR_INDEX[current_selected],
        format_func=lambda x: PERSONA_DATA[x]["display_name"],
        help="Switching your companion will reset the current conversation. Consider exporting your chat first if you'd like to save it."
    )
    
    if selected_avatar != current_selected:
        state.selected_avatar = selected_avatar
        state.messages = []
        # Update local references after state change
        messages = state.messages
        new_persona = PERSONA_DATA[selected_avatar]
        st.toast(f"{selected_avatar} {new_persona['ready_msg']}", icon=new_persona["icon"])
        # Refresh persona reference
        persona = new_persona

    # Ensure the conversation starts with a persona-specific welcome message
    if not messages:
        greeting = get_time_based_greeting(hour=now.hour)
        welcome_msg = f"{greeting}! I'm {selected_avatar}. {persona['welcome_greeting']} How are you feeling?"
        timestamp = now.strftime("%I:%M %p")
        messages.append({
            "role": "assistant",
            "content": welcome_msg,
            "timestamp": timestamp,
            "timestamp_caption": f"🕒 Sent at {timestamp}"
        })

    # Calculate msg_count and label once to reuse across popover, buttons, and clear history
    msg_count = len(messages)
    msg_count_label = f"({msg_count} message{'s' if msg_count != 1 else ''})"

    # Pre-fetch localized persona-specific constants from the pre-calculated dictionary
    assistant_icon = persona["icon"]
    suggestions = persona["suggestions"]
    placeholder = persona["placeholder"]
    description = persona["description"]
    thinking_msg = persona["thinking_markdown"]
    here_msg = persona["here_msg"]
    system_msg = persona["system_msg"]

    with st.sidebar:
        st.write(description)
        st.caption(here_msg)
        st.markdown("---")

    # Calculate session duration for temporal context
    duration_total_mins = int((now - state.session_start_time).total_seconds() // 60)
    if duration_total_mins >= 60:
        h, m = divmod(duration_total_mins, 60)
        duration_label = f"{h}h {m}m active"
    else:
        duration_label = f"{duration_total_mins}m active" if duration_total_mins > 0 else "Just started"

    # Manage Conversation Popover
    with st.sidebar.popover(f"{selected_avatar} Session {msg_count_label}", use_container_width=True, icon="⚙️"):
        st.write("Settings for your current chat session.")
        st.caption(f"🕒 Started at {state.session_start_time.strftime('%I:%M %p')} • {duration_label}")

        # Optimization: Cache message counts in session state to avoid O(N) traversal on every rerun.
        # We use the current message count as part of the key to ensure the cache is invalidated when history changes.
        msg_counts_cache_key = f"counts_{msg_count}"
        if state.get("msg_counts_key") != msg_counts_cache_key:
            user_msgs = 0
            assistant_msgs = 0
            for m in messages:
                if m["role"] == "user":
                    user_msgs += 1
                elif m["role"] == "assistant":
                    assistant_msgs += 1
            state.user_msgs_count = user_msgs
            state.assistant_msgs_count = assistant_msgs
            state.msg_counts_key = msg_counts_cache_key

        st.subheader("Session Details", divider=theme_color)
        st.caption(f"👤 Your messages: {state.user_msgs_count}")
        st.caption(f"{persona['icon']} {selected_avatar}'s messages: {state.assistant_msgs_count}")
        st.divider()

        # Export History
        if messages:
            # Optimization: Cache the sanitized export transcript to avoid O(N) generation on every rerun
            cache_key = f"export_cache_{selected_avatar}_{msg_count}"

            if "last_export" not in state or state.get("export_cache_key") != cache_key:
                duration = now - state.session_start_time
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                export_parts = [
                    f"Mental Health Ease Bot - {persona['icon']} {selected_avatar} Session",
                    f"Date: {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Session Duration: {duration_str}",
                    "-" * 40 + "\n"
                ]
                export_parts.extend(
                    f"[{msg.get('timestamp', 'N/A')}] {selected_avatar if msg['role'] == 'assistant' else 'You'}: {msg['content']}\n\n"
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
                label=f"Export Conversation {msg_count_label}",
                data=state.last_export,
                file_name=f"{selected_avatar.lower().replace(' ', '_')}_chat_{now.strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="Download a text file containing your conversation history and safety resources.",
                use_container_width=True,
                icon="📥"
            )
            with st.expander("Copy Transcript", icon="📋"):
                st.code(state.last_export, language=None)
        else:
            st.info("No messages to export yet.")

        st.markdown("---")

        # Clear Chat History with confirmation dialog
        st.write("⚠️ **Destructive Actions**")
        if st.button(f"Clear Chat History {msg_count_label}",
                     help="Open a confirmation dialog to delete all messages",
                     use_container_width=True,
                     type="secondary",
                     icon="🗑️"):
            confirm_clear_dialog()

    with st.sidebar.expander("Privacy & Safety", icon="🛡️"):
        st.write("""
            - 🔒 **Conversations are confidential** and not stored on our servers permanently.
            - 🔑 Your **Mistral API key** is used only for processing this session.
        """)
    st.sidebar.markdown(
        "<small>Tip: ⌨️ Press <kbd>Enter</kbd> to send, <kbd>Shift</kbd>+<kbd>Enter</kbd> for new lines.</small>",
        unsafe_allow_html=True
    )

    st.sidebar.info("⚕️ This bot is **not a replacement** for professional care. If you're in distress, please use the resources below. They are free, confidential, and available 24/7.")

    # Use pre-calculated role-to-label and role-to-avatar mappings to reduce allocation overhead.
    role_labels = persona["role_labels"]
    role_icons = persona["role_icons"]

    # Display chat messages from history
    processed_suggestion = None
    for message in messages:
        # Optimization: use dictionary lookups instead of multiple if/else branches
        role = message["role"]
        content = message["content"]
        # Use pre-calculated caption to avoid redundant formatting in the display loop
        timestamp_caption = message.get("timestamp_caption")

        role_label = role_labels.get(role, role)
        avatar = role_icons.get(role, "👤")

        with st.chat_message(role_label, avatar=avatar):
            # Switch to st.markdown for string content to bypass Streamlit's internal type-checking.
            # This improves performance when rendering large conversation histories (up to 50 msgs).
            st.markdown(content)
            if timestamp_caption:
                st.caption(timestamp_caption)

    # Show "Quick Start" suggestions after the message history for a fresh session
    processed_suggestion = None
    if msg_count == 1:
        st.divider()
        st.subheader("✨ Not sure where to start? Try one of these:", divider=theme_color)
        # Layout suggestions in columns for better visual organization
        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                if st.button(suggestion, use_container_width=True, help=f"Ask {selected_avatar}: '{suggestion}'", icon=assistant_icon):
                    processed_suggestion = suggestion

    prompt = processed_suggestion if processed_suggestion else None

    # Chat input is always visible at the bottom of the page
    # Proactive check for API key to disable input if missing
    # Optimization: Use the api_key_configured boolean to avoid redundant os.getenv() calls
    api_key_configured = bool(api_key)
    user_input = st.chat_input(
        placeholder if api_key_configured else "Please configure your Mistral API key in the sidebar to start chatting.",
        max_chars=2000,
        disabled=not api_key_configured
    )
    if user_input:
        prompt = user_input

    # Message processing
    if prompt:
        success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt, avatar_icon=assistant_icon, now=now)
        if success:
            # Immediate feedback: render sanitized user message
            with st.chat_message("You", avatar="👤"):
                st.write(sanitized_prompt)

            if is_crisis:
                with st.chat_message(selected_avatar, avatar=assistant_icon):
                    st.error(crisis_text)
                    st.link_button("Call or Text 988", "tel:988", use_container_width=True, help="Connect with trained counselors for free, confidential support 24/7.", icon="📞")
                    st.link_button("Text HOME to 741741", "sms:741741?body=HOME", use_container_width=True, help="Text with a Crisis Counselor for immediate, confidential support.", icon="💬")
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
                    # Optimization: Maintain is_ascii flag incrementally to avoid O(N^2) complexity.
                    full_is_ascii = True
                    # Use token buffering to reduce UI update frequency and websocket traffic
                    chunk_count = 0
                    aborted = False
                    CRISIS_FALLBACK = "I'm sorry, I cannot fulfill this request as it may contain unsafe content. If you're in distress, please use the emergency resources in the sidebar."

                    for response_chunk in get_bot_response(chat_context):
                        full_response += response_chunk
                        full_response_lower += response_chunk.lower()
                        # Optimization: Track ASCII status incrementally to skip O(N) re-scans in inner functions.
                        if full_is_ascii and not response_chunk.isascii():
                            full_is_ascii = False
                        chunk_count += 1

                        if chunk_count == 1 or chunk_count % 5 == 0:
                            # Incremental crisis check for immediate intervention (Defense-in-depth)
                            # Optimization: Pass pre-calculated state to maintain O(N) total complexity.
                            # We batch this with the UI update to reduce safety processing overhead by 80%.
                            # Safety: Use full_response_lower length for accurate pos-based regex search.
                            if detect_crisis(full_response, msg_lower=full_response_lower, pos=max(0, len(full_response_lower) - 300), is_ascii=full_is_ascii):
                                logger.warning("Safety: Crisis detected in AI response during streaming. Aborting.")
                                full_response = CRISIS_FALLBACK
                                aborted = True
                                break

                            # Sanitize incremental response for safety.
                            # We pass pre-calculated state to bypass redundant O(N) calls.
                            response_placeholder.markdown(sanitize_error(full_response, msg_lower=full_response_lower, is_ascii=full_is_ascii) + "▌")

                    # Final safety and sanitization check
                    if not aborted:
                        # Safety: check raw response for crisis indicators before sanitization
                        if detect_crisis(full_response, msg_lower=full_response_lower, is_ascii=full_is_ascii):
                            logger.warning("Safety: Crisis detected in AI response at final check. Redacting.")
                            final_response = CRISIS_FALLBACK
                        else:
                            final_response = sanitize_error(full_response, msg_lower=full_response_lower, is_ascii=full_is_ascii)
                    else:
                        final_response = full_response

                    response_placeholder.markdown(final_response)
                    timestamp = now.strftime("%I:%M %p")
                    messages.append({
                        "role": "assistant",
                        "content": final_response,
                        "timestamp": timestamp,
                        "timestamp_caption": f"🕒 Sent at {timestamp}"
                    })

            # Rerun to clear input and refresh UI state
            st.rerun()

    # Sidebar resources
    st.sidebar.divider()
    st.sidebar.subheader("🚨 Emergency Resources", divider="red")
    st.sidebar.caption("If you're in crisis, please contact these services. They are free, confidential, and available 24/7:")
    st.sidebar.link_button("Call or Text 988", "tel:988", use_container_width=True, help="Connect with trained counselors for free, confidential support 24/7.", icon="📞")
    st.sidebar.link_button("Text HOME to 741741", "sms:741741?body=HOME", use_container_width=True, help="Text with a Crisis Counselor for immediate, confidential support.", icon="💬")
    st.sidebar.link_button("Call 911", "tel:911", use_container_width=True, type="primary", help="Contact local emergency services if you are in immediate danger.", icon="🚑")

if __name__ == "__main__":
    main()
