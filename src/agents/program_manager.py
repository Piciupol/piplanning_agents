"""Hybrid Program Manager - orchestrates User Story sequencing."""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, AsyncIterator, Optional

from src.core.models import Feature, Team, Assignment, Message, NegotiationRound, UserStory
from src.agents.base_agents import ITeamAgent, IProgramManager
from src.agents.dependency_agent import DependencyAgent
from src.agents.team_agent import TeamAgent
from src.utils.config import Config
from src.core.strategies import PlanningStrategy, DependencyAwarePlanningStrategy, PrioritizationStrategy, StandardPrioritization
from src.core.events import PlanningEvent, ProposalEvent, AssignmentAcceptedEvent, AssignmentRejectedEvent, GapFillingStartEvent

class ProgramManager(IProgramManager):
    """Hybrid Program Manager with intelligent negotiation capabilities."""
    
    def __init__(
        self,
        teams: List[Team],
        features: List[Feature],
        iterations: List[str],
        max_rounds: int = 3,
        team_agent_factory: Any = None,
        planning_strategy: Optional[PlanningStrategy] = None,
        prioritization_strategy: Optional[PrioritizationStrategy] = None
    ):
        self.teams = teams
        self.features = features
        self.iterations = iterations
        self.max_rounds = max_rounds
        
        self.planning_strategy = planning_strategy or DependencyAwarePlanningStrategy()
        self.prioritization_strategy = prioritization_strategy or StandardPrioritization()
        
        if team_agent_factory:
            self.team_agents: Dict[str, ITeamAgent] = {
                team.name: team_agent_factory.create_team_agent(team) for team in teams
            }
            for team in teams:
                if team.id not in self.team_agents:
                    self.team_agents[team.id] = self.team_agents[team.name]
        else:
            self.team_agents: Dict[str, ITeamAgent] = {
                team.name: TeamAgent(team) for team in teams
            }
            for team in teams:
                if team.id not in self.team_agents:
                    self.team_agents[team.id] = self.team_agents[team.name]
            
        self.dependency_agent = DependencyAgent()
        
        # State
        self.assignments = []
        self.negotiation_rounds = []
        self.messages = [] # Kept for backward compatibility if needed, but mostly empty now
        self.scheduled_stories: Dict[int, str] = {}
        self.scheduled_features: Dict[int, str] = {}

    def prioritize_work(self, sprint_configs: Dict[str, Any] = None) -> List[Feature]:
        """
        Sort features based on the active prioritization strategy.
        Calculates necessary metrics (like CoD) within the strategy execution.
        """
        sorted_features = self.prioritization_strategy.prioritize(self.features, sprint_configs)
        self.features = sorted_features # Update internal state
        return sorted_features

    def build_sequence(self) -> List[UserStory]:
        """
        Build execution sequence from features.
        Replaces UserStorySequencingAgent.
        """
        sequence = []
        for feature in self.features:
            sequence.extend(feature.user_stories)
        return sequence
    
    async def run_negotiation(self, user_stories_sequence: List[UserStory] = None) -> AsyncIterator[PlanningEvent]:
        if user_stories_sequence is None:
            user_stories_sequence = self.build_sequence()
        
        for round_num in range(1, self.max_rounds + 1):
            # Round bookkeeping if needed later
            
            for user_story in user_stories_sequence:
                if user_story.id in self.scheduled_stories: continue
                
                assigned_team_id = user_story.assigned_team
                if not assigned_team_id: continue
                
                team_agent = self.team_agents.get(assigned_team_id)
                if not team_agent:
                    matching_team = next((t for t in self.teams if t.id == assigned_team_id), None)
                    if matching_team: team_agent = self.team_agents.get(matching_team.name)
                if not team_agent: continue
                
                team_name = assigned_team_id
                
                # Emit Proposal Event
                yield ProposalEvent(
                    story_id=user_story.id,
                    story_title=user_story.title,
                    team_id=team_name,
                    iteration="TBD", # Not known yet
                    effort=user_story.get_effort() or 5.0
                )
                
                # Strategy asks Team Agent directly
                suggested_iteration, rejection_reason = self.planning_strategy.find_slot(
                    user_story=user_story,
                    team_agent=team_agent,
                    iterations=self.iterations,
                    scheduled_stories=self.scheduled_stories,
                    scheduled_features=self.scheduled_features
                )

                if suggested_iteration:
                    self._accept_assignment(user_story, assigned_team_id, suggested_iteration, team_agent)
                    
                    yield AssignmentAcceptedEvent(
                        story_id=user_story.id,
                        team_id=team_name,
                        iteration=suggested_iteration,
                        effort=user_story.get_effort() or 5.0,
                        reason="Capacity and dependencies met"
                    )
                else:
                    yield AssignmentRejectedEvent(
                        story_id=user_story.id,
                        team_id=team_name,
                        reason=rejection_reason,
                        suggested_iteration=None
                    )
            
            # End of round logic
        
        yield GapFillingStartEvent()
        self._fill_gaps_with_split_stories()

    def _accept_assignment(self, user_story, team_id, iteration, team_agent):
        assignment = Assignment(
            user_story_id=user_story.id,
            feature_id=user_story.feature_id,
            team_id=team_id,
            iteration=iteration,
            effort=user_story.get_effort() or 5.0,
            status="accepted",
            sequence_order=len(self.assignments) + 1,
            dependency_ready=True,
        )
        self.assignments.append(assignment)
        self.scheduled_stories[user_story.id] = iteration
        if user_story.feature_id not in self.scheduled_features:
            self.scheduled_features[user_story.feature_id] = iteration
        
        if hasattr(team_agent, 'current_assignments'):
            team_agent.current_assignments[iteration] = \
                team_agent.current_assignments.get(iteration, 0) + assignment.effort

    def _fill_gaps_with_split_stories(self):
        pass 

    def get_final_plan(self) -> Dict[str, Any]:
        return {
            "assignments": [a.model_dump() for a in self.assignments if a.status == "accepted"],
            "negotiation_rounds": len(self.negotiation_rounds), # May be 0 now if rounds logic removed
            "messages": len(self.messages),
            "scheduled_stories": self.scheduled_stories,
            "scheduled_features": self.scheduled_features,
        }
