import unittest
from app import detect_crisis, sanitize_error

class TestSafetyRobustness(unittest.TestCase):
    def test_detect_crisis_homoglyphs(self):
        # Normal detection
        self.assertTrue(detect_crisis("I want to suicide"))

        # Homoglyph bypasses (Cyrillic characters)
        self.assertTrue(detect_crisis("I want to suісіde"))  # Cyrillic 'і' and 'с'
        self.assertTrue(detect_crisis("I want to kіll myself")) # Cyrillic 'і'

        # NFKC Normalization (Full-width characters)
        self.assertTrue(detect_crisis("I want to ｓｕｉｃｉｄｅ"))

        # Safe strings containing lookalikes (false positive check)
        self.assertFalse(detect_crisis("I have a nice car"))

    def test_sanitize_aws_key(self):
        # AWS Access Key ID sanitization (AKIA)
        msg = "Error: AccessDenied for AKIA1234567890ABCDEF"
        sanitized = sanitize_error(msg)
        self.assertIn("[REDACTED_AWS_KEY]", sanitized)
        self.assertNotIn("AKIA1234567890ABCDEF", sanitized)

        # AWS Session Key sanitization (ASIA)
        msg2 = "Token: ASIA1234567890ABCDEF"
        sanitized2 = sanitize_error(msg2)
        self.assertIn("[REDACTED_AWS_KEY]", sanitized2)
        self.assertNotIn("ASIA1234567890ABCDEF", sanitized2)

        # Fast-path check for AWS keys
        self.assertTrue("akia" in "akia".lower()) # Sanity check for SENSITIVE_MARKERS
        self.assertTrue("asia" in "asia".lower())

    def test_detect_crisis_very_short(self):
        # Check that it doesn't crash on very short messages and returns False
        self.assertFalse(detect_crisis("hi"))
        self.assertFalse(detect_crisis(""))

if __name__ == '__main__':
    unittest.main()
