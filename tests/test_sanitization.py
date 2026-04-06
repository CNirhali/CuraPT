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

    def test_sanitize_error_quoted_password(self):
        msg = 'connection failed with password: "my secret pass"'
        sanitized = sanitize_error(msg)
        self.assertIn("password: [REDACTED]", sanitized)
        self.assertNotIn("my secret pass", sanitized)

    def test_sanitize_error_generic_token(self):
        msg = "api_key: some_long_token_string"
        sanitized = sanitize_error(msg)
        self.assertIn("api_key: [REDACTED]", sanitized)
        self.assertNotIn("some_long_token_string", sanitized)

    def test_sanitize_error_complex_separator(self):
        msg = "API_KEY  =  'hidden_value'"
        sanitized = sanitize_error(msg)
        self.assertIn("API_KEY  =  [REDACTED]", sanitized)
        self.assertNotIn("hidden_value", sanitized)

    def test_sanitize_error_bearer_token(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        sanitized = sanitize_error(msg)
        # Note: Bearer [REDACTED_JWT] is more specific than Bearer [REDACTED]
        self.assertIn("Bearer [REDACTED_JWT]", sanitized)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIs", sanitized)

    def test_sanitize_error_pii_credit_card(self):
        msg = "My card number is 4111 1111 1111 1111"
        sanitized = sanitize_error(msg)
        self.assertIn("[REDACTED_PII]", sanitized)
        self.assertNotIn("4111", sanitized)

    def test_sanitize_error_pii_amex(self):
        msg = "My amex is 3782-822463-10005"
        sanitized = sanitize_error(msg)
        self.assertIn("[REDACTED_PII]", sanitized)
        self.assertNotIn("3782", sanitized)

    def test_sanitize_error_masks_api_key_with_hyphens_and_underscores(self):
        # Test Anthropic style, OpenAI project keys, and keys with underscores
        test_keys = [
            "sk-ant-api03-1234567890abcdef1234567890abcdef",
            "sk-proj-1234567890_abcdef1234567890abcdef",
            "sk-secret_key-12345"
        ]
        for key in test_keys:
            sensitive_msg = f"Error with key {key}"
            sanitized = sanitize_error(sensitive_msg)
            self.assertIn("[REDACTED_API_KEY]", sanitized)
            self.assertNotIn(key, sanitized)

    def test_sanitize_error_quoted_json_identifiers(self):
        # Regression tests for quoted keys and passwords (e.g., in JSON or structured logs)
        test_cases = [
            ('{"key": "secret"}', '{"key": [REDACTED]}'),
            ('{"password": "abc"}', '{"password": [REDACTED]}'),
            ("'token': 'xyz'", "'token': [REDACTED]"),
            ('password="123"', 'password=[REDACTED]'),
            ('"secret" : "my-hidden-val"', '"secret" : [REDACTED]')
        ]
        for input_str, expected in test_cases:
            result = sanitize_error(input_str)
            self.assertEqual(result, expected, f"Failed for input: {input_str}")

    def test_sanitize_error_homoglyph_bypass(self):
        # 'а' is Cyrillic homoglyph for 'a', 'е' is Cyrillic homoglyph for 'e'
        # 'і' is Cyrillic homoglyph for 'i', 'о' is Cyrillic homoglyph for 'o'
        test_cases = [
            ("My pаssword: hidden123", "My password: [REDACTED]"),
            ("The sеcrеt is 'my-val'", "The secret is [REDACTED]"),
            ("apі_kеy: token123", "api_key: [REDACTED]"),
            ("My kеy is sk-12345", "My key is [REDACTED_API_KEY]"),
            ("My РАSSWORD: hidden123", "My PASSWORD: [REDACTED]"), # Mixed-case Cyrillic
            ("My ѕесrеt is val", "My secret is [REDACTED]"),      # 'ѕ' is Dze
        ]
        for input_str, expected in test_cases:
            result = sanitize_error(input_str)
            self.assertEqual(result, expected, f"Failed for homoglyph input: {input_str}")

    def test_sanitize_error_basic_auth(self):
        msg = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        sanitized = sanitize_error(msg)
        self.assertIn("Basic [REDACTED]", sanitized)
        self.assertNotIn("dXNlcjpwYXNzd29yZA==", sanitized)

    def test_sanitize_error_new_keywords(self):
        test_cases = [
            ("api-key: secret123", "api-key: [REDACTED]"),
            ("client_secret: hidden", "client_secret: [REDACTED]"),
            ("x-api-key: value", "x-api-key: [REDACTED]")
        ]
        for input_str, expected in test_cases:
            result = sanitize_error(input_str)
            self.assertEqual(result, expected, f"Failed for keyword: {input_str}")

    def test_sanitize_error_invisible_chars_bypass(self):
        # Soft hyphen (\u00AD) and Zero Width Space (\u200B)
        msg = "p\u00ADa\u200Bssword: hidden123"
        sanitized = sanitize_error(msg)
        self.assertEqual(sanitized, "password: [REDACTED]")

if __name__ == '__main__':
    unittest.main()
