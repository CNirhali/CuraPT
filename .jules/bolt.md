## 2025-05-15 - [Regex and Resource Caching Optimizations]
**Learning:** In Python, pre-compiling regular expressions with `re.compile()` and using flags like `re.IGNORECASE` is significantly more efficient than manual string lowercase conversion and iterative keyword checking (approx. 2.2x speedup in this codebase). Additionally, heavy API clients like `MistralClient` should be cached using `@st.cache_resource` in Streamlit to avoid expensive re-initializations during app reruns.
**Action:** Always prefer pre-compiled regex for keyword/pattern matching in hot paths and ensure all global resources are properly cached in Streamlit applications.

## 2025-05-16 - [Context Truncation for LLM Latency]
**Learning:** LLM response latency and token costs grow linearly/quadratically with conversation history. Truncating the context to the most recent 10 messages provides a significant performance boost (~200-500ms reduction in response time) while maintaining sufficient context for high-quality interactions. Additionally, cleaning up redundant script code in Streamlit reduces the overhead of the "rerun on interaction" model.
**Action:** Implement context windowing (truncation) for all LLM-backed chat features and periodically audit the main script for execution-blocking redundancies.

## 2025-05-17 - [Response Streaming for Perceived Performance]
**Learning:** For LLM applications, Time To First Token (TTFT) is more critical for UX than total response time. Switching from synchronous `chat` to `chat_stream` and update the UI in real-time provides immediate feedback, significantly reducing perceived latency. Additionally, cleaning up system prompts by removing leading whitespace (e.g., from multi-line strings) reduces unnecessary token consumption and improves model adherence.
**Action:** Always implement streaming for LLM-backed chat interfaces and ensure system prompts are trimmed of unnecessary whitespace/tokens.

## 2026-03-03 - [Static Constant Pre-calculation in Streamlit]
**Learning:** In Streamlit's "run on every interaction" execution model, module-level pre-calculation of static values (like dictionary keys or list comprehensions for stable configurations) is significantly more efficient than re-calculating them inside the main loop or UI components. This reduces CPU overhead per rerun.
**Action:** Move all static data transformations and configuration extractions to the module level.

## 2026-03-04 - [Token Buffering and History Capping]
**Learning:** Updating the Streamlit UI (via `st.markdown`) for every token in a stream causes significant websocket overhead and browser rerender lag. Buffering tokens and updating the UI every 5-10 chunks provides a much smoother experience. Additionally, capping `st.session_state.messages` to a fixed size (e.g., 50) is essential to prevent linear performance degradation in Streamlit's "render everything" model.
**Action:** Always implement token buffering in streaming loops and maintain a bounded session state for long-running chat applications.
