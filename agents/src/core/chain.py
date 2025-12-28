"""Chained Execution for sequential skill pipelines.

Claude Agents SDK Pattern: PROMPT CHAINING
- Execute skills in sequence
- Pass output of one skill as input to next
- Track intermediate results
"""
from dataclasses import dataclass
from typing import List, Optional, Any, Dict

from src.utils.logging import get_logger
from src.skills.registry import get_registry

logger = get_logger()


@dataclass
class ChainStep:
    """A step in the execution chain."""
    skill_name: str
    input_text: str
    output_text: Optional[str] = None
    duration_ms: int = 0
    success: bool = True


@dataclass
class ChainResult:
    """Result of a chained execution."""
    steps: List[ChainStep]
    final_output: str
    total_duration_ms: int
    success: bool


class ChainedExecution:
    """Execute skills in sequence with output→input passing.

    Usage:
        chain = ChainedExecution()
        result = await chain.execute(
            skills=["research", "planning", "code-review"],
            initial_input="Build user authentication"
        )
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """Initialize chained executor.

        Args:
            llm_client: LLM client (uses default if None)
        """
        self.registry = get_registry()
        self.logger = logger.bind(component="ChainedExecution")

        if llm_client is None:
            from src.services.llm import get_llm_client
            llm_client = get_llm_client()
        self.llm = llm_client

    async def execute(
        self,
        skills: List[str],
        initial_input: str,
        transform_output: bool = True
    ) -> ChainResult:
        """Execute skills in sequence.

        Args:
            skills: List of skill names to execute in order
            initial_input: Initial input for first skill
            transform_output: Whether to transform output for next skill

        Returns:
            ChainResult with all steps and final output
        """
        steps: List[ChainStep] = []
        current_input = initial_input
        total_duration = 0

        self.logger.info(
            "chain_start",
            skills=skills,
            input_len=len(initial_input)
        )

        for skill_name in skills:
            step = await self._execute_step(
                skill_name=skill_name,
                input_text=current_input,
                previous_steps=steps
            )
            steps.append(step)
            total_duration += step.duration_ms

            if not step.success:
                self.logger.error("chain_step_failed", skill=skill_name)
                return ChainResult(
                    steps=steps,
                    final_output=step.output_text or f"Error in {skill_name}",
                    total_duration_ms=total_duration,
                    success=False
                )

            # Prepare input for next step
            if transform_output and step.output_text:
                current_input = await self._transform_for_next(
                    step.output_text,
                    skills[skills.index(skill_name) + 1] if skills.index(skill_name) < len(skills) - 1 else None
                )
            else:
                current_input = step.output_text or current_input

        final_output = steps[-1].output_text if steps else initial_input

        self.logger.info(
            "chain_complete",
            steps=len(steps),
            duration_ms=total_duration
        )

        return ChainResult(
            steps=steps,
            final_output=final_output,
            total_duration_ms=total_duration,
            success=True
        )

    async def _execute_step(
        self,
        skill_name: str,
        input_text: str,
        previous_steps: List[ChainStep]
    ) -> ChainStep:
        """Execute a single step in the chain."""
        import time
        start = time.time()

        step = ChainStep(skill_name=skill_name, input_text=input_text)

        try:
            # Load skill
            skill = self.registry.get_full(skill_name)

            if not skill:
                step.success = False
                step.output_text = f"Skill not found: {skill_name}"
                return step

            # Build context from previous steps
            context = ""
            if previous_steps:
                context = "\n\n[Previous Steps]\n" + "\n".join(
                    f"- {s.skill_name}: {s.output_text[:200]}..."
                    if s.output_text and len(s.output_text) > 200
                    else f"- {s.skill_name}: {s.output_text}"
                    for s in previous_steps[-3:]  # Last 3 steps
                )

            # Execute with LLM
            response = self.llm.chat(
                messages=[{
                    "role": "user",
                    "content": f"{input_text}{context}"
                }],
                system=skill.get_system_prompt(),
                max_tokens=2048
            )

            step.output_text = response
            step.success = True

        except Exception as e:
            self.logger.error("step_error", skill=skill_name, error=str(e))
            step.success = False
            step.output_text = f"Error: {str(e)}"

        step.duration_ms = int((time.time() - start) * 1000)
        return step

    async def _transform_for_next(
        self,
        output: str,
        next_skill: Optional[str]
    ) -> str:
        """Transform output to be suitable input for next skill."""
        if not next_skill:
            return output

        # Simple transformation: add context about what was done
        return f"""Based on the previous analysis:

{output}

Please continue with your specialized processing."""

    async def execute_with_gates(
        self,
        skills: List[str],
        initial_input: str,
        gate_condition: Optional[callable] = None
    ) -> ChainResult:
        """Execute chain with quality gates between steps.

        Args:
            skills: Skill sequence
            initial_input: Initial input
            gate_condition: Async function(step_output) -> bool for gate check

        Returns:
            ChainResult (may be partial if gate fails)
        """
        steps: List[ChainStep] = []
        current_input = initial_input
        total_duration = 0

        for skill_name in skills:
            step = await self._execute_step(
                skill_name=skill_name,
                input_text=current_input,
                previous_steps=steps
            )
            steps.append(step)
            total_duration += step.duration_ms

            if not step.success:
                break

            # Check gate condition
            if gate_condition and step.output_text:
                passes_gate = await gate_condition(step.output_text)
                if not passes_gate:
                    self.logger.info("gate_failed", skill=skill_name)
                    break

            current_input = step.output_text or current_input

        return ChainResult(
            steps=steps,
            final_output=steps[-1].output_text if steps else initial_input,
            total_duration_ms=total_duration,
            success=all(s.success for s in steps)
        )
