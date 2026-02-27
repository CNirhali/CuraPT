## 2025-05-15 - [Security Enhancement] Error Masking and Input Validation

**Vulnerability:** Information Leakage and potential Denial of Service (DoS).
**Learning:** Returning raw exception strings directly to the frontend can expose sensitive internal state, such as API keys or stack traces. Additionally, unrestricted input length can lead to resource exhaustion.
**Prevention:** Always catch exceptions at the edge and return generic, user-friendly messages while logging the detailed error server-side. Use `max_chars` on Streamlit `chat_input` to limit input size.
