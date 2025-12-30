"""Unit tests for InputValidator.

Tests validation of skill names, text inputs, and FAQ patterns.
"""
import pytest

import sys
sys.path.insert(0, 'agents')

from validators.input import InputValidator, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating valid result."""
        result = ValidationResult(valid=True, value="cleaned")
        assert result.valid is True
        assert result.value == "cleaned"
        assert result.error is None

    def test_invalid_result(self):
        """Test creating invalid result."""
        result = ValidationResult(valid=False, error="Bad input")
        assert result.valid is False
        assert result.value is None
        assert result.error == "Bad input"


class TestSkillNameValidation:
    """Tests for skill_name validation."""

    def test_valid_simple_name(self):
        """Valid simple skill names pass."""
        result = InputValidator.skill_name("planning")
        assert result.valid is True
        assert result.value == "planning"

    def test_valid_with_hyphens(self):
        """Skill names with hyphens are valid."""
        result = InputValidator.skill_name("ui-ux-pro-max")
        assert result.valid is True
        assert result.value == "ui-ux-pro-max"

    def test_valid_with_numbers(self):
        """Skill names with numbers are valid."""
        result = InputValidator.skill_name("research-v2")
        assert result.valid is True

    def test_invalid_empty(self):
        """Empty skill name fails."""
        result = InputValidator.skill_name("")
        assert result.valid is False
        assert "1-50" in result.error

    def test_invalid_too_long(self):
        """Skill name over 50 chars fails."""
        long_name = "a" * 51
        result = InputValidator.skill_name(long_name)
        assert result.valid is False
        assert "1-50" in result.error

    def test_invalid_uppercase(self):
        """Uppercase letters fail."""
        result = InputValidator.skill_name("Planning")
        assert result.valid is False
        assert "lowercase" in result.error

    def test_invalid_special_chars(self):
        """Special characters fail."""
        for char in ["!", "@", "#", "$", "_", "."]:
            result = InputValidator.skill_name(f"skill{char}name")
            assert result.valid is False, f"Should reject '{char}'"

    def test_invalid_spaces(self):
        """Spaces fail."""
        result = InputValidator.skill_name("skill name")
        assert result.valid is False

    def test_boundary_50_chars(self):
        """Exactly 50 chars is valid."""
        name = "a" * 50
        result = InputValidator.skill_name(name)
        assert result.valid is True

    def test_boundary_1_char(self):
        """Single char is valid."""
        result = InputValidator.skill_name("a")
        assert result.valid is True


class TestTextInputValidation:
    """Tests for text_input validation."""

    def test_valid_normal_text(self):
        """Normal text passes."""
        result = InputValidator.text_input("Hello, how are you?")
        assert result.valid is True
        assert result.value == "Hello, how are you?"

    def test_invalid_empty(self):
        """Empty text fails."""
        result = InputValidator.text_input("")
        assert result.valid is False
        assert "empty" in result.error

    def test_invalid_too_long_default(self):
        """Text over 4000 chars fails with default limit."""
        long_text = "a" * 4001
        result = InputValidator.text_input(long_text)
        assert result.valid is False
        assert "4000" in result.error

    def test_custom_max_length(self):
        """Custom max_length works."""
        text = "a" * 500
        result = InputValidator.text_input(text, max_length=100)
        assert result.valid is False
        assert "100" in result.error

    def test_strips_null_bytes(self):
        """Null bytes are stripped."""
        result = InputValidator.text_input("Hello\x00World")
        assert result.valid is True
        assert result.value == "HelloWorld"
        assert "\x00" not in result.value

    def test_strips_control_chars(self):
        """Control characters (0x00-0x1F, 0x7F) are stripped."""
        # Test various control characters
        result = InputValidator.text_input("A\x01B\x02C\x1FD\x7FE")
        assert result.valid is True
        assert result.value == "ABCDE"

    def test_preserves_newlines(self):
        """Newlines and tabs are preserved (0x09, 0x0A, 0x0D)."""
        result = InputValidator.text_input("Line1\nLine2\tTabbed")
        assert result.valid is True
        assert "\n" in result.value
        assert "\t" in result.value

    def test_unicode_allowed(self):
        """Unicode characters pass."""
        result = InputValidator.text_input("Hello 世界 🚀")
        assert result.valid is True
        assert result.value == "Hello 世界 🚀"

    def test_boundary_4000_chars(self):
        """Exactly 4000 chars is valid."""
        text = "a" * 4000
        result = InputValidator.text_input(text)
        assert result.valid is True


class TestFaqPatternValidation:
    """Tests for faq_pattern validation."""

    def test_valid_pattern(self):
        """Valid pattern passes."""
        result = InputValidator.faq_pattern("how to deploy")
        assert result.valid is True
        assert result.value == "how to deploy"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        result = InputValidator.faq_pattern("  pattern here  ")
        assert result.valid is True
        assert result.value == "pattern here"

    def test_invalid_empty_after_strip(self):
        """Pattern that's empty after stripping fails."""
        result = InputValidator.faq_pattern("   ")
        assert result.valid is False
        assert "empty" in result.error

    def test_invalid_too_long(self):
        """Pattern over 200 chars fails."""
        long_pattern = "a" * 201
        result = InputValidator.faq_pattern(long_pattern)
        assert result.valid is False
        assert "200" in result.error

    def test_boundary_200_chars(self):
        """Exactly 200 chars is valid."""
        pattern = "a" * 200
        result = InputValidator.faq_pattern(pattern)
        assert result.valid is True

    def test_special_chars_allowed(self):
        """FAQ patterns can include special chars."""
        result = InputValidator.faq_pattern("what is /command?")
        assert result.valid is True
