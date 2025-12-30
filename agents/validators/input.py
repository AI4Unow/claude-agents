"""Input validation for user data, skill names, and FAQ patterns.

Security:
- Sanitize control characters from user input
- Enforce length limits
- Validate format constraints
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result of input validation."""
    valid: bool
    value: Optional[str] = None
    error: Optional[str] = None


class InputValidator:
    """Validates user inputs with security constraints.

    Rules:
    - Skill names: lowercase alphanumeric + hyphens, 1-50 chars
    - Text inputs: clean control chars, max 4000 chars
    - FAQ patterns: max 200 chars, strip whitespace
    """

    VALID_SKILL_NAME = re.compile(r'^[a-z0-9-]{1,50}$')
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]')

    @staticmethod
    def skill_name(name: str) -> ValidationResult:
        """Validate skill name format.

        Args:
            name: Skill name to validate

        Returns:
            ValidationResult with valid flag and cleaned value or error message

        Rules:
            - Lowercase alphanumeric characters and hyphens only
            - Length: 1-50 characters
        """
        if not name or len(name) > 50:
            return ValidationResult(
                valid=False,
                error="Skill name must be 1-50 characters"
            )

        if not InputValidator.VALID_SKILL_NAME.match(name):
            return ValidationResult(
                valid=False,
                error="Skill name must be lowercase alphanumeric with hyphens only"
            )

        return ValidationResult(valid=True, value=name)

    @staticmethod
    def text_input(text: str, max_length: int = 4000) -> ValidationResult:
        """Validate and sanitize text input.

        Args:
            text: Text to validate
            max_length: Maximum allowed length (default: 4000)

        Returns:
            ValidationResult with cleaned text or error message

        Security:
            - Removes control characters (0x00-0x1F, 0x7F)
            - Enforces length limits
        """
        if not text:
            return ValidationResult(
                valid=False,
                error="Text input cannot be empty"
            )

        if len(text) > max_length:
            return ValidationResult(
                valid=False,
                error=f"Text must not exceed {max_length} characters"
            )

        # Remove control characters
        cleaned = InputValidator.CONTROL_CHARS.sub('', text)

        return ValidationResult(valid=True, value=cleaned)

    @staticmethod
    def faq_pattern(pattern: str) -> ValidationResult:
        """Validate FAQ pattern.

        Args:
            pattern: FAQ pattern to validate

        Returns:
            ValidationResult with cleaned pattern or error message

        Rules:
            - Max 200 characters
            - Cannot be empty after stripping whitespace
        """
        if len(pattern) > 200:
            return ValidationResult(
                valid=False,
                error="Pattern must not exceed 200 characters"
            )

        cleaned = pattern.strip()
        if not cleaned:
            return ValidationResult(
                valid=False,
                error="Pattern cannot be empty"
            )

        return ValidationResult(valid=True, value=cleaned)
