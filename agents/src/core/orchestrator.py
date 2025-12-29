"""Orchestrator for multi-skill task execution.

Claude Agents SDK Pattern: ORCHESTRATOR-WORKERS
- Decompose complex tasks into subtasks
- Delegate to skill workers (parallel or sequential)
- Synthesize worker outputs into final response
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Awaitable

from src.utils.logging import get_logger
from src.core.router import SkillRouter
from src.skills.registry import Skill, get_registry

logger = get_logger()

# Type alias for progress callback
ProgressCallback = Callable[[str], Awaitable[None]]


@dataclass
class SubTask:
    """A subtask from decomposition."""
    description: str
    skill_name: Optional[str] = None
    depends_on: List[int] = field(default_factory=list)
    result: Optional[str] = None


@dataclass
class WorkerResult:
    """Result from a skill worker."""
    skill_name: str
    subtask: str
    output: str
    success: bool
    duration_ms: int


class Orchestrator:
    """Decompose tasks, delegate to skill workers, synthesize results.

    Usage:
        orch = Orchestrator()
        result = await orch.execute(
            "Build a login system with tests",
            context={"project": "my-app"}
        )
    """

    def __init__(
        self,
        router: Optional[SkillRouter] = None,
        max_parallel: int = 5,
        llm_client: Optional[Any] = None
    ):
        """Initialize orchestrator.

        Args:
            router: Skill router (creates one if None)
            max_parallel: Max concurrent workers
            llm_client: LLM client for decomposition/synthesis
        """
        self.router = router or SkillRouter()
        self.max_parallel = max_parallel
        self.logger = logger.bind(component="Orchestrator")

        if llm_client is None:
            from src.services.llm import get_llm_client
            llm_client = get_llm_client()
        self.llm = llm_client

    async def execute(
        self,
        task: str,
        context: Optional[Dict] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """Execute a complex task through orchestration.

        Args:
            task: Task description
            context: Additional context (project info, etc.)
            progress_callback: Async function to report progress

        Returns:
            Synthesized final response
        """
        self.logger.info("orchestration_start", task=task[:100])

        async def report(msg: str):
            """Safe progress reporting with error handling."""
            if progress_callback:
                try:
                    await progress_callback(msg)
                except Exception as e:
                    self.logger.warning("progress_callback_error", error=str(e)[:50])

        # Step 1: Decompose into subtasks
        await report("📋 <i>Analyzing task...</i>")
        subtasks = await self.decompose(task, context)
        self.logger.info("decomposed", subtasks=len(subtasks))
        await report(f"📋 <i>Planned {len(subtasks)} subtasks</i>")

        # Step 2: Validate and sanitize dependencies
        dependencies = {str(i): st.depends_on for i, st in enumerate(subtasks)}
        validated_deps = self._validate_dependencies(
            [str(i) for i in range(len(subtasks))],
            dependencies
        )

        # Update subtasks with validated dependencies
        for i, subtask in enumerate(subtasks):
            subtask.depends_on = validated_deps.get(str(i), [])

        # Step 3: Validate DAG (no cycles)
        if not self._validate_dag(
            [str(i) for i in range(len(subtasks))],
            {str(i): st.depends_on for i, st in enumerate(subtasks)}
        ):
            return "Error: Circular skill dependency detected. Please review task decomposition."

        # Step 4: Route subtasks to skills
        for i, subtask in enumerate(subtasks):
            if not subtask.skill_name:
                matches = await self.router.route(subtask.description, limit=1)
                if matches:
                    subtask.skill_name = matches[0].skill_name

        # Step 5: Execute workers with progress
        results = await self._execute_with_dependencies(subtasks, report)

        # Step 6: Synthesize results
        await report("✨ <i>Synthesizing results...</i>")
        final = await self.synthesize(task, results, context)

        # Final stats
        total_time = sum(r.duration_ms for r in results)
        success_count = sum(1 for r in results if r.success)
        await report(f"✅ <i>Complete ({success_count}/{len(results)} skills, {total_time}ms)</i>")

        self.logger.info("orchestration_complete", workers=len(results))
        return final

    def _validate_dependencies(
        self,
        skills: List[str],
        deps: Dict[str, List[int]]
    ) -> Dict[str, List[int]]:
        """Validate and sanitize dependency indices.

        Args:
            skills: List of skill identifiers
            deps: Dependency mapping (skill -> list of indices)

        Returns:
            Validated dependency mapping with invalid indices removed
        """
        n = len(skills)
        validated = {}

        for skill, indices in deps.items():
            # Filter out invalid indices:
            # - Out of bounds (< 0 or >= n)
            # - Self-references (skill depends on itself)
            valid_indices = [
                i for i in indices
                if 0 <= i < n and skills[i] != skill
            ]
            validated[skill] = valid_indices

            if len(valid_indices) < len(indices):
                removed = len(indices) - len(valid_indices)
                self.logger.warning(
                    "invalid_dependencies_removed",
                    skill=skill,
                    removed=removed
                )

        return validated

    def _validate_dag(
        self,
        skills: List[str],
        dependencies: Dict[str, List[int]]
    ) -> bool:
        """Validate skill dependencies form a DAG (no cycles).

        Uses DFS with three-color marking:
        - 0 (white): unvisited
        - 1 (gray): visiting (in current path)
        - 2 (black): visited (all descendants explored)

        A back edge (pointing to a gray node) indicates a cycle.

        Args:
            skills: List of skill identifiers
            dependencies: Dependency mapping (skill -> list of indices)

        Returns:
            True if DAG is valid (no cycles), False if cycle detected
        """
        n = len(skills)
        visited = [0] * n  # 0=unvisited, 1=visiting, 2=visited

        def has_cycle(node: int) -> bool:
            """DFS to detect cycle starting from node."""
            if visited[node] == 1:
                return True  # Back edge = cycle detected

            if visited[node] == 2:
                return False  # Already explored

            visited[node] = 1  # Mark as visiting

            # Check all dependencies
            for dep in dependencies.get(skills[node], []):
                if dep < n and has_cycle(dep):
                    return True

            visited[node] = 2  # Mark as visited
            return False

        # Check all nodes (handles disconnected components)
        for i in range(n):
            if visited[i] == 0 and has_cycle(i):
                self.logger.error(
                    "dag_cycle_detected",
                    skills=[skills[j] for j in range(n) if visited[j] == 1]
                )
                return False

        return True

    async def decompose(
        self,
        task: str,
        context: Optional[Dict] = None
    ) -> List[SubTask]:
        """Decompose a complex task into subtasks.

        Uses LLM to break down the task intelligently.
        """
        context_str = ""
        if context:
            context_str = f"\nContext: {context}"

        prompt = f"""Decompose this task into 2-5 subtasks that can be assigned to different specialists.

