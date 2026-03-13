import unittest
from app import sanitize_error

class TestSanitizeError(unittest.TestCase):
    def test_sanitize_error_masks_api_key(self):
        sensitive_msg = "Error connecting with key sk-1234567890abcdef1234567890abcdef"
        sanitized = sanitize_error(sensitive_msg)
        self.assertIn("[REDACTED_API_KEY]", sanitized)
        self.assertNotIn("sk-1234567890abcdef1234567890abcdef", sanitized)

    def test_sanitize_error_handles_non_string(self):
        self.assertEqual(sanitize_error(123), "123")

    def test_sanitize_error_no_key(self):
        msg = "Generic connection error"
        self.assertEqual(sanitize_error(msg), msg)

    def test_sanitize_error_word_boundary(self):
        msg = "The risk-based assessment was completed."
        self.assertEqual(sanitize_error(msg), msg)

    def test_sanitize_error_generic_password(self):
        msg = "connection failed with password=my_secret_pass"
        sanitized = sanitize_error(msg)
        self.assertIn("password=[REDACTED]", sanitized)
        self.assertNotIn("my_secret_pass", sanitized)

    def test_sanitize_error_generic_token(self):
        msg = "api_key: some_long_token_string"
        sanitized = sanitize_error(msg)
        self.assertIn("api_key=[REDACTED]", sanitized)
        self.assertNotIn("some_long_token_string", sanitized)

    def test_sanitize_error_bearer_token(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        sanitized = sanitize_error(msg)
        self.assertIn("Bearer [REDACTED]", sanitized)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIs", sanitized)

if __name__ == '__main__':
    unittest.main()
