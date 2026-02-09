"""Integration tests for LLM Intent Interpreter."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from caps.agent import IntentInterpreter


class TestIntentInterpreter:
    """Test IntentInterpreter with mocked Gemini API."""

    @patch('caps.agent.intent_interpreter.genai.Client')
    def test_interpret_payment_intent(self, mock_client_class):
        """Test interpretation of payment request."""
        # Mock the Gemini API response
        mock_response = Mock()
        mock_response.text = '{"intent_type": "PAYMENT", "amount": 50.0, "merchant_vpa": "canteen@vit", "confidence_score": 0.95}'
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Create interpreter with fake API key
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'fake-key'}):
            interpreter = IntentInterpreter(api_key='fake-key')
            
            result = interpreter.interpret_sync("Pay canteen 50 rupees")
            
            assert result["intent_type"] == "PAYMENT"
            assert result["amount"] == 50.0
            assert result["merchant_vpa"] == "canteen@vit"
            assert result["confidence_score"] == 0.95

    @patch('caps.agent.intent_interpreter.genai.Client')
    def test_interpret_balance_inquiry(self, mock_client_class):
        """Test interpretation of balance inquiry."""
        mock_response = Mock()
        mock_response.text = '{"intent_type": "BALANCE_INQUIRY", "confidence_score": 0.99}'
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'fake-key'}):
            interpreter = IntentInterpreter(api_key='fake-key')
            
            result = interpreter.interpret_sync("Check my balance")
            
            assert result["intent_type"] == "BALANCE_INQUIRY"
            assert result["confidence_score"] == 0.99

    @patch('caps.agent.intent_interpreter.genai.Client')
    def test_interpret_ambiguous_low_confidence(self, mock_client_class):
        """Test that ambiguous input returns low confidence."""
        mock_response = Mock()
        mock_response.text = '{"intent_type": "PAYMENT", "confidence_score": 0.2}'
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'fake-key'}):
            interpreter = IntentInterpreter(api_key='fake-key')
            
            result = interpreter.interpret_sync("Maybe do something")
            
            assert result["confidence_score"] < 0.5

    @patch('caps.agent.intent_interpreter.genai.Client')
    def test_interpret_invalid_json_fallback(self, mock_client_class):
        """Test fallback when LLM returns invalid JSON."""
        mock_response = Mock()
        mock_response.text = 'This is not JSON'
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'fake-key'}):
            interpreter = IntentInterpreter(api_key='fake-key')
            
            result = interpreter.interpret_sync("Pay someone")
            
            # Should return low confidence fallback
            assert result["confidence_score"] == 0.0
            assert "raw_input" in result

    def test_missing_api_key(self):
        """Test that missing API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                IntentInterpreter()

    @patch('caps.agent.intent_interpreter.genai.Client')
    def test_raw_input_included(self, mock_client_class):
        """Test that raw_input is always included in result."""
        mock_response = Mock()
        mock_response.text = '{"intent_type": "PAYMENT", "amount": 100.0, "merchant_vpa": "test@vpa", "confidence_score": 0.9}'
        
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'fake-key'}):
            interpreter = IntentInterpreter(api_key='fake-key')
            
            user_input = "Send 100 to test"
            result = interpreter.interpret_sync(user_input)
            
            assert "raw_input" in result
            assert result["raw_input"] == user_input
