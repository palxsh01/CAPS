"""Integration tests for LLM Intent Interpreter (Ollama)."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from caps.agent import IntentInterpreter

class TestIntentInterpreter:
    """Test IntentInterpreter with mocked Ollama API."""

    @patch('caps.agent.intent_interpreter.httpx.Client')
    def test_interpret_payment_intent(self, mock_client_class):
        """Test interpretation of payment request."""
        # Mock httpx response
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": '{"intent_type": "PAYMENT", "amount": 50.0, "merchant_identifier": "canteen", "confidence_score": 0.95}'
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client
        
        interpreter = IntentInterpreter()
        result = interpreter.interpret_sync("Pay canteen 50 rupees")
        
        assert result["intent_type"] == "PAYMENT"
        assert result["amount"] == 50.0
        assert result["merchant_vpa"] == "canteen@upi" # Inferred via map logic
        assert result["confidence_score"] == 0.95

    @patch('caps.agent.intent_interpreter.httpx.Client')
    def test_interpret_balance_inquiry(self, mock_client_class):
        """Test interpretation of balance inquiry."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": '{"intent_type": "BALANCE_INQUIRY", "confidence_score": 0.99}'
        }
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client
        
        interpreter = IntentInterpreter()
        result = interpreter.interpret_sync("Check my balance")
        
        assert result["intent_type"] == "BALANCE_INQUIRY"

    @patch('caps.agent.intent_interpreter.httpx.Client')
    def test_interpret_json_markdown_fallback(self, mock_client_class):
        """Test fallback when LLM returns markdown code blocks."""
        mock_response = Mock()
        # Simulate local LLM wrapping JSON in markdown
        mock_response.json.return_value = {
            "response": '```json\n{"intent_type": "PAYMENT", "amount": 20}\n```'
        }
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client
        
        interpreter = IntentInterpreter()
        result = interpreter.interpret_sync("Pay 20")
        
        assert result["intent_type"] == "PAYMENT"
        assert result["amount"] == 20

    @patch('caps.agent.intent_interpreter.httpx.Client')
    def test_connection_error(self, mock_client_class):
        """Test handling of connection errors."""
        mock_client_class.side_effect = Exception("Connection refused")
        
        interpreter = IntentInterpreter()
        result = interpreter.interpret_sync("Pay 20")
        
        assert result["intent_type"] == "UNKNOWN"
        assert result["error"] == "INTENT_INTERPRETATION_UNAVAILABLE"
