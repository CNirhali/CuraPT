from app import detect_crisis

def test_detect_crisis_positive():
    assert detect_crisis("I want to kill myself") == True
    assert detect_crisis("i feel like ending it all") == True
    assert detect_crisis("maybe I should hurt myself") == True

def test_detect_crisis_negative():
    assert detect_crisis("I'm feeling a bit sad today") == False
    assert detect_crisis("How can I improve my productivity?") == False
    assert detect_crisis("I'm happy with my progress") == False

def test_detect_crisis_case_insensitivity():
    assert detect_crisis("SUICIDE is not the answer") == True
    assert detect_crisis("I want to DIE") == True
