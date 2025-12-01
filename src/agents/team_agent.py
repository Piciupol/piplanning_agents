"""Hybrid Team Agent - combines standard logic with AI capabilities."""
from typing import Dict, Any, List, Optional, Tuple
import re

from src.core.models import Team, Message, UserStory
from src.agents.base_agents import ITeamAgent
from src.utils.config import Config


class TeamAgent(ITeamAgent):
    """Hybrid team agent that uses deterministic logic."""
    
    def __init__(self, team: Team):
        """
        Initialize TeamAgent.
        
        Args:
            team: Team model
        """
        self.team = team
        self.current_assignments: Dict[str, float] = {}  # iteration -> load
        self.memory: List[Message] = []
    
    def find_assignment_slot(
        self,
        user_story: UserStory,
        start_iteration: str,
        iterations: List[str],
        scheduled_stories: Dict[int, str],
        scheduled_features: Dict[int, str]
    ) -> Tuple[Optional[str], str]:
        """
        Find the earliest valid iteration for a user story starting from start_iteration.
        Returns: (iteration_name, reason)
        """
        try:
            start_index = iterations.index(start_iteration)
        except ValueError:
            start_index = 0

        # Check each iteration starting from the proposed one
        for i in range(start_index, len(iterations)):
            iteration = iterations[i]
            response = self.check_capacity_and_dependencies(
                user_story, iteration, scheduled_stories, scheduled_features
            )
            if response.get("can_do"):
                return iteration, response.get("reason", "")

        return None, "No capacity or dependencies met in any future iteration"

    def can_do_user_story(
        self,
        user_story: UserStory,
        iteration: str,
        scheduled_stories: Dict[int, str],
        scheduled_features: Dict[int, str]
    ) -> Dict[str, Any]:
        """Wrapper for backward compatibility or direct check."""
        return self.check_capacity_and_dependencies(user_story, iteration, scheduled_stories, scheduled_features)

    def check_capacity_and_dependencies(
        self,
        user_story: UserStory,
        iteration: str,
        scheduled_stories: Dict[int, str],
        scheduled_features: Dict[int, str]
    ) -> Dict[str, Any]:
        """Deterministic check logic."""
        response = {
            "can_do": False,
            "reason": "",
            "suggested_iteration": None,
            "alternative": None,
        }
        
        # Check 2: Feature Dependencies
        if user_story.depends_on_features:
            missing_feature_deps = []
            for dep_feature_id in user_story.depends_on_features:
                if dep_feature_id not in scheduled_features:
                    missing_feature_deps.append(dep_feature_id)
                else:
                    dep_iter = scheduled_features[dep_feature_id]
                    if not self._is_iteration_before(dep_iter, iteration):
                        missing_feature_deps.append(dep_feature_id)
            
            if missing_feature_deps:
                response["can_do"] = False
                dep_list = ", ".join([f"Feature {d}" for d in missing_feature_deps])
                response["reason"] = f"Nie możemy zacząć - czekamy na zakończenie {dep_list}. Te features muszą być gotowe wcześniej."
                if scheduled_features:
                    latest_dep_iter = max(
                        (scheduled_features[dep_id] for dep_id in user_story.depends_on_features if dep_id in scheduled_features),
                        default=iteration
                    )
                    response["suggested_iteration"] = self._next_iteration(latest_dep_iter)
                return response
        
        # Check 3: User Story Dependencies
        if user_story.depends_on_stories:
            missing_story_deps = []
            for dep_us_id in user_story.depends_on_stories:
                if dep_us_id not in scheduled_stories:
                    missing_story_deps.append(dep_us_id)
                else:
                    dep_iter = scheduled_stories[dep_us_id]
                    # Allow dependencies within the SAME iteration for Stories
                    if not self._is_iteration_before_or_same(dep_iter, iteration):
                        missing_story_deps.append(dep_us_id)
            
            if missing_story_deps:
                response["can_do"] = False
                dep_list = ", ".join([f"Story {d}" for d in missing_story_deps])
                response["reason"] = f"Musimy poczekać na {dep_list} - te user stories muszą być zrobione wcześniej."
                if scheduled_stories:
                    latest_dep_iter = max(
                        (scheduled_stories[dep_id] for dep_id in user_story.depends_on_stories if dep_id in scheduled_stories),
                        default=iteration
                    )
                    response["suggested_iteration"] = self._next_iteration(latest_dep_iter)
                return response
        
        # Check 4: Capacity (with buffer)
        current_load = self.current_assignments.get(iteration, 0)
        # Use capacity_per_sprint if available, otherwise fallback to capacity_per_iteration
        capacity = None
        if self.team.capacity_per_sprint and iteration in self.team.capacity_per_sprint:
            sprint_capacity = self.team.capacity_per_sprint[iteration]
            # Handle both dict and int formats
            if isinstance(sprint_capacity, dict):
                capacity = sprint_capacity.get("total", None)
            else:
                capacity = sprint_capacity
        
        # Fallback to capacity_per_iteration if capacity_per_sprint not found
        if capacity is None:
            capacity = self.team.capacity_per_iteration if hasattr(self.team, 'capacity_per_iteration') else 40
        
        buffer = Config.CAPACITY_BUFFER
        max_allowed_capacity = capacity * (1.0 - buffer)
        available_capacity = max_allowed_capacity - current_load
        required_effort = user_story.get_effort() or 5.0
        
        if required_effort <= available_capacity:
            response["can_do"] = True
            response["reason"] = f"Mamy jeszcze {available_capacity:.1f} SP wolnego miejsca w {iteration}. Możemy to wziąć!"
        else:
            response["can_do"] = False
            response["reason"] = f"Nie mamy wystarczającej pojemności w {iteration}. Mamy {available_capacity:.1f} SP dostępne (max {max_allowed_capacity:.1f} SP z buforem {buffer*100:.0f}%), a potrzeba {required_effort:.1f} SP. Proponuję przenieść na późniejszą iterację."
            response["suggested_iteration"] = self._find_next_available_iteration(
                iteration,
                required_effort,
                scheduled_stories
            )
        
        return response

    def get_capacity_status(self, iteration: str) -> Dict[str, Any]:
        """Get current capacity status for an iteration."""
        current_load = self.current_assignments.get(iteration, 0)
        available = self.team.capacity_per_iteration - current_load
        utilization = (current_load / self.team.capacity_per_iteration * 100) if self.team.capacity_per_iteration > 0 else 0
        
        # Get capacity for this iteration
        if self.team.capacity_per_sprint and iteration in self.team.capacity_per_sprint:
            sprint_capacity = self.team.capacity_per_sprint[iteration]
            capacity = sprint_capacity.get("total", self.team.capacity_per_iteration)
        else:
            capacity = self.team.capacity_per_iteration
        
        return {
            "team_id": self.team.id,
            "iteration": iteration,
            "current_load": current_load,
            "capacity": capacity,
            "available": capacity - current_load,
            "utilization_percent": (current_load / capacity * 100) if capacity > 0 else 0,
        }

    def _is_iteration_before(self, iter1: str, iter2: str) -> bool:
        match1 = re.search(r'\d+', iter1)
        match2 = re.search(r'\d+', iter2)
        num1 = int(match1.group()) if match1 else 999
        num2 = int(match2.group()) if match2 else 999
        return num1 < num2

    def _is_iteration_before_or_same(self, iter1: str, iter2: str) -> bool:
        match1 = re.search(r'\d+', iter1)
        match2 = re.search(r'\d+', iter2)
        num1 = int(match1.group()) if match1 else 999
        num2 = int(match2.group()) if match2 else 999
        return num1 <= num2
    
    def _next_iteration(self, iteration: str) -> str:
        match = re.search(r'(\d+)', iteration)
        if match:
            num = int(match.group())
            return iteration.replace(str(num), str(num + 1))
        return iteration
    
    def _find_next_available_iteration(
        self,
        current_iteration: str,
        required_effort: float,
        scheduled_stories: Dict[int, str]
    ) -> str:
        return self._next_iteration(current_iteration)
