## 2025-05-15 - [Destructive Action Safety]
**Learning:** For a mental health support application, conversations are deeply personal and potentially significant. Deleting this history without a clear, multi-step confirmation (like a checkbox or a two-step button) is a significant UX regression that can cause distress.
**Action:** Always implement a confirmation step (e.g., `st.checkbox` to enable a delete button) for any destructive actions affecting user data.

## 2025-05-15 - [Safety Disclaimer Visibility]
**Learning:** Critical safety information, such as medical disclaimers, should not be hidden inside collapsed UI elements (like expanders or tabs). Visibility directly impacts accessibility and user safety.
**Action:** Place essential safety notices in persistent, prominent UI components (like `st.sidebar.info` or `st.sidebar.caption`) that are always visible to the user.

## 2025-05-15 - [Persona Contextualization]
**Learning:** In a multi-persona AI application, minor UI elements like chat input placeholders and status captions are high-leverage areas for reinforcing the selected persona's identity. Tailoring these small details significantly increases the perceived empathy and "presence" of the AI.
**Action:** Use dynamic mapping for transient UI text (placeholders, status labels) to ensure they always reflect the active persona's unique tone and purpose.

## 2025-05-15 - [Integrated Suggestion Affordances]
**Learning:** For initial chat interactions, placing suggestion buttons outside the assistant's context bubble creates a disjointed experience. Integrating suggestions directly into the assistant's greeting bubble improves visual hierarchy and clarifies the "rich message" nature of the AI's first communication.
**Action:** Render initial conversation starters within the same UI container as the greeting message, using subtle captions for instructional text.

## 2025-05-15 - [Action Context & Confirmation]
**Learning:** Providing dynamic metadata (like message counts) on management buttons gives users immediate clarity on the scale of their actions (exporting or deleting). This "informed consent" model reduces user anxiety when interacting with data management tools.
**Action:** Always include relevant quantity markers (e.g., item counts) on buttons that perform batch operations or data-heavy tasks.
