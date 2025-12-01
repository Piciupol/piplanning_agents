"""Hybrid Risk Agent - identifies risks using standard rules and AI."""
from typing import List, Dict
import uuid
import json
from datetime import datetime, timezone

from src.core.models import Feature, Assignment, Team, Risk, RiskLevel
from src.agents.base_agents import IRiskAgent
from src.agents.ai_agent_base import AIAgentBase


class RiskAgent(AIAgentBase, IRiskAgent):
    """Hybrid agent for identifying risks."""
    
    def identify_risks(
        self,
        features: List[Feature],
        assignments: List[Assignment],
        teams: List[Team],
        team_agents: Dict[str, any] = None,
        iterations: List[str] = None
    ) -> List[Risk]:
        """
        Identify risks.
        Uses standard rules first, then AI to find qualitative risks.
        """
        # 1. Standard deterministic risks
        risks = self._identify_standard_risks(features, assignments, teams, team_agents)
        
        # 2. AI qualitative analysis
        ai_risks = self._identify_ai_risks(features, assignments, teams, risks, iterations)
        risks.extend(ai_risks)
            
        return risks

    def _identify_standard_risks(
        self,
        features: List[Feature],
        assignments: List[Assignment],
        teams: List[Team],
        team_agents: Dict[str, any] = None
    ) -> List[Risk]:
        """Identify risks using deterministic rules."""
        risks = []
        accepted_assignments = [a for a in assignments if a.status == "accepted"]
        
        # Risk 1: Unresolved dependencies
        for feature in features:
            if feature.depends_on_features:
                for dep_id in feature.depends_on_features:
                    dep_assigned = any(
                        a.feature_id == dep_id and a.status == "accepted"
                        for a in accepted_assignments
                    )
                    
                    if not dep_assigned:
                        risk = Risk(
                            id=f"risk-dep-{feature.id}-{dep_id}",
                            title=f"Unresolved dependency: Feature {dep_id} not in plan",
                            description=f"Feature {feature.id} ({feature.title}) depends on Feature {dep_id} which is not assigned",
                            probability=0.8,
                            impact=RiskLevel.HIGH,
                            risk_score=0.8 * 3.0,
                            mitigation="Ensure dependent feature is included in PI plan",
                            related_features=[feature.id, dep_id],
                            status="identified"
                        )
                        risks.append(risk)
        
        # Risk 2: Capacity overcommitment
        if teams:
            team_iteration_load: Dict[tuple, float] = {}
            
            for assignment in accepted_assignments:
                key = (assignment.team_id, assignment.iteration)
                team_iteration_load[key] = team_iteration_load.get(key, 0) + assignment.effort
            
            for team in teams:
                # Find all iterations this team is working in
                iterations = set(a.iteration for a in accepted_assignments if a.team_id == team.id)
                for iteration in iterations:
                    key = (team.id, iteration)
                    load = team_iteration_load.get(key, 0)
                    capacity = team.capacity_per_iteration
                    
                    if load > capacity:
                        overcommit = ((load / capacity) - 1) * 100
                        risk_level = RiskLevel.CRITICAL if overcommit > 20 else RiskLevel.HIGH
                        
                        risk = Risk(
                            id=f"risk-capacity-{team.id}-{iteration}",
                            title=f"Overcommitment: {team.name} in {iteration}",
                            description=f"Team {team.name} is overcommitted by {overcommit:.1f}% ({load:.1f}/{capacity} SP)",
                            probability=0.9 if overcommit > 20 else 0.7,
                            impact=risk_level,
                            risk_score=(0.9 if overcommit > 20 else 0.7) * (4.0 if overcommit > 20 else 3.0),
                            mitigation="Reduce scope or increase capacity",
                            owner=team.id,
                            status="identified"
                        )
                        risks.append(risk)
        
        # Risk 3: Features without assignments
        # Filter assignments that have feature_id set (should be all, but be safe)
        assignments_with_feature = [a for a in accepted_assignments if hasattr(a, 'feature_id') and a.feature_id is not None]
        assigned_feature_ids = {a.feature_id for a in assignments_with_feature}
        
        # Also check if features have any user stories assigned
        # A feature is considered assigned if at least one of its user stories is assigned
        assigned_user_story_ids = {a.user_story_id for a in assignments_with_feature if hasattr(a, 'user_story_id')}
        
        unassigned_features = []
        for feature in features:
            # Check if feature itself is assigned (has assignments with this feature_id)
            if feature.id not in assigned_feature_ids:
                # Also check if any user story from this feature is assigned
                feature_user_stories = feature.user_stories or []
                feature_has_assigned_stories = any(
                    us.id in assigned_user_story_ids 
                    for us in feature_user_stories
                ) if feature_user_stories else False
                
                # If no user stories are assigned, feature is unassigned
                # Also consider feature unassigned if it has no user stories at all
                if not feature_has_assigned_stories:
                    unassigned_features.append(feature)
        
        if unassigned_features:
            # Create individual risk for each unassigned feature, or group them
            if len(unassigned_features) == 1:
                f = unassigned_features[0]
                risk = Risk(
                    id=f"risk-unassigned-feature-{f.id}",
                    title=f"Feature {f.id} not assigned: {f.title[:50]}",
                    description=f"Feature {f.id} ({f.title}) has no user stories assigned to any team/iteration",
                    probability=1.0,
                    impact=RiskLevel.MEDIUM,
                    risk_score=1.0 * 2.0,
                    mitigation="Assign feature to a team/iteration or move to next PI",
                    related_features=[f.id],
                    status="identified"
                )
                risks.append(risk)
            else:
                # Group multiple unassigned features
                risk = Risk(
                    id=f"risk-unassigned-features",
                    title=f"{len(unassigned_features)} features not assigned",
                    description=f"{len(unassigned_features)} features have no user stories assigned to any team/iteration: {', '.join([f'{f.id} ({f.title[:30]})' for f in unassigned_features[:5]])}{'...' if len(unassigned_features) > 5 else ''}",
                    probability=1.0,
                    impact=RiskLevel.MEDIUM,
                    risk_score=1.0 * 2.0,
                    mitigation="Assign features to teams/iterations or move to next PI",
                    related_features=[f.id for f in unassigned_features],
                    status="identified"
                )
                risks.append(risk)
        
        return risks

    def _identify_ai_risks(
        self,
        features: List[Feature],
        assignments: List[Assignment],
        teams: List[Team],
        standard_risks: List[Risk],
        iterations: List[str] = None
    ) -> List[Risk]:
        """Use AI to identify qualitative risks."""
        # Prepare comprehensive context
        # Features: Include all features with full details
        features_ctx = []
        for f in features:
            feat_data = {
                "id": f.id,
                "title": f.title,
                "description": f.description or "",
                "effort": f.effort,
                "user_stories_count": len(f.user_stories) if f.user_stories else 0,
                "deadline_sprint": f.deadline_sprint if hasattr(f, 'deadline_sprint') else None,
                "depends_on_features": f.depends_on_features if hasattr(f, 'depends_on_features') else []
            }
            features_ctx.append(feat_data)
        
        # Teams: Include capacity per sprint if available
        teams_ctx = []
        for t in teams:
            team_data = {
                "id": t.id,
                "name": t.name,
                "capacity_per_iteration": t.capacity_per_iteration if hasattr(t, 'capacity_per_iteration') else 40
            }
            # Add capacity per sprint if available
            if hasattr(t, 'capacity_per_sprint') and t.capacity_per_sprint:
                team_data["capacity_per_sprint"] = {}
                for sprint_name, sprint_cap in t.capacity_per_sprint.items():
                    if isinstance(sprint_cap, dict):
                        team_data["capacity_per_sprint"][sprint_name] = sprint_cap.get("total", team_data["capacity_per_iteration"])
                    else:
                        team_data["capacity_per_sprint"][sprint_name] = sprint_cap
            teams_ctx.append(team_data)
        
        # Assignments: Include all assignments with full details
        assignments_ctx = []
        for a in assignments:
            if a.status == "accepted":
                assign_data = {
                    "user_story_id": a.user_story_id,
                    "feature_id": a.feature_id,
                    "team": a.team_id,
                    "iteration": a.iteration,
                    "effort": a.effort,
                    "sequence_order": a.sequence_order
                }
                assignments_ctx.append(assign_data)
        
        # Calculate utilization per team per iteration
        utilization_ctx = {}
        if iterations:
            for team in teams:
                team_id = team.id
                utilization_ctx[team_id] = {}
                for iteration in iterations:
                    team_assignments = [a for a in assignments_ctx if a["team"] == team.name and a["iteration"] == iteration]
                    total_effort = sum(a["effort"] for a in team_assignments)
                    
                    # Get capacity for this iteration
                    capacity = team.capacity_per_iteration
                    if hasattr(team, 'capacity_per_sprint') and team.capacity_per_sprint and iteration in team.capacity_per_sprint:
                        sprint_cap = team.capacity_per_sprint[iteration]
                        if isinstance(sprint_cap, dict):
                            capacity = sprint_cap.get("total", capacity)
                        else:
                            capacity = sprint_cap
                    
                    utilization = (total_effort / capacity * 100) if capacity > 0 else 0
                    utilization_ctx[team_id][iteration] = {
                        "used": total_effort,
                        "capacity": capacity,
                        "utilization_percent": round(utilization, 1)
                    }
        
        # Count unassigned features
        assigned_feature_ids = {a["feature_id"] for a in assignments_ctx}
        unassigned_features_count = len([f for f in features if f.id not in assigned_feature_ids])
        
        system_prompt = """You are a Risk Manager in SAFe. 
    Analyze the PI Plan and identify qualitative risks (e.g. complexity, team experience, tight schedule, unclear requirements, dependencies, capacity issues).
    Do NOT report obvious quantitative risks like 'overcapacity' or 'missing dependency' as they are already checked by standard rules.
    Focus on strategic, organizational, and process risks."""
        
        user_prompt = f"""PI Plan Context:
    Total Features: {len(features)}
    Unassigned Features: {unassigned_features_count}
    Total Teams: {len(teams)}
    Total Assignments: {len(assignments_ctx)}
    Iterations: {iterations if iterations else 'Not specified'}
    
    Features ({len(features)} total): {json.dumps(features_ctx, indent=2, default=str)}
    
    Teams: {json.dumps(teams_ctx, indent=2, default=str)}
    
    Team Utilization per Iteration: {json.dumps(utilization_ctx, indent=2, default=str)}
    
    Assignments Sample (showing first 20): {json.dumps(assignments_ctx[:20], indent=2, default=str)}
    
    Already Identified Standard Risks: {[r.title for r in standard_risks]}
    
    Analyze this plan and identify 3-5 additional QUALITATIVE risks that are not already covered.
    Consider: team workload distribution, feature complexity, dependencies, schedule tightness, resource constraints, coordination challenges.
    
    Return JSON array:
    [
      {{
        "title": "Risk Title",
        "description": "Detailed explanation of why this is a risk",
        "probability": 0.5,
        "impact": "high/medium/low",
        "mitigation": "Recommended action to mitigate"
      }}
    ]"""
        
        response = self.call_llm(system_prompt, user_prompt, temperature=1.0)
        
        ai_risks = []
        if response:
            try:
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                if json_start >= 0:
                    data = json.loads(response[json_start:json_end])
                    for i, r in enumerate(data):
                        impact_enum = RiskLevel.MEDIUM
                        if r["impact"].lower() == "high": impact_enum = RiskLevel.HIGH
                        elif r["impact"].lower() == "critical": impact_enum = RiskLevel.CRITICAL
                        elif r["impact"].lower() == "low": impact_enum = RiskLevel.LOW
                        
                        risk = Risk(
                            id=f"risk-ai-{i}-{uuid.uuid4().hex[:4]}",
                            title=r["title"],
                            description=r["description"],
                            probability=r.get("probability", 0.5),
                            impact=impact_enum,
                            risk_score=r.get("probability", 0.5) * 3.0,
                            mitigation=r.get("mitigation", ""),
                            status="identified"
                        )
                        ai_risks.append(risk)
            except:
                pass
        
        return ai_risks
