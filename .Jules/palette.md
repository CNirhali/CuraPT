## 2025-05-15 - [Destructive Action Safety]
**Learning:** For a mental health support application, conversations are deeply personal and potentially significant. Deleting this history without a clear, multi-step confirmation (like a checkbox or a two-step button) is a significant UX regression that can cause distress.
**Action:** Always implement a confirmation step (e.g., `st.checkbox` to enable a delete button) for any destructive actions affecting user data.

## 2025-05-15 - [Safety Disclaimer Visibility]
**Learning:** Critical safety information, such as medical disclaimers, should not be hidden inside collapsed UI elements (like expanders or tabs). Visibility directly impacts accessibility and user safety.
**Action:** Place essential safety notices in persistent, prominent UI components (like `st.sidebar.info` or `st.sidebar.caption`) that are always visible to the user.

## 2025-05-15 - [Layout Stability & Persistence]
**Learning:** In Streamlit, widgets that are conditionally rendered (e.g., inside an `if not prompt:` block) will disappear from the UI during reruns when the condition is false, causing jarring layout shifts. This "flicker" breaks the user's flow and makes the interface feel unstable.
**Action:** Always render persistent interaction elements like `st.chat_input` outside of conditional logic. Capture their value and then use logic to determine which input (suggestion vs. text) to process.
