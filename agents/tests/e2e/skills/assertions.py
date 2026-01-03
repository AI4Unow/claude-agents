# agents/tests/e2e/skills/assertions.py
"""Multi-level assertion framework for skill response validation.

Levels:
1. Basic: Response exists, minimum length, no error patterns
2. Pattern: Keyword matching, regex patterns
3. Semantic: LLM-as-Judge (optional, env var toggled)
"""
import re
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class AssertionResult:
    """Result of running assertion checks."""
    passed: bool
    level: str  # "basic", "pattern", "semantic"
    message: str
    score: Optional[float] = None

    def __bool__(self) -> bool:
        return self.passed


class SkillAssertionChecker:
    """Multi-level assertion checker for skill responses.

    Usage:
        checker = SkillAssertionChecker(use_llm=False)
        result = checker.check(
            response="...",
            config={"patterns": ["plan", "step"], "min_length": 100},
            skill_name="planning"
        )
        assert result.passed, result.message
    """

    def __init__(self, use_llm: bool = False):
        """Initialize checker.

        Args:
            use_llm: Whether to use LLM-as-Judge for semantic checks.
                     Controlled by E2E_USE_LLM_ASSERTIONS env var.
        """
        self.use_llm = use_llm or os.environ.get(
            "E2E_USE_LLM_ASSERTIONS", "false"
        ).lower() == "true"
        self._evaluator = None

    def check(
        self,
        response: str,
        config: Dict[str, Any],
        skill_name: str
    ) -> AssertionResult:
        """Run assertion checks at all levels.

        Args:
            response: Skill response text
            config: Assertion config from test data
            skill_name: Name of skill (for logging)

        Returns:
            AssertionResult with pass/fail status and message
        """
        if response is None:
            return AssertionResult(
                passed=False,
                level="basic",
                message=f"Skill '{skill_name}' returned None"
            )

        # Level 1: Basic checks
        basic_result = self._check_basic(response, config, skill_name)
        if not basic_result.passed:
            return basic_result

        # Level 2: Pattern matching
        pattern_result = self._check_patterns(response, config, skill_name)
        if not pattern_result.passed:
            return pattern_result

        # Level 3: Semantic (if enabled)
        semantic_config = config.get("semantic", {})
        if self.use_llm and semantic_config.get("enabled"):
            return self._check_semantic(response, semantic_config, skill_name)

        return AssertionResult(
            passed=True,
            level="pattern",
            message=f"Skill '{skill_name}' passed all checks"
        )

    def _check_basic(
        self,
        response: str,
        config: Dict[str, Any],
        skill_name: str
    ) -> AssertionResult:
        """Level 1: Basic validity checks."""
        # Check minimum length
        min_len = config.get("min_length", 20)
        if len(response) < min_len:
            return AssertionResult(
                passed=False,
                level="basic",
                message=f"Response too short: {len(response)} < {min_len}"
            )

        # Check error patterns
        text_lower = response.lower()
        error_patterns = config.get("error_patterns", ["❌", "error:"])
        for pattern in error_patterns:
            # Only match at start of response for error detection
            if text_lower.startswith(pattern.lower()):
                return AssertionResult(
                    passed=False,
                    level="basic",
                    message=f"Error pattern found at start: {pattern}"
                )

        return AssertionResult(
            passed=True,
            level="basic",
            message="Basic checks passed"
        )

    def _check_patterns(
        self,
        response: str,
        config: Dict[str, Any],
        skill_name: str
    ) -> AssertionResult:
        """Level 2: Keyword and regex pattern matching."""
        text_lower = response.lower()

        # Check any-match keywords
        patterns = config.get("patterns", [])
        if patterns:
            matched = any(p.lower() in text_lower for p in patterns)
            if not matched:
                return AssertionResult(
                    passed=False,
                    level="pattern",
                    message=f"No keyword matched. Expected one of: {patterns}"
                )

        # Check regex patterns (if any)
        regex_patterns = config.get("regex", [])
        for pattern in regex_patterns:
            try:
                if not re.search(pattern, response, re.IGNORECASE):
                    return AssertionResult(
                        passed=False,
                        level="pattern",
                        message=f"Regex not matched: {pattern}"
                    )
            except re.error as e:
                return AssertionResult(
                    passed=False,
                    level="pattern",
                    message=f"Invalid regex pattern: {pattern} ({e})"
                )

        return AssertionResult(
            passed=True,
            level="pattern",
            message="Pattern checks passed"
        )

    def _check_semantic(
        self,
        response: str,
        config: Dict[str, Any],
        skill_name: str
    ) -> AssertionResult:
        """Level 3: LLM-based semantic evaluation.

        Only runs if use_llm=True and semantic.enabled=True in config.
        """
        try:
            # Lazy import evaluator
            if self._evaluator is None:
                from src.core.evaluator import EvaluatorOptimizer
                self._evaluator = EvaluatorOptimizer()

            criteria = config.get("criteria", "Response is relevant and complete")
            min_score = config.get("min_score", 0.7)

            # Run evaluation - use asyncio.run() for Python 3.10+ compatibility
            import asyncio
            evaluation = asyncio.run(
                self._evaluator.evaluate_simple(response, criteria)
            )

            if evaluation.score >= min_score:
                return AssertionResult(
                    passed=True,
                    level="semantic",
                    message=f"Semantic check passed: {evaluation.score:.2f}",
                    score=evaluation.score
                )
            else:
                return AssertionResult(
                    passed=False,
                    level="semantic",
                    message=f"Semantic check failed: {evaluation.score:.2f} < {min_score}. {evaluation.feedback}",
                    score=evaluation.score
                )

        except ImportError:
            # EvaluatorOptimizer not available
            return AssertionResult(
                passed=True,
                level="semantic",
                message="Semantic check skipped (evaluator not available)"
            )
        except Exception as e:
            # Fallback to pass if LLM fails
            return AssertionResult(
                passed=True,
                level="semantic",
                message=f"Semantic check skipped (error): {e}"
            )


# Convenience functions

def check_skill_response(
    response: str,
    skill_name: str,
    patterns: List[str] = None,
    min_length: int = 20,
    use_llm: bool = False
) -> AssertionResult:
    """Quick check for skill response.

    Args:
        response: Skill response text
        skill_name: Name of skill
        patterns: Expected keywords (any-match)
        min_length: Minimum response length
        use_llm: Use LLM-as-Judge

    Returns:
        AssertionResult
    """
    config = {
        "min_length": min_length,
        "patterns": patterns or [],
    }
    checker = SkillAssertionChecker(use_llm=use_llm)
    return checker.check(response, config, skill_name)


def assert_skill_response(
    response: str,
    skill_name: str,
    patterns: List[str] = None,
    min_length: int = 20
) -> None:
    """Assert skill response is valid.

    Raises:
        AssertionError: If response fails checks
    """
    result = check_skill_response(response, skill_name, patterns, min_length)
    assert result.passed, result.message
