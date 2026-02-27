import pytest
from app import detect_crisis, get_bot_response
from mistralai.models.chat_completion import ChatMessage

def test_detect_crisis_positive():
    assert detect_crisis("I want to kill myself") is True
    assert detect_crisis("I feel like I want to end it all") is True
    assert detect_crisis("maybe i should hurt myself") is True

def test_detect_crisis_negative():
    assert detect_crisis("I am feeling a bit sad today") is False
    assert detect_crisis("How can I improve my productivity?") is False
    assert detect_crisis("I love my life") is False

def test_get_bot_response_success(mocker):
    # Mock MistralClient
    mock_client = mocker.patch("app.client")
    mock_response = mocker.Mock()
    mock_response.choices = [mocker.Mock(message=mocker.Mock(content="Hello! How can I help you?"))]
    mock_client.chat.return_value = mock_response

    messages = [ChatMessage(role="user", content="Hello")]
    response = get_bot_response(messages, "Therapist")

    assert response == "Hello! How can I help you?"

def test_get_bot_response_error_masking(mocker):
    # Mock MistralClient to raise an exception
    mock_client = mocker.patch("app.client")
    mock_client.chat.side_effect = Exception("Sensitive API Error: sk-123456789")

    messages = [ChatMessage(role="user", content="Hello")]
    response = get_bot_response(messages, "Therapist")

    # Ensure the sensitive error message is NOT leaked
    assert "Sensitive API Error" not in response
    assert "sk-123456789" not in response
    assert response == "I apologize, but I'm having trouble connecting right now. Please try again later."
