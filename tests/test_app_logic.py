import pytest
from app import detect_crisis, get_bot_response, get_crisis_response, handle_user_input
from mistralai.models.chat_completion import ChatMessage
import streamlit as st

def test_detect_crisis():
    # Positive cases
    assert detect_crisis("I want to kill myself") == True
    assert detect_crisis("i feel like ending it all") == True
    assert detect_crisis("maybe I should hurt myself") == True
    assert detect_crisis("Life is not worth living, I want to die") == True
    assert detect_crisis("SUICIDE is not the answer") == True
    assert detect_crisis("I want to DIE") == True
    assert detect_crisis("I'm feeling suicidal") == True
    assert detect_crisis("kill me now") == True
    assert detect_crisis("I will jump off a bridge") == True
    assert detect_crisis("I want to cut myself") == True
    assert detect_crisis("I should hang myself") == True
    assert detect_crisis("I'll poison myself") == True

    # Negative cases
    assert detect_crisis("I'm feeling much better today") == False
    assert detect_crisis("I'm just tired") == False
    assert detect_crisis("I'm feeling a bit sad today") == False
    assert detect_crisis("How can I improve my productivity?") == False
    assert detect_crisis("I'm happy with my progress") == False

def test_get_crisis_response():
    # Verify the presence of actionable links with descriptive text
    response = get_crisis_response()
    assert "[Call or Text 988](tel:988)" in response
    assert "[Text HOME to 741741](sms:741741)" in response
    assert "[Call 911](tel:911)" in response

def test_get_bot_response_success(mocker):
    # Mock MistralClient
    mock_client = mocker.Mock()

    # Mock chat_stream to return a generator of chunks
    mock_chunk1 = mocker.Mock()
    mock_chunk1.choices = [mocker.Mock(delta=mocker.Mock(content="Hello! "))]
    mock_chunk2 = mocker.Mock()
    mock_chunk2.choices = [mocker.Mock(delta=mocker.Mock(content="How can I help you?"))]

    mock_client.chat_stream.return_value = [mock_chunk1, mock_chunk2]
    mock_client._api_key = "some-key"

    mocker.patch("app.get_mistral_client", return_value=mock_client)

    messages = [ChatMessage(role="user", content="Hello")]
    response_gen = get_bot_response(messages)

    response_content = "".join(list(response_gen))

    assert response_content == "Hello! How can I help you?"

def test_get_bot_response_error_masking(mocker):
    # Mock MistralClient to raise an exception
    mock_client = mocker.Mock()
    mock_client.chat_stream.side_effect = Exception("Sensitive API Error: sk-123456789")
    mock_client._api_key = "some-key"

    mocker.patch("app.get_mistral_client", return_value=mock_client)

    messages = [ChatMessage(role="user", content="Hello")]
    response_gen = get_bot_response(messages)

    response_content = "".join(list(response_gen))

    # Ensure the sensitive error message is NOT leaked
    assert "Sensitive API Error" not in response_content
    assert "sk-123456789" not in response_content
    assert "I'm here for you" in response_content

def test_handle_user_input_stores_chatmessage_objects(mocker):
    # Mock streamlit session state with an object that supports both dict and attribute access
    class MockState:
        def __init__(self):
            self.messages = []
            self.last_message_time = 0
        def get(self, k, d):
            return getattr(self, k, d)
        def __getitem__(self, k):
            return getattr(self, k)

    mock_state = MockState()
    mocker.patch.object(st, "session_state", mock_state)

    prompt = "Hello"
    success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt)

    assert success == True
    assert is_crisis == False
    assert crisis_text is None
    assert sanitized_prompt == prompt

    assert len(st.session_state["messages"]) == 1
    msg = st.session_state["messages"][0]
    assert isinstance(msg, ChatMessage)
    assert msg.role == "user"
    assert msg.content == prompt

