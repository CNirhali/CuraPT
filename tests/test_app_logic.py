from app import detect_crisis, get_crisis_response

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
