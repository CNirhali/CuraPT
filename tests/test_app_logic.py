from app import detect_crisis, get_crisis_response

def test_detect_crisis():
    assert detect_crisis("I want to kill myself") == True
    assert detect_crisis("I'm feeling much better today") == False
    assert detect_crisis("Life is not worth living, I want to die") == True
    assert detect_crisis("I'm just tired") == False

def test_get_crisis_response():
    response = get_crisis_response()
    assert "988" in response
    assert "741741" in response
    assert "911" in response
