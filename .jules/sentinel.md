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

## 2026-03-01 - [Resource Exhaustion Protection and Safety Unified]
**Vulnerability:** Unbounded session state (message history) and unrestricted bot response length could lead to memory exhaustion and resource-based DoS. Additionally, inconsistent safety checks between chat input and suggestion buttons created a safety bypass.
**Fix:** Implemented centralized `handle_user_input` with rate limiting (2s) and message history capping (50 messages). Added `MAX_RESPONSE_CHARS` limit to `get_bot_response`. Unified all input entry points to use the safety wrapper.
**Impact:** Protects against DoS attacks targeting server memory and API tokens, while ensuring all user interactions are screened for safety.

## 2026-03-01 - [Sensitive Data Leakage in Server Logs]
**Vulnerability:** Potential leakage of API keys and other sensitive credentials into server-side logs during error handling.
**Learning:** Even when errors are masked from the frontend, logging the raw exception message can inadvertently store secrets in persistent log files. Furthermore, Python's `exc_info=True` appends tracebacks which bypass manual sanitization of the error message string.
**Prevention:** Implement a custom `logging.Formatter` (e.g., `SanitizedFormatter`) that redacts sensitive patterns from the *entire* formatted log record, including tracebacks. Apply this formatter to all root handlers for defense-in-depth.

## 2026-03-02 - [User-Side Secret Redaction and Regex Precision]
**Vulnerability:** Accidental leakage of secrets (API keys) by the user into chat history, provider requests, and logs.
**Learning:** Redacting secrets only on the server-side output is insufficient; user input must be sanitized at the ingestion point to prevent secrets from ever reaching the LLM provider or being stored in session state. Additionally, simple regex patterns for keys (like `sk-[a-zA-Z0-9]+`) can cause false positives in normal text (e.g., "risk-based").
**Prevention:** Sanitize user input immediately in the processing pipeline (e.g., `handle_user_input`) and use word boundaries (`\b`) in redaction regexes to ensure only full tokens matching the secret pattern are masked.

## 2026-03-03 - [Vulnerable Dependencies in requirements.txt]
**Vulnerability:** Several project dependencies were pinned to versions with known critical and high-severity vulnerabilities (e.g., Streamlit 1.28.2 vulnerable to XSS, Pillow 10.1.0 vulnerable to Arbitrary Code Execution).
**Learning:** Even with robust internal security logic, the application remains vulnerable if the underlying platform and libraries are insecure. Regular automated dependency auditing is essential.
**Prevention:** Pin dependencies to secure versions and use tools like `pip-audit` to identify and resolve vulnerabilities in third-party packages.
