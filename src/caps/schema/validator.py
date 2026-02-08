"""
Schema Validator - Trust Gate 1

This module enforces strict schema validation on LLM outputs.
It prevents hallucinated fields, type mismatches, and malformed data from progressing
to the Policy Engine.
"""

import json
import logging
from typing import Any, Dict, Union

from pydantic import ValidationError as PydanticValidationError

from caps.schema.intent_schema import PaymentIntent


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error for schema violations."""

    def __init__(self, message: str, errors: list[Dict[str, Any]] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


class SchemaValidator:
    """
    Schema Validator (Trust Gate 1)
    
    Enforces strict typing and prevents:
    - Hallucinated fields
    - Type mismatches
    - Missing required fields
    - Invalid data formats
    
    This is the first line of defense against LLM errors.
    """

    def __init__(self):
        self.logger = logger

    def validate(self, data: Union[str, Dict[str, Any]]) -> PaymentIntent:
        """
        Validate and parse intent data.
        
        Args:
            data: Raw JSON string or dictionary from LLM
            
        Returns:
            Validated PaymentIntent object
            
        Raises:
            ValidationError: If data fails schema validation
        """
        # Parse JSON if string
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parse error: {e}")
                raise ValidationError(
                    message="PARSE_ERROR: Invalid JSON format",
                    errors=[{"type": "json_decode", "msg": str(e)}],
                )
        else:
            parsed_data = data

        # Validate against schema
        try:
            intent = PaymentIntent.model_validate(parsed_data)
            self.logger.info(f"Schema validation passed for intent_id: {intent.intent_id}")
            return intent

        except PydanticValidationError as e:
            # Extract field-specific errors
            errors = []
            for error in e.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "type": error["type"],
                    "msg": error["msg"],
                })

            self.logger.error(f"Schema validation failed: {errors}")
            raise ValidationError(
                message="VALIDATION_ERROR: Schema validation failed",
                errors=errors,
            )

    def validate_safe(self, data: Union[str, Dict[str, Any]]) -> tuple[PaymentIntent | None, ValidationError | None]:
        """
        Safe validation that returns errors instead of raising.
        
        Args:
            data: Raw JSON string or dictionary from LLM
            
        Returns:
            Tuple of (validated_intent, error)
            - On success: (PaymentIntent, None)
            - On failure: (None, ValidationError)
        """
        try:
            intent = self.validate(data)
            return intent, None
        except ValidationError as e:
            return None, e
