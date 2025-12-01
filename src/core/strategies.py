"""Strategy definitions for Planning and Prioritization."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.core.models import Feature, UserStory, Team, Assignment

# --- 1. Feature Prioritization Strategies ---

class PrioritizationStrategy(ABC):
    """Abstract base class for feature prioritization logic."""
    
    @abstractmethod
    def prioritize(self, features: List[Feature], sprint_configs: Dict[str, Any] = None) -> List[Feature]:
        """Sort features based on specific criteria."""
        pass

class StandardPrioritization(PrioritizationStrategy):
    """
    Current logic: 
    1. Target Date (Earliest Milestone)
    2. Deadline Sprint
    3. Cost of Delay / WSJF
    """
    def prioritize(self, features: List[Feature], sprint_configs: Dict[str, Any] = None) -> List[Feature]:
        
        # 1. Prepare metrics (Calculate CoD/WSJF if missing)
        for feature in features:
            # Default Business Value
            if not feature.business_value:
                feature.business_value = 100.0
            
            # Determine urgency boost based on deadline
            urgency_boost = 1.0
            if feature.deadline_sprint:
                try:
                    sprint_num = int(''.join(filter(str.isdigit, feature.deadline_sprint)) or '999')
                    if sprint_num <= 2:
                        urgency_boost = 2.0
                    elif sprint_num <= 4:
                        urgency_boost = 1.5
                except: pass
            
            # Calculate CoD
            feature.cost_of_delay = (feature.business_value or 0) * urgency_boost
            
            # Calculate Score = CoD / Effort (Standard WSJF formula)
            effort = feature.effort or 1.0
            feature.wsjf_score = feature.cost_of_delay / effort

        # 2. Sort
        def sort_key(f: Feature) -> tuple:
            # 1. Target Date
            target_date_priority = float('inf')
            if f.milestones:
                milestone_dates = [m.target_date for m in f.milestones if m.target_date]
                if milestone_dates:
                    earliest_date = min(milestone_dates)
                    if isinstance(earliest_date, str):
                        try:
                            earliest_date = datetime.fromisoformat(earliest_date.replace('Z', '+00:00'))
                        except: pass
                    if hasattr(earliest_date, 'timestamp'):
                        target_date_priority = earliest_date.timestamp()
            
            # 2. Deadline Sprint
            deadline_priority = 999
            if f.deadline_sprint:
                try:
                    deadline_priority = int(''.join(filter(str.isdigit, f.deadline_sprint)) or '999')
                except: pass
            
            # 3. Cost of Delay (Negative because we want Descending order for value)
            cost_of_delay = -(f.cost_of_delay or 0)
            
            return (target_date_priority, deadline_priority, cost_of_delay)
            
        return sorted(features, key=sort_key)


# --- 2. Planning/Assignment Strategies ---

class PlanningStrategy(ABC):
    """Abstract base class for assigning stories to iterations."""
    
    @abstractmethod
    def find_slot(self, 
                  user_story: UserStory, 
                  team_agent: Any,  # Expects ITeamAgent interface
                  iterations: List[str],
                  scheduled_stories: Dict[int, str],
                  scheduled_features: Dict[int, str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the best iteration for a user story by asking the TeamAgent.
        Returns: (iteration_name, rejection_reason)
        """
        pass

class DependencyAwarePlanningStrategy(PlanningStrategy):
    """
    Calculates the earliest possible start based on dependencies, 
    then asks the Team Agent to find the best slot from there onwards.
    """
    def find_slot(self, 
                  user_story: UserStory, 
                  team_agent: Any, 
                  iterations: List[str],
                  scheduled_stories: Dict[int, str],
                  scheduled_features: Dict[int, str]) -> Tuple[Optional[str], Optional[str]]:
        
        # Determine the earliest possible start iteration based on dependencies
        start_index = 0
        
        # 1. Check Feature Dependencies (Must be completed BEFORE current iteration)
        if user_story.depends_on_features:
            for dep_id in user_story.depends_on_features:
                if dep_id in scheduled_features:
                    dep_iter = scheduled_features[dep_id]
                    if dep_iter in iterations:
                        # Must be strictly after the feature's iteration
                        idx = iterations.index(dep_iter)
                        start_index = max(start_index, idx + 1)

        # 2. Check Story Dependencies (Can be in SAME iteration or later)
        if user_story.depends_on_stories:
            for dep_id in user_story.depends_on_stories:
                if dep_id in scheduled_stories:
                    dep_iter = scheduled_stories[dep_id]
                    if dep_iter in iterations:
                        # Can be same iteration
                        idx = iterations.index(dep_iter)
                        start_index = max(start_index, idx)
        
        # If dependencies push us beyond available iterations, reject early
        if start_index >= len(iterations):
            return None, "Dependencies push start date beyond available iterations"
            
        start_iteration = iterations[start_index]
        
        # Delegate the full search to the Team Agent starting from the calculated constraint
        return team_agent.find_assignment_slot(
            user_story=user_story,
            start_iteration=start_iteration,
            iterations=iterations,
            scheduled_stories=scheduled_stories,
            scheduled_features=scheduled_features
        )
