"""Dependency Agent - detects and manages cross-team dependencies."""
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid

from src.core.models import Feature, Assignment, Message


class DependencyAgent:
    """Agent responsible for detecting and managing dependencies."""
    
    def __init__(self):
        """Initialize DependencyAgent."""
        self.dependencies: Dict[int, List[int]] = {}  # feature_id -> [dependent_feature_ids]
    
    def analyze_dependencies(self, features: List[Feature]) -> Dict[str, Any]:
        """
        Analyze dependencies between features.
        
        Args:
            features: List of features
            
        Returns:
            Analysis results
        """
        # Build dependency graph
        for feature in features:
            if feature.depends_on_features:
                self.dependencies[feature.id] = feature.depends_on_features
        
        # Detect cross-team dependencies (will be checked after assignments)
        return {
            "total_dependencies": sum(len(deps) for deps in self.dependencies.values()),
        }
    
    def check_assignment_dependencies(
        self,
        assignments: List[Assignment],
        features: List[Feature]
    ) -> List[Message]:
        """
        Check if assignments create cross-team dependencies.
        
        Args:
            assignments: List of assignments
            features: List of features
            
        Returns:
            List of warning messages
        """
        messages = []
        
        # Build feature -> team mapping
        feature_team = {a.feature_id: a.team_id for a in assignments}
        
        # Build assignments map feature_id -> assignment
        assignments_map = {a.feature_id: a for a in assignments}
        
        # Build features map
        features_map = {f.id: f for f in features}
        
        # Check each assignment
        for assignment in assignments:
            # Check feature-level dependencies
            feature = features_map.get(assignment.feature_id)
            if feature:
                for dep_id in feature.depends_on_features:
                    if dep_id in assignments_map:
                        dep_assignment = assignments_map[dep_id]
                        
                        # Check order (dependency should be same or earlier iteration)
                        # Simple check: extract numbers from "Iteration X"
                        import re
                        curr_iter_match = re.search(r'\d+', assignment.iteration)
                        dep_iter_match = re.search(r'\d+', dep_assignment.iteration)
                        
                        if curr_iter_match and dep_iter_match:
                            curr_iter = int(curr_iter_match.group())
                            dep_iter = int(dep_iter_match.group())
                            
                            if dep_iter > curr_iter:
                                # Dependency scheduled AFTER dependent item
                                message = Message(
                                    message_id=str(uuid.uuid4()),
                                    timestamp=datetime.now(timezone.utc),
                                    from_agent="DependencyAgent",
                                    to_agent="ProgramManager",
                                    message_type="dependency_violation",
                                    payload={
                                        "feature_id": feature.id,
                                        "depends_on": dep_id,
                                        "issue": f"Dependency scheduled in Iteration {dep_iter}, but dependent item in Iteration {curr_iter}",
                                        "severity": "high",
                                    },
                                )
                                messages.append(message)
                        
                        # Check cross-team
                        if dep_assignment.team_id != assignment.team_id:
                            message = Message(
                                message_id=str(uuid.uuid4()),
                                timestamp=datetime.now(timezone.utc),
                                from_agent="DependencyAgent",
                                to_agent="ProgramManager",
                                message_type="dependency_warning",
                                payload={
                                    "feature_id": feature.id,
                                    "depends_on": dep_id,
                                    "feature_team": assignment.team_id,
                                    "dependency_team": dep_assignment.team_id,
                                    "issue": "Cross-team dependency",
                                    "severity": "medium",
                                },
                            )
                            messages.append(message)
        
        return messages
