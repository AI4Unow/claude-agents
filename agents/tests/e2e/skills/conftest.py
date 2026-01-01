"""Skill test fixtures and helpers."""
import pytest

# Skill categories for parametrization
REMOTE_SKILLS = [
    "planning", "debugging", "research", "code-review",
    "backend-development", "frontend-development", "mobile-development",
    "ui-ux-pro-max", "ui-styling", "frontend-design-pro",
    "ai-multimodal", "ai-artist",
    "gemini-grounding", "gemini-thinking",
    "content", "content-research-writer",
    "data", "databases",
    "github", "telegram-chat", "shopify", "payment-integration",
    "devops", "firebase-automation",
    "problem-solving", "sequential-thinking",
    "skill-creator", "mcp-management",
    "internal-comms", "worktree-manager",
    "better-auth", "chrome-devtools", "mcp-builder",
    "repomix", "web-frameworks", "webapp-testing",
]

LOCAL_SKILLS = [
    "pdf", "docx", "xlsx", "pptx",
    "video-downloader", "image-enhancer",
    "media-processing", "canvas-design",
]

HYBRID_SKILLS = [
    "better-auth", "chrome-devtools", "mcp-builder",
    "repomix", "sequential-thinking", "web-frameworks", "webapp-testing",
]

SLOW_SKILLS = [
    "gemini-deep-research",
    "gemini-vision",
]


@pytest.fixture(params=REMOTE_SKILLS)
def remote_skill(request):
    """Parametrize over remote skills."""
    return request.param


@pytest.fixture(params=LOCAL_SKILLS)
def local_skill(request):
    """Parametrize over local skills."""
    return request.param


@pytest.fixture(params=SLOW_SKILLS)
def slow_skill(request):
    """Parametrize over slow skills."""
    return request.param
