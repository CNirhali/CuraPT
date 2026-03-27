## 2025-05-15 - [Persona-Based Immersion & Streaming Responsiveness]
**Learning:** Dynamic visual cues (like theme-colored subheader dividers) and immediate streaming feedback (first-token UI updates) significantly enhance the sense of presence and responsiveness in persona-based AI applications. Truncating UI boilerplate from 'thinking' states allows the user to focus on the assistant's persona-specific icon.
**Action:** Use persona metadata to drive UI theme elements and ensure streaming loops update on `chunk_count == 1` to reduce perceived latency.

## 2025-05-16 - [Persona-Specific Greetings & Direct Dialogue]
**Learning:** Tailoring the initial greeting to match the persona's voice (e.g., professional for Therapist vs. enthusiastic for Life Coach) establishes immediate rapport and clarifies the assistant's role. Changing generic 'user' labels to 'You' makes the chat interface feel more personal and engaging. Proactive configuration feedback (like API key warnings) reduces user frustration during setup.
**Action:** Include persona-specific greeting fields in configuration dictionaries and prioritize 'You/I' dialogue labels for chat interfaces. Implement visible configuration status checks in sidebars to aid onboarding.
