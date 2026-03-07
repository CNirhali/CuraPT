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

    # Negative cases
    assert detect_crisis("I'm feeling much better today") == False
    assert detect_crisis("I'm just tired") == False
    assert detect_crisis("I'm feeling a bit sad today") == False
    assert detect_crisis("How can I improve my productivity?") == False
    assert detect_crisis("I'm happy with my progress") == False

def test_get_crisis_response():
    # Verify the presence of actionable links
    response = get_crisis_response()
    assert "[988](tel:988)" in response
    assert "[Text HOME to 741741](sms:741741)" in response
    assert "[911](tel:911)" in response

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
    assert "I apologize" in response_content

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
    success, is_crisis, crisis_text = handle_user_input(prompt)

    assert success == True
    assert is_crisis == False
    assert crisis_text is None

    assert len(st.session_state["messages"]) == 1
    msg = st.session_state["messages"][0]
    assert isinstance(msg, ChatMessage)
    assert msg.role == "user"
    assert msg.content == prompt

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
    success, is_crisis, crisis_text = handle_user_input(prompt)

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
