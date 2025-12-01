"""Base interfaces for agents."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.models import Feature, Team, UserStory, PIObjective, Risk, Assignment


class IWSJFAgent(ABC):
    """Interface for WSJF Agent."""
    
    @abstractmethod
    def calculate_wsjf(self, features: List[Feature]) -> List[Feature]:
        """Calculate WSJF scores for features."""
        pass


class ITeamAgent(ABC):
    """Interface for Team Agent."""
    
    @abstractmethod
    def can_do_user_story(
        self,
        user_story: UserStory,
        iteration: str,
        scheduled_stories: Dict[int, str],
        scheduled_features: Dict[int, str]
    ) -> Dict[str, Any]:
        """Check if team can do User Story."""
        pass
    
    @abstractmethod
    def get_capacity_status(self, iteration: str) -> Dict[str, Any]:
        """Get capacity status for iteration."""
        pass


class IObjectiveAgent(ABC):
    """Interface for Objective Agent."""
    
    @abstractmethod
    def generate_objectives(
        self,
        features: List[Feature],
        teams: List[Team]
    ) -> List[PIObjective]:
        """Generate PI Objectives."""
        pass


class IRiskAgent(ABC):
    """Interface for Risk Agent."""
    
    @abstractmethod
    def identify_risks(
        self,
        features: List[Feature],
        assignments: List[Assignment],
        teams: List[Team],
        team_agents: Dict[str, Any]
    ) -> List[Risk]:
        """Identify risks."""
        pass


class IUserStorySequencingAgent(ABC):
    """Interface for User Story Sequencing Agent."""
    
    @abstractmethod
    def build_execution_sequence(self, features: List[Feature]) -> List[UserStory]:
        """Build execution sequence for User Stories."""
        pass


class IProgramManager(ABC):
    """Interface for Program Manager Agent."""
    
    @abstractmethod
    async def run_negotiation(self) -> Any:
        """Run negotiation process."""
        pass
    
    @abstractmethod
    def get_final_plan(self) -> Dict[str, Any]:
        """Get final plan."""
        pass


class IReportingAgent(ABC):
    """Interface for Reporting Agent."""
    
    @abstractmethod
    def generate_program_board(
        self,
        project: str,
        pi_start: str,
        iterations: List[str],
        teams: List[Team],
        features: List[Feature],
        assignments: List[Assignment],
        negotiation_rounds: int,
        pi_objectives: Optional[List[PIObjective]] = None,
        risks: Optional[List[Risk]] = None
    ) -> Any:
        """Generate program board."""
        pass
    
    @abstractmethod
    def generate_transcript(
        self,
        session_id: str,
        start_time: Any,
        messages: List[Any],
        final_plan: Any
    ) -> Any:
        """Generate transcript."""
        pass
