## 2025-05-15 - [Persona-Based Immersion & Streaming Responsiveness]
**Learning:** Dynamic visual cues (like theme-colored subheader dividers) and immediate streaming feedback (first-token UI updates) significantly enhance the sense of presence and responsiveness in persona-based AI applications. Truncating UI boilerplate from 'thinking' states allows the user to focus on the assistant's persona-specific icon.
**Action:** Use persona metadata to drive UI theme elements and ensure streaming loops update on `chunk_count == 1` to reduce perceived latency.

## 2025-05-16 - [Persona-Specific Greetings & Direct Dialogue]
**Learning:** Tailoring the initial greeting to match the persona's voice (e.g., professional for Therapist vs. enthusiastic for Life Coach) establishes immediate rapport and clarifies the assistant's role. Changing generic 'user' labels to 'You' makes the chat interface feel more personal and engaging. Proactive configuration feedback (like API key warnings) reduces user frustration during setup.
**Action:** Include persona-specific greeting fields in configuration dictionaries and prioritize 'You/I' dialogue labels for chat interfaces. Implement visible configuration status checks in sidebars to aid onboarding.

## 2025-05-17 - [Proactive Configuration Feedback & Temporal Context]
**Learning:** Disabling the chat input with a descriptive placeholder when the system is unconfigured (e.g., missing API key) prevents user frustration by providing clear, immediate guidance. Adding message timestamps (`st.caption`) significantly improves the professional feel and utility of the conversation by providing temporal context for the user's mental health journey.
**Action:** Always provide specific, actionable feedback for unconfigured app states and implement lightweight metadata support (like timestamps) in chat histories to enhance user engagement.
