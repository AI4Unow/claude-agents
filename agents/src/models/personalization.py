"""Personalization data models."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Literal

ToneType = Literal["concise", "detailed", "casual", "formal"]
ResponseLength = Literal["short", "medium", "long"]
MacroActionType = Literal["command", "skill", "sequence"]


@dataclass
class CommunicationPrefs:
    """User communication preferences."""
    use_emoji: bool = False
    markdown_preference: bool = True
    response_length: ResponseLength = "short"


@dataclass
class UserProfile:
    """User profile for personalization."""
    user_id: int
    name: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    tone: ToneType = "concise"
    domain: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    communication: CommunicationPrefs = field(default_factory=CommunicationPrefs)
    onboarded: bool = False
    onboarded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "timezone": self.timezone,
            "language": self.language,
            "tone": self.tone,
            "domain": self.domain,
            "tech_stack": self.tech_stack,
            "communication": {
                "use_emoji": self.communication.use_emoji,
                "markdown_preference": self.communication.markdown_preference,
                "response_length": self.communication.response_length,
            },
            "onboarded": self.onboarded,
            "onboarded_at": self.onboarded_at.isoformat() if self.onboarded_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        comm = data.get("communication", {})
        return cls(
            user_id=data.get("user_id", 0),
            name=data.get("name"),
            timezone=data.get("timezone", "UTC"),
            language=data.get("language", "en"),
            tone=data.get("tone", "concise"),
            domain=data.get("domain", []),
            tech_stack=data.get("tech_stack", []),
            communication=CommunicationPrefs(
                use_emoji=comm.get("use_emoji", False),
                markdown_preference=comm.get("markdown_preference", True),
                response_length=comm.get("response_length", "short"),
            ),
            onboarded=data.get("onboarded", False),
            onboarded_at=datetime.fromisoformat(data["onboarded_at"]) if data.get("onboarded_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )


@dataclass
class WorkContext:
    """Current work context for user."""
    user_id: int
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    active_branch: Optional[str] = None
    recent_skills: List[str] = field(default_factory=list)
    session_facts: List[str] = field(default_factory=list)
    last_active: Optional[datetime] = None
    session_start: Optional[datetime] = None

    MAX_RECENT_SKILLS = 5
    MAX_SESSION_FACTS = 10

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "current_project": self.current_project,
            "current_task": self.current_task,
            "active_branch": self.active_branch,
            "recent_skills": self.recent_skills[-self.MAX_RECENT_SKILLS:],
            "session_facts": self.session_facts[-self.MAX_SESSION_FACTS:],
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "session_start": self.session_start.isoformat() if self.session_start else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkContext":
        return cls(
            user_id=data.get("user_id", 0),
            current_project=data.get("current_project"),
            current_task=data.get("current_task"),
            active_branch=data.get("active_branch"),
            recent_skills=data.get("recent_skills", []),
            session_facts=data.get("session_facts", []),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None,
            session_start=datetime.fromisoformat(data["session_start"]) if data.get("session_start") else None,
        )


@dataclass
class Macro:
    """Personal macro for shortcuts."""
    macro_id: str
    user_id: int
    trigger_phrases: List[str]
    action_type: MacroActionType
    action: str  # command string, skill name, or sequence JSON
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    use_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "macro_id": self.macro_id,
            "user_id": self.user_id,
            "trigger_phrases": self.trigger_phrases,
            "action_type": self.action_type,
            "action": self.action,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "use_count": self.use_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Macro":
        return cls(
            macro_id=data.get("macro_id", ""),
            user_id=data.get("user_id", 0),
            trigger_phrases=data.get("trigger_phrases", []),
            action_type=data.get("action_type", "command"),
            action=data.get("action", ""),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            use_count=data.get("use_count", 0),
        )


@dataclass
class PersonalContext:
    """Aggregated personalization context."""
    profile: Optional[UserProfile] = None
    work_context: Optional[WorkContext] = None
    macros: List[Macro] = field(default_factory=list)
    memories: List[Dict] = field(default_factory=list)

    @property
    def is_onboarded(self) -> bool:
        return self.profile is not None and self.profile.onboarded

    @property
    def has_macros(self) -> bool:
        return len(self.macros) > 0
