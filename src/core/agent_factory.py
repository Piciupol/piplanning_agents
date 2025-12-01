"""Factory for creating agents."""
from typing import List, Dict, Any, Optional

from src.agents.base_agents import IProgramManager, ITeamAgent
from src.agents.data_agent import DataAgent
from src.agents.program_manager import ProgramManager
from src.agents.team_agent import TeamAgent
from src.agents.dependency_agent import DependencyAgent
from src.agents.reporting_agent import ReportingAgent
from src.agents.objective_agent import ObjectiveAgent
from src.agents.risk_agent import RiskAgent
from src.core.models import Feature, Team
from src.core.strategies import (
    StandardPrioritization, 
    DependencyAwarePlanningStrategy
)
from src.utils.config import Config

class AgentFactory:
    """Factory for creating agents with appropriate configuration."""
    
    def __init__(self):
        """Initialize factory."""
        pass
    
    def create_data_agent(self) -> DataAgent:
        return DataAgent()
    
    def create_program_manager(
        self,
        teams: List[Team],
        features: List[Feature],
        iterations: List[str],
        max_rounds: int = 3
    ) -> ProgramManager:
        # Strategies
        planning_strategy = DependencyAwarePlanningStrategy()
        prioritization_strategy = StandardPrioritization()
            
        return ProgramManager(
            teams=teams,
            features=features,
            iterations=iterations,
            max_rounds=max_rounds,
            planning_strategy=planning_strategy,
            prioritization_strategy=prioritization_strategy
        )
    
    def create_team_agent(self, team: Team) -> TeamAgent:
        return TeamAgent(team)
    
    def create_dependency_agent(self) -> DependencyAgent:
        return DependencyAgent()
    
    def create_reporting_agent(self) -> ReportingAgent:
        return ReportingAgent()
        
    def create_objective_agent(self) -> ObjectiveAgent:
        return ObjectiveAgent()
        
    def create_risk_agent(self) -> RiskAgent:
        return RiskAgent()
