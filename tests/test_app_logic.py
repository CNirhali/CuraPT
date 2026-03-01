import pytest
from app import detect_crisis, get_bot_response, get_crisis_response
from mistralai.models.chat_completion import ChatMessage

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
    assert detect_crisis("I want to kill myself") == True
    assert detect_crisis("I'm feeling much better today") == False
    assert detect_crisis("Life is not worth living, I want to die") == True
    assert detect_crisis("I'm just tired") == False

def test_get_crisis_response():
    response = get_crisis_response()
    assert "988" in response
    assert "741741" in response
    assert "911" in response

def test_get_bot_response_success(mocker):
    # Mock MistralClient
    mock_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.choices = [mocker.Mock(message=mocker.Mock(content="Hello! How can I help you?"))]
    mock_client.chat.return_value = mock_response

    mocker.patch("app.get_mistral_client", return_value=mock_client)

    messages = [ChatMessage(role="user", content="Hello")]
    response = get_bot_response(messages, "Therapist")

    assert response == "Hello! How can I help you?"

def test_get_bot_response_error_masking(mocker):
    # Mock MistralClient to raise an exception
    mock_client = mocker.Mock()
    mock_client.chat.side_effect = Exception("Sensitive API Error: sk-123456789")

    mocker.patch("app.get_mistral_client", return_value=mock_client)

    messages = [ChatMessage(role="user", content="Hello")]
    response = get_bot_response(messages, "Therapist")

    # Ensure the sensitive error message is NOT leaked
    assert "Sensitive API Error" not in response
    assert "sk-123456789" not in response
    assert response == "I apologize, but I'm having trouble connecting right now. Please try again later."
