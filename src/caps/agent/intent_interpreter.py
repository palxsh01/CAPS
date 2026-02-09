"""
LLM Intent Interpreter (Ollama Version)

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
import httpx
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# System prompt for intent interpretation
SYSTEM_PROMPT = """You are an untrusted Intent Interpreter inside CAPS (Context-Aware Agentic Payment System).

Your role is strictly LIMITED to converting a single, final, debounced user command
into a structured JSON intent. You do NOT authorize payments. You do NOT reason
about policy, risk, balance, limits, or consent.

SYSTEM CONSTRAINTS:
- You may be unavailable due to quota, latency, or external failure.
- If you cannot reliably interpret the intent, you MUST fail closed.
- You MUST NOT hallucinate missing fields.
- You MUST NOT retry automatically.
- You MUST NOT infer permissions, authorization, or approval.

INPUT GUARANTEES:
- The input is a FINAL transcript (not streaming partials).
- No sensitive context (balance, limits, trust state) is provided.
- The input may be malformed, ambiguous, or incomplete.

OUTPUT REQUIREMENTS:
- Output MUST be valid JSON.
- Output MUST strictly conform to the schema below.
- If interpretation is uncertain, set confidence_score LOW (≤ 0.4).
- If interpretation is not possible, return an ERROR object instead of guessing.

ALLOWED TASK:
- Extract payment-related intent ONLY if explicitly stated by the user.

DISALLOWED BEHAVIOR:
- Do NOT assume default merchants.
- Do NOT normalize brand names.
- Do NOT split or chain intents.
- Do NOT generate follow-up actions.

SCHEMA (STRICT):
{
  "intent_type": "PAYMENT" | "BALANCE_INQUIRY" | "TRANSACTION_HISTORY" | "UNKNOWN",
  "amount": number | null,
  "currency": "INR" | null,
  "merchant_identifier": string | null,
  "confidence_score": number
}

ERROR SCHEMA (FAIL-CLOSED):
{
  "intent_type": "UNKNOWN",
  "error": "INTENT_INTERPRETATION_UNAVAILABLE"
}

EXAMPLES:

Input: "pay Arihant Rs 20"
Output:
{
  "intent_type": "PAYMENT",
  "amount": 20,
  "currency": "INR",
  "merchant_identifier": "Arihant",
  "confidence_score": 0.9
}

Input: "check balance"
Output:
{
  "intent_type": "BALANCE_INQUIRY",
  "confidence_score": 0.95
}

Input: "show my transactions"
Output:
{
  "intent_type": "TRANSACTION_HISTORY",
  "confidence_score": 0.95
}

Input: "handle it"
Output:
{
  "intent_type": "UNKNOWN",
  "confidence_score": 0.1
}

FAILURE MODE:
If you are rate-limited, unavailable, or uncertain:
Return the ERROR SCHEMA.
Do NOT retry.
Do NOT guess.
Do NOT fabricate.

Remember:
You suggest intent.
The system decides.
The wallet obeys only rules.
"""


class IntentInterpreter:
    """
    Local LLM-based Intent Interpreter (Reasoning Layer)
    
    Converts natural language to structured JSON intents using Ollama.
    This layer has zero trust and no access to sensitive data.
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.1,  # Lower temperature for code/JSON models
    ):
        """
        Initialize the intent interpreter with Ollama.
        
        Args:
            ollama_url: URL to Ollama API (defaults to OLLAMA_URL or http://localhost:11434/api/generate)
            model_name: Model to use (defaults to OLLAMA_MODEL or codellama:7b)
            temperature: Model temperature (lower = more deterministic)
        """
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "codellama:7b")
        self.temperature = temperature
        
        self.timeout = 30.0 # Timeout for local inference

        self.logger = logger
        self.logger.info(f"Intent Interpreter initialized with Local LLM: {self.model_name} at {self.ollama_url}")

    async def interpret(self, user_input: str) -> Dict[str, Any]:
        """
        Interpret user input and generate payment intent JSON via Ollama.
        
        Args:
            user_input: Natural language payment request
            
        Returns:
            Dictionary containing the structured intent (unvalidated)
        """
        self.logger.info(f"Interpreting input: {user_input[:100]}...")

        try:
            # Prepare payload for Ollama
            payload = {
                "model": self.model_name,
                "prompt": f"User: {user_input}\nOutput JSON:",
                "system": SYSTEM_PROMPT,
                "stream": False,
                "format": "json", # Enforce JSON mode
                "options": {
                    "temperature": self.temperature
                }
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
            raw_output = result.get("response", "").strip()
            self.logger.debug(f"LLM raw output: {raw_output}")

            # Parse JSON
            intent_data = self._parse_json_response(raw_output, user_input)

            self.logger.info(f"Intent interpretation complete: {intent_data.get('intent_type')}")
            return intent_data

        except httpx.ConnectError:
            self.logger.error("Failed to connect to Ollama. Is it running?")
            return {
                "intent_type": "UNKNOWN",
                "error": "LLM_CONNECTION_FAILED"
            }
        except Exception as e:
            self.logger.error(f"Intent interpretation failed: {e}")
            # FAIL CLOSED
            return {
                "intent_type": "UNKNOWN",
                "error": "INTENT_INTERPRETATION_UNAVAILABLE"
            }

    def interpret_sync(self, user_input: str) -> Dict[str, Any]:
        """
        Synchronous version of interpret (for CLI and simple scripts).
        """
        self.logger.info(f"Interpreting input (sync): {user_input[:100]}...")

        try:
            payload = {
                "model": self.model_name,
                "prompt": f"User: {user_input}\nOutput JSON:",
                "system": SYSTEM_PROMPT,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": self.temperature
                }
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.ollama_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
            raw_output = result.get("response", "").strip()
            self.logger.debug(f"LLM raw output: {raw_output}")

            intent_data = self._parse_json_response(raw_output, user_input)
            self.logger.info(f"Intent interpretation complete: {intent_data.get('intent_type')}")
            return intent_data

        except Exception as e:
            self.logger.error(f"Intent interpretation failed: {e}")
            return {
                "intent_type": "UNKNOWN",
                "error": "INTENT_INTERPRETATION_UNAVAILABLE"
            }

    def _parse_json_response(self, raw_output: str, user_input: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Handle markdown code blocks if Ollama (rarely) outputs them even in JSON mode
        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            json_lines = [l for l in lines if not l.startswith("```")]
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

        if "merchant_identifier" in intent_data and not intent_data.get("merchant_vpa"):
             # Map identifier to VPA
             intent_data["merchant_vpa"] = intent_data["merchant_identifier"]
             if intent_data["merchant_vpa"] and "@" not in intent_data["merchant_vpa"]:
                 intent_data["merchant_vpa"] += "@upi"

        # Ensure raw_input is included
        if "raw_input" not in intent_data:
            intent_data["raw_input"] = user_input

        return intent_data