Task: {task}{context_str}

Available specialists: {', '.join(self.router.get_all_skills()[:20])}

Return a JSON array of subtasks. Each subtask should have:
- "description": What needs to be done
- "skill": Best matching specialist (or null if unknown)
- "depends_on": Array of subtask indices this depends on (0-indexed)

Example:
[
  {{"description": "Design database schema", "skill": "backend-development", "depends_on": []}},
  {{"description": "Create API endpoints", "skill": "backend-development", "depends_on": [0]}},
  {{"description": "Build login form", "skill": "frontend-development", "depends_on": [1]}}
]

Return ONLY the JSON array, no other text."""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
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

            subtask_data = json.loads(response.strip())

            return [
                SubTask(
                    description=s.get("description", ""),
                    skill_name=s.get("skill"),
                    depends_on=s.get("depends_on", [])
                )
                for s in subtask_data
            ]

        except Exception as e:
            self.logger.error("decompose_failed", error=str(e))
            # Fallback: single subtask
            return [SubTask(description=task)]

    async def _execute_with_dependencies(
        self,
        subtasks: List[SubTask],
        report: Callable[[str], Awaitable[None]] = None
    ) -> List[WorkerResult]:
        """Execute subtasks respecting dependencies with progress."""
        results: List[WorkerResult] = []
        completed = set()

        async def noop_report(msg: str):
            pass

        if report is None:
            report = noop_report

        while len(completed) < len(subtasks):
            # Find ready tasks (all dependencies completed)
            ready = []
            for i, subtask in enumerate(subtasks):
                if i not in completed:
                    if all(d in completed for d in subtask.depends_on):
                        ready.append((i, subtask))

            if not ready:
                self.logger.error("dependency_deadlock")
                break

            # Execute ready tasks in parallel (up to max_parallel)
            batch = ready[:self.max_parallel]

            # Report starting skills
            skill_names = [st.skill_name or "general" for _, st in batch]
            if len(skill_names) == 1:
                await report(f"🔧 <i>Using: {skill_names[0]}</i>")
            else:
                await report(f"🔧 <i>Using: {', '.join(skill_names)}</i>")

            batch_results = await asyncio.gather(*[
                self._execute_worker(
                    subtask,
                    {str(d): results[d].output for d in subtask.depends_on if d < len(results)}
                )
                for i, subtask in batch
            ])

            for (i, subtask), result in zip(batch, batch_results):
                results.append(result)
                subtasks[i].result = result.output
                completed.add(i)

                # Preview of result (first 100 chars)
                preview = result.output[:100].replace('\n', ' ')
                if len(result.output) > 100:
                    preview += "..."

                emoji = "📝" if result.success else "❌"
                await report(f"{emoji} <i>{result.skill_name}: {preview}</i>")

        return results

    async def _execute_worker(
        self,
        subtask: SubTask,
        dependency_outputs: Dict[str, str]
    ) -> WorkerResult:
        """Execute a single skill worker."""
        import time
        start = time.time()

        skill_name = subtask.skill_name or "general"

        try:
            # Load skill
            registry = get_registry()
            skill = registry.get_full(skill_name) if skill_name != "general" else None

            # Build prompt
            deps_context = ""
            if dependency_outputs:
                deps_context = "\n\nPrevious results:\n" + "\n".join(
                    f"- {k}: {v[:200]}..." if len(v) > 200 else f"- {k}: {v}"
                    for k, v in dependency_outputs.items()
                )

            system = skill.get_system_prompt() if skill else "You are a helpful assistant."
            user_message = f"{subtask.description}{deps_context}"

            # Execute with LLM
            response = self.llm.chat(
                messages=[{"role": "user", "content": user_message}],
                system=system,
                max_tokens=2048
            )

            duration_ms = int((time.time() - start) * 1000)

            return WorkerResult(
                skill_name=skill_name,
                subtask=subtask.description,
                output=response,
                success=True,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            self.logger.error("worker_failed", skill=skill_name, error=str(e))

            return WorkerResult(
                skill_name=skill_name,
                subtask=subtask.description,
                output=f"Error: {str(e)}",
                success=False,
                duration_ms=duration_ms
            )

    async def synthesize(
        self,
        original_task: str,
        results: List[WorkerResult],
        context: Optional[Dict] = None
    ) -> str:
        """Synthesize worker outputs into final response."""
        if len(results) == 1:
            return results[0].output

        results_text = "\n\n".join(
            f"### {r.skill_name}: {r.subtask}\n{r.output}"
            for r in results
            if r.success
        )

        prompt = f"""Synthesize these worker outputs into a coherent final response.

Original Task: {original_task}

Worker Outputs:
{results_text}

Create a unified response that integrates all the work done. Be concise but complete."""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            return response

        except Exception as e:
            self.logger.error("synthesis_failed", error=str(e))
            # Fallback: concatenate results
            return results_text
