"""Data models for PI Planning application."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid  # Added uuid import
from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeatureStatus(str, Enum):
    """Feature status."""
    NEW = "new"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Team(BaseModel):
    """Team model."""
    id: str
    name: str
    capacity_per_iteration: int = Field(default=40, description="Story points capacity")
    current_load: int = Field(default=0, description="Current iteration load")
    # Capacity per Sprint (total capacity per sprint)
    capacity_per_sprint: Optional[Dict[str, Dict[str, int]]] = Field(
        default=None,
        description="Capacity per sprint: {'Sprint 1': {'total': 50}, ...}"
    )


class UserStory(BaseModel):
    """User Story model."""
    id: int
    title: str
    description: Optional[str] = None
    feature_id: int = Field(description="Feature this US belongs to")
    assigned_team: Optional[str] = Field(default=None, description="Team assigned to this US")
    effort: Optional[float] = Field(default=None, description="Story points (for new stories)")
    remaining_work: Optional[float] = Field(default=None, description="Remaining work in hours (for active stories)")
    state: FeatureStatus = FeatureStatus.NEW
    
    # Dependencies (can be Feature IDs or UserStory IDs)
    depends_on_features: List[int] = Field(default_factory=list, description="Feature IDs this US depends on")
    depends_on_stories: List[int] = Field(default_factory=list, description="UserStory IDs this US depends on")
    
    # Assignment (negotiated)
    assigned_iteration: Optional[str] = Field(default=None, description="Iteration to be negotiated")
    sequence_order: Optional[int] = Field(default=None, description="Order in execution sequence")
    
    def get_effort(self) -> Optional[float]:
        """
        Get the appropriate effort value for planning.
        For active stories, returns remaining_work if available, otherwise effort.
        For new stories, returns effort.
        """
        if self.state == FeatureStatus.ACTIVE:
            return self.remaining_work if self.remaining_work is not None else self.effort
        return self.effort


class Milestone(BaseModel):
    """Milestone model for Feature deadlines."""
    id: int
    title: str
    target_date: Optional[datetime] = Field(default=None, description="Target date for milestone")
    sprint: Optional[str] = Field(default=None, description="Sprint when milestone should be completed")
    
class Feature(BaseModel):
    """Feature/Epic/WorkItem model."""
    id: int
    title: str
    description: Optional[str] = None
    area_path: Optional[str] = None
    iteration_path: Optional[str] = None
    state: FeatureStatus = FeatureStatus.NEW
    priority: Priority = Priority.MEDIUM
    
    # WSJF fields (used for prioritizing User Stories)
    business_value: Optional[float] = Field(default=None, description="Business value (0-100)")
    cost_of_delay: Optional[float] = Field(default=None, description="Cost of delay")
    effort: Optional[float] = Field(default=None, description="Total effort (sum of US)")
    wsjf_score: Optional[float] = Field(default=None, description="WSJF score")
    wsjf_rank: Optional[int] = Field(default=None, description="WSJF ranking")
    
    # Dependencies (Feature level)
    depends_on_features: List[int] = Field(default_factory=list, description="Feature IDs this depends on")
    
    # Milestones (deadlines for features)
    milestones: List[Milestone] = Field(default_factory=list, description="Milestones with target dates")
    deadline_sprint: Optional[str] = Field(default=None, description="Latest sprint when feature must be completed (from milestones)")
    
    # User Stories
    user_stories: List[UserStory] = Field(default_factory=list, description="User Stories in this feature")
    
    # Assignment (pre-assigned to team)
    assigned_team: Optional[str] = Field(default=None, description="Team assigned to this feature")
    assigned_iteration: Optional[str] = Field(default=None, description="Iteration (derived from US)")


class Assignment(BaseModel):
    """Assignment of User Story to iteration (sequencing result)."""
    user_story_id: int
    feature_id: int  # Parent feature
    team_id: str  # Pre-assigned team
    iteration: str  # Negotiated iteration
    effort: float
    status: str = Field(default="proposed", description="proposed, accepted, rejected, scheduled")
    sequence_order: Optional[int] = Field(default=None, description="Order in execution sequence")
    dependency_ready: bool = Field(default=False, description="All dependencies are scheduled before this")


class Message(BaseModel):
    """Message between agents."""
    message_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    response: Optional[Dict[str, Any]] = None


class NegotiationRound(BaseModel):
    """Single negotiation round."""
    round_number: int
    proposals: List[Assignment]
    responses: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# SAFe-specific models for POC
class RiskLevel(str, Enum):
    """Risk impact levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Risk(BaseModel):
    """Risk model for SAFe Risk Burndown."""
    id: str
    title: str
    description: str
    probability: float = Field(ge=0.0, le=1.0, description="Probability 0-1")
    impact: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = Field(default=0.0, description="probability * impact_weight")
    mitigation: Optional[str] = None
    owner: Optional[str] = None  # Team ID
    status: str = Field(default="identified", description="identified, mitigated, accepted")
    related_features: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PIObjective(BaseModel):
    """PI Objective model for SAFe."""
    id: str
    title: str
    description: str
    business_value: float = Field(ge=1.0, le=10.0, description="SAFe business value 1-10")
    features: List[int] = Field(default_factory=list, description="Feature IDs contributing")
    team_commitments: Dict[str, bool] = Field(default_factory=dict, description="team_id -> committed")
    status: str = Field(default="draft", description="draft, committed, achieved")
    metrics: Optional[Dict[str, Any]] = None


class ProgramBoard(BaseModel):
    """Final program board with SAFe elements."""
    project: str
    pi_start: str
    iterations: List[str]
    teams: List[Team]
    assignments: List[Assignment]
    features: List[Feature]
    pi_objectives: List[PIObjective] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    negotiation_rounds: int = 0
    ai_insights: Optional[Dict[str, Any]] = Field(default=None, description="AI-generated insights about the plan")


class Transcript(BaseModel):
    """Full conversation transcript."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message] = Field(default_factory=list)
    final_plan: Optional[ProgramBoard] = None

