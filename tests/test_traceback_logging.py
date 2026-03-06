import logging
import io
import unittest
from app import SanitizedFormatter

class TestTracebackLogging(unittest.TestCase):
    def test_traceback_sanitization(self):
        # Setup a logger with SanitizedFormatter
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(SanitizedFormatter('%(message)s'))

        logger = logging.getLogger('test_traceback')
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.ERROR)

        api_key = "sk-secret123"
        try:
            # Trigger an exception that includes the secret in its message
            raise ValueError(f"Secret leaked here: {api_key}")
        except Exception:
            # Log with exc_info=True to include the traceback
            logger.error("An error occurred", exc_info=True)

        log_output = log_stream.getvalue()

        # Verify that the secret is redacted in the entire log output
        self.assertNotIn(api_key, log_output)
        self.assertIn("[REDACTED_API_KEY]", log_output)
        # Also ensure the generic message is there
        self.assertIn("An error occurred", log_output)
        # And parts of the traceback (to confirm it was actually logged)
        self.assertIn("Traceback", log_output)
        self.assertIn("ValueError", log_output)

if __name__ == '__main__':
    unittest.main()
