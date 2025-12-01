from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone

@dataclass
class PlanningEvent:
    """Base class for planning events."""
    timestamp: datetime = field(init=False)

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc)

@dataclass
class ProposalEvent(PlanningEvent):
    story_id: int
    story_title: str
    team_id: str
    iteration: str
    effort: float

@dataclass
class AssignmentAcceptedEvent(PlanningEvent):
    story_id: int
    team_id: str
    iteration: str
    effort: float
    reason: str

@dataclass
class AssignmentRejectedEvent(PlanningEvent):
    story_id: int
    team_id: str
    reason: str
    suggested_iteration: Optional[str] = None

@dataclass
class GapFillingStartEvent(PlanningEvent):
    message: str = "Starting gap filling phase..."
