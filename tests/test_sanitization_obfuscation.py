from app import sanitize_error

def test_sanitization_obfuscation():
    # Test multiline secret with 'key'
    msg1 = "My key\n: value123"
    sanitized1 = sanitize_error(msg1)
    assert "[REDACTED]" in sanitized1, f"Failed multiline key: {repr(sanitized1)}"

    # Test multiline secret with 'password'
    msg2 = "The password\n= secret123"
    sanitized2 = sanitized2 = sanitize_error(msg2)
    assert "[REDACTED]" in sanitized2, f"Failed multiline password: {repr(sanitized2)}"

    # Test multiline secret with 'token'
    msg3 = "token\nis\nmytoken"
    sanitized3 = sanitize_error(msg3)
    assert "[REDACTED]" in sanitized3, f"Failed multiline token: {repr(sanitized3)}"

    # Test that normal 'key' still works
    msg4 = "key: value"
    sanitized4 = sanitize_error(msg4)
    assert "[REDACTED]" in sanitized4, f"Failed normal key: {repr(sanitized4)}"