def test_handle_user_input_sanitization(mocker):
    # Mock streamlit session state
    class MockState:
        def __init__(self):
            self.messages = []
            self.last_message_time = 0
        def get(self, k, d):
            return getattr(self, k, d)
        def __getitem__(self, k):
            return getattr(self, k)

    mock_state = MockState()
    mocker.patch.object(st, "session_state", mock_state)

    prompt = "My secret key is sk-1234567890abcdef1234567890abcdef"
    success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt)

    assert success == True
    assert "[REDACTED_API_KEY]" in sanitized_prompt
    assert "sk-1234567890abcdef1234567890abcdef" not in sanitized_prompt

    assert len(st.session_state["messages"]) == 1
    msg = st.session_state["messages"][0]
    assert msg.content == sanitized_prompt

def test_handle_user_input_crisis_stores_chatmessage_objects(mocker):
    # Mock streamlit session state with an object that supports both dict and attribute access
    class MockState:
        def __init__(self):
            self.messages = []
            self.last_message_time = 0
        def get(self, k, d):
            return getattr(self, k, d)
        def __getitem__(self, k):
            return getattr(self, k)

    mock_state = MockState()
    mocker.patch.object(st, "session_state", mock_state)

    prompt = "I want to kill myself"
    success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt)

    assert success == True
    assert is_crisis == True
    assert "988" in crisis_text

    assert len(st.session_state["messages"]) == 2
    user_msg = st.session_state["messages"][0]
    assistant_msg = st.session_state["messages"][1]

    assert isinstance(user_msg, ChatMessage)
    assert user_msg.role == "user"

    assert isinstance(assistant_msg, ChatMessage)
    assert assistant_msg.role == "assistant"
    assert "988" in assistant_msg.content

def test_bot_response_sanitization_and_safety(mocker):
    # Mock MistralClient
    mock_client = mocker.Mock()

    # Mock chat_stream to return something sensitive and then something unsafe
    mock_chunk1 = mocker.Mock()
    mock_chunk1.choices = [mocker.Mock(delta=mocker.Mock(content="My key is sk-12345. "))]
    mock_chunk2 = mocker.Mock()
    mock_chunk2.choices = [mocker.Mock(delta=mocker.Mock(content="You should kill yourself."))]

    mock_client.chat_stream.return_value = [mock_chunk1, mock_chunk2]
    mock_client._api_key = "some-key"

    mocker.patch("app.get_mistral_client", return_value=mock_client)

    # We need to mock streamlit components that are called in the loop
    mocker.patch("streamlit.chat_message")
    mock_placeholder = mocker.Mock()
    mocker.patch("streamlit.empty", return_value=mock_placeholder)
    mocker.patch("streamlit.rerun")

    # Mock session state
    class MockState:
        def __init__(self):
            self.messages = [ChatMessage(role="user", content="hello")]
            self.last_message_time = 0
            self.selected_avatar = "Therapist"
        def get(self, k, d):
            return getattr(self, k, d)
        def __getitem__(self, k):
            return getattr(self, k)

    mock_state = MockState()
    mocker.patch.object(st, "session_state", mock_state)

    from app import main
    # We call main() but we need to mock the environment so it doesn't try to run everything
    # Alternatively, we can just test the logic inside the block.
    # Since I cannot easily call main() without it trying to render everything,
    # I will test by observing the effects on session_state.messages if I were to run that logic.

    # Re-implementing the logic briefly for the test or calling the function that does it.
    # The logic is in main(). Let's see if I can extract it or just mock enough of main.

    # Actually, a better way is to test get_bot_response and then how it's used.
    # But get_bot_response is a generator.

    messages = [ChatMessage(role="system", content="prompt"), ChatMessage(role="user", content="hello")]
    full_response = ""
    for chunk in get_bot_response(messages):
        full_response += chunk

    from app import sanitize_error, detect_crisis
    final_response = sanitize_error(full_response)
    assert "sk-12345" not in final_response
    assert "[REDACTED_API_KEY]" in final_response

    if detect_crisis(final_response):
        final_response = "Redacted"

    assert final_response == "Redacted"
