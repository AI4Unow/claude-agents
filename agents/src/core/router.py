"""Skill Router using Qdrant semantic search.

Claude Agents SDK Pattern: ROUTING
- Classify user request semantically
- Route to best matching skill(s)
- Support fallback to keyword search
"""
from dataclasses import dataclass
from typing import List, Optional

from src.utils.logging import get_logger
from src.skills.registry import SkillRegistry, Skill, get_registry

logger = get_logger()


@dataclass
class RouteMatch:
    """A skill match from routing."""
    skill_name: str
    score: float
    description: str


class SkillRouter:
    """Route requests to skills using Qdrant semantic search.

    Usage:
        router = SkillRouter()
        matches = await router.route("Create a plan for auth system")
        skill = matches[0].skill_name  # "planning"
    """

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        min_score: float = 0.5
    ):
        """Initialize router.

        Args:
            registry: Skill registry (uses singleton if None)
            min_score: Minimum similarity score for matches
        """
        self.registry = registry or get_registry()
        self.min_score = min_score
        self.logger = logger.bind(component="SkillRouter")

    async def route(
        self,
        request: str,
        limit: int = 3,
        category: Optional[str] = None
    ) -> List[RouteMatch]:
        """Route request to matching skills.

        Args:
            request: User request text
            limit: Max number of matches
            category: Optional category filter

        Returns:
            List of RouteMatch sorted by score (descending)
        """
        from src.services.embeddings import get_embedding
        from src.services.qdrant import search_skills, search_with_fallback

        # Get embedding for request
        try:
            embedding = get_embedding(request)
        except Exception as e:
            self.logger.warning("embedding_failed", error=str(e))
            # Fall back to keyword matching
            return await self._keyword_route(request, limit)

        # Search skills in Qdrant
        results = await search_skills(
            embedding=embedding,
            limit=limit,
            category=category
        )

        # If no Qdrant results, try fallback
        if not results:
            results = await search_with_fallback(
                collection="skills",
                embedding=embedding,
                query_text=request,
                limit=limit
            )

        matches = []
        for r in results:
            score = r.get("score", 0)
            if score >= self.min_score:
                matches.append(RouteMatch(
                    skill_name=r.get("name", r.get("id", "")),
                    score=score,
                    description=r.get("description", "")
                ))

        self.logger.info(
            "routing_complete",
            request=request[:50],
            matches=len(matches)
        )

        return matches

    async def _keyword_route(
        self,
        request: str,
        limit: int
    ) -> List[RouteMatch]:
        """Fallback keyword-based routing."""
        summaries = self.registry.discover()
        keywords = set(request.lower().split())

        scored = []
        for summary in summaries:
            # Simple keyword overlap scoring
            desc_words = set(summary.description.lower().split())
            name_words = set(summary.name.lower().replace('-', ' ').split())

            overlap = len(keywords & (desc_words | name_words))
            if overlap > 0:
                score = overlap / len(keywords)
                scored.append((summary, score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            RouteMatch(
                skill_name=s.name,
                score=score,
                description=s.description
            )
            for s, score in scored[:limit]
        ]

    async def route_single(
        self,
        request: str,
        category: Optional[str] = None
    ) -> Optional[Skill]:
        """Route to single best skill and load it.

        Returns:
            Loaded Skill or None if no match
        """
        matches = await self.route(request, limit=1, category=category)
        if not matches:
            return None

        return self.registry.get_full(matches[0].skill_name)

    def get_all_skills(self) -> List[str]:
        """Get all available skill names for reference."""
        return self.registry.get_names()
