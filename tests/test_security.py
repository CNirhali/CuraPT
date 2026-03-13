import unittest
from unittest.mock import MagicMock, patch
from app import get_bot_response

class TestSecurity(unittest.TestCase):
    @patch('app.get_mistral_client')
    def test_get_bot_response_masks_errors(self, mock_get_client):
        # Set up the mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Set up the mock chat_stream to raise an exception
        mock_client.chat_stream.side_effect = Exception("Detailed internal database error connection string with password=123")

        # Call the function
        messages = [{"role": "user", "content": "Hello"}]
        response_gen = get_bot_response(messages)
        response = "".join(list(response_gen))

        # Assert that the response is a generic error message
        self.assertIn("I'm here for you", response)

        # Assert that the detailed error is NOT in the response
        self.assertNotIn("password=123", response)
        self.assertNotIn("Exception", response)

    def test_user_input_sanitization_before_provider(self):
        # This test ensures that handle_user_input redacts secrets before they reach the rest of the system
        import streamlit as st
        from app import handle_user_input
        from mistralai.models.chat_completion import ChatMessage

        # Mock streamlit session state
        class MockState:
            def __init__(self):
                self.messages = []
                self.last_message_time = 0
            def get(self, k, d):
                return getattr(self, k, d)
            def __getitem__(self, k):
                return getattr(self, k)

        mock_state = MockState()
        with patch.object(st, 'session_state', mock_state):
            secret_key = "sk-abcdef1234567890abcdef1234567890"
            prompt = f"Please use this key: {secret_key}"

            success, is_crisis, crisis_text, sanitized_prompt = handle_user_input(prompt)

            self.assertTrue(success)
            # Support both specific and generic redaction labels
            self.assertTrue("[REDACTED" in sanitized_prompt)
            self.assertNotIn(secret_key, sanitized_prompt)

            # Check that the sanitized version is what's stored in history
            self.assertEqual(len(mock_state.messages), 1)
            self.assertTrue("[REDACTED" in mock_state.messages[0].content)
            self.assertNotIn(secret_key, mock_state.messages[0].content)

if __name__ == '__main__':
    unittest.main()
