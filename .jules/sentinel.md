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

## 2026-03-14 - [Regex Precision for Secret Redaction]
**Vulnerability:** Incomplete redaction of secrets when they are enclosed in quotes or use non-standard separators.
**Learning:** Simple key-value regex patterns (e.g., `key\s*[:=]\s*[^\s,;]+`) fail to catch secrets that contain spaces (if quoted) or preserve the original formatting, which can lead to information leakage or inconsistent UI/logs.
**Prevention:** Use capture groups to preserve original separators and handle multiple quoting styles (single and double quotes) in sanitization regexes to ensure robust secret masking across various input formats.

## 2026-03-16 - [Sanitization Bypass via Fast-Path Desynchronization]
**Vulnerability:** Incomplete redaction of AWS keys (AKIA/ASIA) despite existing regex patterns.
**Learning:** High-speed "guard" checks (like the `SENSITIVE_MARKERS` substring check) must be perfectly synchronized with the underlying regular expression suite. If a marker is missing from the fast-path list, the expensive but secure regex will never execute for that pattern, creating a silent security failure.
**Prevention:** Always maintain a one-to-one mapping between the sets of identifiers in fast-path optimizations and the security-critical patterns they protect.

## 2026-03-15 - [Safety Bypass via Homoglyph Obfuscation]
**Vulnerability:** Crisis detection filters using simple regex or keyword matching can be bypassed using homoglyphs (lookalike characters from different alphabets, e.g., Cyrillic 'і' for Latin 'i') or NFKC normalization forms.
**Learning:** Pure regex checks are insufficient for security-critical filters if attackers can use Unicode variety to hide malicious intent while maintaining visual similarity. NFKC normalization and manual homoglyph mapping are necessary pre-processing steps.
**Prevention:** Apply `unicodedata.normalize('NFKC')` and translate common lookalikes to their Latin equivalents before performing safety-critical pattern matching.

## 2026-03-15 - [Specificity Preservation in Redaction Pipelines]
**Vulnerability:** Generic redaction patterns (e.g., matching any "key: value" pair) can overwrite more specific redaction labels (e.g., `[REDACTED_AWS_KEY]`), leading to a loss of diagnostic context in logs or UI.
**Learning:** When multiple redaction regexes are applied in sequence, broader patterns can consume already-redacted strings if they aren't carefully constrained.
**Prevention:** Use negative lookaheads (e.g., `(?!\[REDACTED)`) in broader, generic redaction patterns to prevent them from matching and over-writing strings that have already been masked by more specific, higher-priority patterns.

## 2026-03-17 - [Redaction Pipeline Interference with Multi-line Blocks]
**Vulnerability:** Generic redaction patterns for single-line secrets (like `key: value`) can partially match and corrupt multi-line sensitive blocks (like PEM Private Keys) before they are fully redacted by specific patterns.
**Learning:** Redaction pipelines must be ordered from most specific to least specific. Additionally, generic patterns should use negative lookaheads to explicitly ignore start-of-block markers (e.g., `---`) for multi-line secrets to ensure the specific block-level redaction handles them completely.
**Prevention:** Ensure specific block-level redaction regexes are at the top of the pipeline and add `(?!---)` lookaheads to generic 'key' or 'secret' patterns.
## 2026-03-21 - PII Redaction Fast-Path Synchronization
**Vulnerability:** Potential leakage of Credit Card numbers (PII) in UI error messages or exported logs due to missing redaction patterns.
**Learning:** Adding complex regex patterns for PII (like Credit Cards) in a performance-optimized sanitization function requires explicit synchronization with the fast-path substring markers (`SENSITIVE_MARKERS`). Failing to add numeric prefixes (e.g., '3782' for Amex, '4111' for Visa) to the markers list causes the entire regex engine to be bypassed for messages containing these PII patterns but lacking other sensitive keywords.
**Prevention:** Always update the fast-path trigger list (`SENSITIVE_MARKERS`) when adding new high-priority redaction patterns to ensure the security logic is actually executed for those patterns.

## 2026-03-22 - [Partial Secret Redaction due to Hyphens and Underscores]
**Vulnerability:** API keys containing hyphens or underscores (e.g., Anthropic, OpenAI project keys) were only partially redacted, potentially leaking the remainder of the secret.
**Learning:** Generic alphanumeric regexes for secrets (like `sk-[a-zA-Z0-9]+`) fail on keys that incorporate hyphens or underscores as separators, leading to insecure partial masking.
**Prevention:** Ensure secret redaction regexes account for all possible character sets used by providers, including hyphens and underscores, and verify against a diverse set of real-world key formats.

## 2026-03-23 - [Safety Bypass via Secret Sanitization]
**Vulnerability:** Crisis detection filters can be bypassed if secret sanitization is performed first, as redaction markers can mask safety-critical keywords (e.g., "My secret is suicide" becomes "My secret is [REDACTED]").
**Learning:** Security and safety layers must be carefully ordered. Sanitization, which purposefully obscures data, should not precede filters that depend on the literal content of that data for threat detection.
**Prevention:** Always perform safety-critical checks (like crisis detection or content moderation) on the raw, unsanitized text before applying any redaction or transformation layers.

## 2026-03-29 - [Enhanced Defense-in-Depth for Modern Secret Formats]
**Vulnerability:** Potential leakage of modern and high-entropy secrets (GitHub Fine-grained PATs, Stripe Restricted Keys, Google OAuth Secrets, and standalone JWTs) in logs or UI.
**Learning:** Generic secret patterns (like `sk-...` or `key: ...`) are insufficient for modern token formats that use specific prefixes (e.g., `github_pat_`, `rk_`, `GOCSPX-`) or have recognizable structures (like JWT's `eyJ...`). Furthermore, specific patterns like JWT must be prioritized in the redaction pipeline to ensure precise labeling (e.g., `[REDACTED_JWT]`) before broader patterns (like `Bearer [REDACTED]`) consume them.
**Prevention:** Maintain a specialized and prioritized list of regex patterns for all known high-risk token formats used by the application and its dependencies. Always synchronize the performance fast-path (`SENSITIVE_MARKERS`) with these new patterns.

## 2026-03-30 - [Sanitization Bypass via Quoted Identifiers]
**Vulnerability:** Information leakage in structured logs or JSON data where sensitive keys (e.g., `"password"`, `"key"`) were not redacted because they were enclosed in quotes.
**Learning:** Generic secret redaction patterns must account for structured data formats where identifiers are frequently quoted. Simple word-boundary checks (`\bkey\b`) might match the name but fail if the name is wrapped in delimiters like `"` or `'`. Using backreferences in regex allows for matching balanced quotes around an identifier. Additionally, performance guards must be explicitly updated to include these quoted variants to ensure the redaction logic is triggered.
**Prevention:** Use advanced regex patterns that support optional, balanced delimiters for all generic secret identifiers. Ensure that individual regex guards in the sanitization pipeline are also updated to trigger on these delimited variants.

## 2026-04-05 - [Homoglyph-based Redaction Bypass in sanitize_error]
**Vulnerability:** Redaction of secrets (API keys, passwords) could be bypassed by using homoglyphs (lookalike characters from different alphabets) in the surrounding keywords (e.g., "pаssword" using Cyrillic 'а').
**Learning:** Security filters that depend on specific keywords are vulnerable to Unicode obfuscation. Normalization must be applied to all security-critical string processing layers, not just safety filters like crisis detection.
**Prevention:** Apply canonical normalization (NFKC) and homoglyph mapping to all text before performing security-sensitive pattern matching or redaction. ensure a unified mapping is used across the codebase.
