"""
LLM Intent Interpreter

This module contains the LLM agent that translates natural language to structured intents.

CRITICAL SECURITY PROPERTIES:
1. LLM has ZERO access to sensitive context (balances, limits)
2. LLM output is treated as untrusted suggestion
3. All outputs pass through Schema Validator before use
4. No direct payment execution capability
"""

import json
import logging
import os
from typing import Any, Dict

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


# System prompt for intent interpretation
SYSTEM_PROMPT = """You are a payment intent parser for the CAPS payment system.

Your role is to ONLY convert natural language payment requests into structured JSON.

CRITICAL RULES:
1. You NEVER execute payments or access any payment systems
2. You ONLY output JSON matching the PaymentIntent schema
3. You NEVER hallucinate merchant VPAs - only extract what the user provides
4. If uncertain about any field, set confidence_score < 0.8
5. Never include explanations, only JSON

PaymentIntent Schema:
{
  "intent_type": "PAYMENT" | "BALANCE_INQUIRY" | "TRANSACTION_HISTORY",
  "amount": <positive number or null>,
  "currency": "INR",
  "merchant_vpa": "<identifier>@<provider>" | null,
  "confidence_score": <0.0 to 1.0>,
  "raw_input": "<original user input>"
}

Examples:

User: "Pay canteen@vit 50 rupees"
Output: {"intent_type": "PAYMENT", "amount": 50.0, "currency": "INR", "merchant_vpa": "canteen@vit", "confidence_score": 0.95, "raw_input": "Pay canteen@vit 50 rupees"}

User: "Check my balance"
Output: {"intent_type": "BALANCE_INQUIRY", "confidence_score": 0.99, "raw_input": "Check my balance"}

User: "Send some money somewhere"
Output: {"intent_type": "PAYMENT", "confidence_score": 0.3, "raw_input": "Send some money somewhere"}

Output ONLY the JSON, no other text.
"""


class IntentInterpreter:
    """
    LLM-based Intent Interpreter (Reasoning Layer)
    
    Converts natural language to structured JSON intents using Gemini.
    This layer has zero trust and no access to sensitive data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.3,
    ):
        """
        Initialize the intent interpreter.
        
        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use (defaults to GEMINI_MODEL env var)
            temperature: Model temperature (lower = more deterministic)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be set in environment or passed as argument")

        # Read model from env var with fallback to gemini-2.5-flash-lite
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.temperature = temperature

        # Configure new Gemini client
        self.client = genai.Client(api_key=self.api_key)

        self.logger = logger
        self.logger.info(f"Intent Interpreter initialized with model: {self.model_name}")

    async def interpret(self, user_input: str) -> Dict[str, Any]:
        """
        Interpret user input and generate payment intent JSON.
        
        Args:
            user_input: Natural language payment request
            
        Returns:
            Dictionary containing the structured intent (unvalidated)
            
        Raises:
            Exception: If LLM API call fails
        """
        self.logger.info(f"Interpreting input: {user_input[:100]}...")

        try:
            # Build prompt
            prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_input}\nOutput:"

            # Call Gemini (async)
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                ),
            )
            
            # Extract text from response
            raw_output = response.text.strip()
            self.logger.debug(f"LLM raw output: {raw_output}")

            # Parse JSON
            intent_data = self._parse_json_response(raw_output, user_input)

            self.logger.info(f"Intent interpretation complete: {intent_data.get('intent_type')}")
            return intent_data

        except Exception as e:
            self.logger.error(f"Intent interpretation failed: {e}")
            raise

    def interpret_sync(self, user_input: str) -> Dict[str, Any]:
        """
        Synchronous version of interpret (for CLI and simple scripts).
        
        Args:
            user_input: Natural language payment request
            
        Returns:
            Dictionary containing the structured intent (unvalidated)
        """
        self.logger.info(f"Interpreting input (sync): {user_input[:100]}...")

        try:
            # Build prompt
            prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_input}\nOutput:"

            # Call Gemini (synchronous)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                ),
            )
            
            # Extract text from response
            raw_output = response.text.strip()
            self.logger.debug(f"LLM raw output: {raw_output}")

            # Parse JSON
            intent_data = self._parse_json_response(raw_output, user_input)

            self.logger.info(f"Intent interpretation complete: {intent_data.get('intent_type')}")
            return intent_data

        except Exception as e:
            self.logger.error(f"Intent interpretation failed: {e}")
            raise

    def _parse_json_response(self, raw_output: str, user_input: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Handle markdown code blocks
        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            # Remove first and last lines (```json and ```)
            json_lines = [l for l in lines[1:] if not l.startswith("```")]
            raw_output = "\n".join(json_lines)
        
        try:
            intent_data = json.loads(raw_output)
        except json.JSONDecodeError:
            self.logger.warning(f"LLM output was not valid JSON: {raw_output}")
            intent_data = {
                "intent_type": "PAYMENT",
                "confidence_score": 0.0,
                "raw_input": user_input,
            }

        # Ensure raw_input is included
        if "raw_input" not in intent_data:
            intent_data["raw_input"] = user_input

        return intent_data
