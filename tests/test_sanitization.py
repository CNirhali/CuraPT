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

if __name__ == '__main__':
    unittest.main()
