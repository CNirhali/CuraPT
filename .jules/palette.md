## 2025-05-15 - [Persona-Based Immersion & Streaming Responsiveness]
**Learning:** Dynamic visual cues (like theme-colored subheader dividers) and immediate streaming feedback (first-token UI updates) significantly enhance the sense of presence and responsiveness in persona-based AI applications. Truncating UI boilerplate from 'thinking' states allows the user to focus on the assistant's persona-specific icon.
**Action:** Use persona metadata to drive UI theme elements and ensure streaming loops update on `chunk_count == 1` to reduce perceived latency.

## 2025-05-16 - [Persona-Specific Greetings & Direct Dialogue]
**Learning:** Tailoring the initial greeting to match the persona's voice (e.g., professional for Therapist vs. enthusiastic for Life Coach) establishes immediate rapport and clarifies the assistant's role. Changing generic 'user' labels to 'You' makes the chat interface feel more personal and engaging. Proactive configuration feedback (like API key warnings) reduces user frustration during setup.
**Action:** Include persona-specific greeting fields in configuration dictionaries and prioritize 'You/I' dialogue labels for chat interfaces. Implement visible configuration status checks in sidebars to aid onboarding.

## 2025-05-17 - [Proactive Configuration Feedback & Temporal Context]
**Learning:** Disabling the chat input with a descriptive placeholder when the system is unconfigured (e.g., missing API key) prevents user frustration by providing clear, immediate guidance. Adding message timestamps (`st.caption`) significantly improves the professional feel and utility of the conversation by providing temporal context for the user's mental health journey.
**Action:** Always provide specific, actionable feedback for unconfigured app states and implement lightweight metadata support (like timestamps) in chat histories to enhance user engagement.

## 2025-05-18 - [Semantic Hierarchy & Utility-Driven Portability]
**Learning:** For persistent sidebar sections like 'Emergency Resources', `st.sidebar.subheader` is preferred over `st.sidebar.error` to provide a correct semantic heading level for accessibility while maintaining visual clarity. Leveraging built-in component features, such as the 'Copy to Clipboard' button in `st.code`, provides a frictionless way to add utility (like transcript copying) without custom UI development.
**Action:** Use subheaders for structural navigation and capitalize on built-in component utilities to enhance user productivity with minimal code overhead.

## 2025-05-19 - [Dialog-Based Destructive Action Confirmation]
**Learning:** Replacing inline confirmation mechanisms (like checkboxes) with modal dialogs (@st.dialog) for destructive actions (e.g., clearing chat history) creates a more intentional and focused user experience. It reduces UI clutter in secondary menus and provides a clear, isolated context for the user to confirm their decision.
**Action:** Use @st.dialog for irreversible or significant destructive operations to ensure user intentionality and maintain a clean primary interface.

## 2025-05-20 - [Enhanced Session Metadata & Temporal Awareness]
**Learning:** Providing real-time session metadata (like "minutes active") and using human-centric pluralization in UI labels (e.g., "1 message" vs "2 messages") increases user perceived value and provides helpful temporal context. Synchronizing time formats across different UI sections (chat bubbles vs sidebar) reduces cognitive load and creates a more cohesive experience.
**Action:** Always implement proper pluralization for count-based labels and ensure temporal metadata (timestamps, durations) are formatted consistently with the primary content area.

## 2025-05-21 - [Frictionless Crisis Intervention & Visual Affordance]
**Learning:** In high-stress or crisis scenarios, every extra step (like typing 'HOME' to a shortcode) is a barrier. Pre-filling SMS bodies using URI parameters (`sms:number?body=text`) significantly improves accessibility for users in distress. Additionally, using standard icons for suggestion chips and destructive confirmations provides immediate visual affordance, making the interface more intuitive.
**Action:** Always use pre-filled message bodies for SMS-based utility links and leverage Streamlit's `icon` parameter for better visual cues on interactive elements.
