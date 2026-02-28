## 2025-05-15 - [Security Enhancement] Error Masking and Input Validation

**Vulnerability:** Information Leakage and potential Denial of Service (DoS).
**Learning:** Returning raw exception strings directly to the frontend can expose sensitive internal state, such as API keys or stack traces. Additionally, unrestricted input length can lead to resource exhaustion.
**Prevention:** Always catch exceptions at the edge and return generic, user-friendly messages while logging the detailed error server-side. Use `max_chars` on Streamlit `chat_input` to limit input size.
## 2026-02-28 - [Information Leakage in Error Messages]
**Vulnerability:** Displaying detailed exception messages and stack traces in the UI can expose sensitive information about the application's environment, dependencies, and internal logic.
**Fix:** Implement a robust error handling pattern that logs the full exception details on the server while returning a generic, non-informative error message to the user.
**Impact:** Prevents attackers from gaining insights into the application's infrastructure and reduces the risk of further exploitation.

## 2026-02-28 - [Denial of Service via Resource Exhaustion]
**Vulnerability:** Allowing unlimited input length in chat interfaces can lead to resource exhaustion on the server and potentially incur high API costs or cause Denial of Service (DoS).
**Fix:** Enforce a reasonable maximum character limit on all user inputs (e.g., using `max_chars` in `st.chat_input`).
**Impact:** Ensures application stability and protects against malicious or accidental resource abuse.
