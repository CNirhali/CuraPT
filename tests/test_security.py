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
        self.assertIn("I apologize", response)

        # Assert that the detailed error is NOT in the response
        self.assertNotIn("password=123", response)
        self.assertNotIn("Exception", response)

if __name__ == '__main__':
    unittest.main()
