## 2025-05-15 - [Persona-Based Immersion & Streaming Responsiveness]
**Learning:** Dynamic visual cues (like theme-colored subheader dividers) and immediate streaming feedback (first-token UI updates) significantly enhance the sense of presence and responsiveness in persona-based AI applications. Truncating UI boilerplate from 'thinking' states allows the user to focus on the assistant's persona-specific icon.
**Action:** Use persona metadata to drive UI theme elements and ensure streaming loops update on `chunk_count == 1` to reduce perceived latency.
