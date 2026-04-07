from app import detect_crisis

def test_multiline_crisis_detection():
    # Test with newline
    assert detect_crisis("I want to kill\nmyself") == True
    # Test with multiple spaces
    assert detect_crisis("I want to kill  myself") == True
    # Test with tabs
    assert detect_crisis("I want to kill\tmyself") == True
