"""Evaluator-Optimizer for quality-critical outputs.

Claude Agents SDK Pattern: EVALUATOR-OPTIMIZER
- Generate initial output
- Evaluate output quality with LLM-as-Judge
- Improve based on feedback (max iterations)
"""
from dataclasses import dataclass
from typing import Optional, Any, List, Dict

from src.utils.logging import get_logger
from src.skills.registry import Skill, get_registry

logger = get_logger()


@dataclass
class Evaluation:
    """Result of evaluating an output."""
    score: float  # 0.0 to 1.0
    feedback: str
    passed: bool
    criteria_scores: Dict[str, float]


@dataclass
class OptimizationResult:
    """Result of the optimization loop."""
    final_output: str
    iterations: int
    final_score: float
    history: List[Dict[str, Any]]
    success: bool


class EvaluatorOptimizer:
    """Generate, evaluate, and improve output quality.

    Usage:
        eo = EvaluatorOptimizer()
        result = await eo.generate_with_evaluation(
            skill=skill,
            task="Write a product description",
            min_score=0.8
        )
    """

    DEFAULT_CRITERIA = [
        ("accuracy", "Is the content factually correct and relevant?"),
        ("completeness", "Does it address all aspects of the task?"),
        ("clarity", "Is it clear, well-structured, and easy to understand?"),
        ("actionability", "Can the user act on this output?"),
    ]

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_iterations: int = 3,
        min_score: float = 0.8
    ):
        """Initialize evaluator-optimizer.

        Args:
            llm_client: LLM client (uses default if None)
            max_iterations: Maximum improvement iterations
            min_score: Score threshold for passing
        """
        self.registry = get_registry()
        self.max_iterations = max_iterations
        self.min_score = min_score
        self.logger = logger.bind(component="EvaluatorOptimizer")

        if llm_client is None:
            from src.services.llm import get_llm_client
            llm_client = get_llm_client()
        self.llm = llm_client

    async def generate_with_evaluation(
        self,
        skill: Skill,
        task: str,
        criteria: Optional[List[tuple]] = None,
        min_score: Optional[float] = None
    ) -> OptimizationResult:
        """Generate output with quality evaluation loop.

        Args:
            skill: Skill to use for generation
            task: Task description
            criteria: List of (name, description) tuples for evaluation
            min_score: Override default min score

        Returns:
            OptimizationResult with final output and metrics
        """
        if criteria is None:
            criteria = self.DEFAULT_CRITERIA
        if min_score is None:
            min_score = self.min_score

        history = []
        current_task = task

        self.logger.info("evaluation_loop_start", task=task[:50], skill=skill.name)

        for iteration in range(self.max_iterations):
            # Generate output
            output = await self._generate(skill, current_task)

            # Evaluate output
            evaluation = await self.evaluate(output, task, criteria)

            history.append({
                "iteration": iteration + 1,
                "output_preview": output[:200],
                "score": evaluation.score,
                "feedback": evaluation.feedback,
                "passed": evaluation.passed
            })

            self.logger.info(
                "iteration_complete",
                iteration=iteration + 1,
                score=evaluation.score,
                passed=evaluation.passed
            )

            if evaluation.passed:
                return OptimizationResult(
                    final_output=output,
                    iterations=iteration + 1,
                    final_score=evaluation.score,
                    history=history,
                    success=True
                )

            # Prepare for next iteration with feedback
            current_task = f"""{task}

[Previous attempt feedback]
Score: {evaluation.score:.2f}
Feedback: {evaluation.feedback}

Please improve the output based on this feedback."""

        # Max iterations reached
        self.logger.warning("max_iterations_reached", final_score=history[-1]["score"])

        return OptimizationResult(
            final_output=output,
            iterations=self.max_iterations,
            final_score=history[-1]["score"],
            history=history,
            success=history[-1]["score"] >= min_score
        )

    async def _generate(self, skill: Skill, task: str) -> str:
        """Generate output using skill."""
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": task}],
                system=skill.get_system_prompt(),
                max_tokens=2048
            )
            return response
        except Exception as e:
            self.logger.error("generate_failed", error=str(e))
            raise

    async def evaluate(
        self,
        output: str,
        original_task: str,
        criteria: List[tuple]
    ) -> Evaluation:
        """Evaluate output quality using LLM-as-Judge.

        Args:
            output: Output to evaluate
            original_task: Original task for context
            criteria: Evaluation criteria

        Returns:
            Evaluation with scores and feedback
        """
        criteria_text = "\n".join(
            f"- {name}: {description}"
            for name, description in criteria
        )

        prompt = f"""Evaluate this output against the given criteria.

ORIGINAL TASK:
{original_task}

OUTPUT TO EVALUATE:
{output}

EVALUATION CRITERIA:
{criteria_text}

For each criterion, provide a score from 0.0 to 1.0.
Then provide an overall score and specific feedback for improvement.

Return your evaluation in this exact JSON format:
{{
  "criteria_scores": {{
    "accuracy": 0.8,
    "completeness": 0.7,
    "clarity": 0.9,
    "actionability": 0.6
  }},
  "overall_score": 0.75,
  "feedback": "Specific suggestions for improvement..."
}}

Return ONLY the JSON, no other text."""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )

            import json
            # Extract JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            if response.endswith("```"):
                response = response[:-3]

            data = json.loads(response.strip())

            score = data.get("overall_score", 0.5)
            criteria_scores = data.get("criteria_scores", {})
            feedback = data.get("feedback", "No specific feedback provided.")

            return Evaluation(
                score=score,
                feedback=feedback,
                passed=score >= self.min_score,
                criteria_scores=criteria_scores
            )

        except Exception as e:
            self.logger.error("evaluation_failed", error=str(e))
            # Fallback: assume needs improvement
            return Evaluation(
                score=0.5,
                feedback=f"Evaluation failed: {str(e)}. Please review output manually.",
                passed=False,
                criteria_scores={}
            )

    async def evaluate_simple(
        self,
        output: str,
        task: str
    ) -> Evaluation:
        """Simple pass/fail evaluation."""
        return await self.evaluate(output, task, self.DEFAULT_CRITERIA)

    async def improve_with_feedback(
        self,
        skill: Skill,
        output: str,
        feedback: str,
        original_task: str
    ) -> str:
        """Improve output based on specific feedback.

        Useful for human-in-the-loop scenarios.
        """
        improvement_task = f"""{original_task}

[Previous output]
{output}

[Feedback for improvement]
{feedback}

Please provide an improved version addressing the feedback."""

        return await self._generate(skill, improvement_task)
