"""Hybrid Reporting Agent - generates reports and AI insights."""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import uuid
import json

from src.core.models import Feature, Team, Assignment, ProgramBoard, Transcript, Message, PIObjective, Risk
from src.agents.ai_agent_base import AIAgentBase
from src.agents.base_agents import IReportingAgent


class ReportingAgent(AIAgentBase, IReportingAgent):
    """Hybrid agent responsible for generating reports and providing AI insights."""
    
    def generate_program_board(
        self,
        project: str,
        pi_start: str,
        iterations: List[str],
        teams: List[Team],
        features: List[Feature],
        assignments: List[Assignment],
        negotiation_rounds: int,
        pi_objectives: List[PIObjective] = None,
        risks: List[Risk] = None
    ) -> ProgramBoard:
        """
        Generate final program board.
        """
        board = ProgramBoard(
            project=project,
            pi_start=pi_start,
            iterations=iterations,
            teams=teams,
            assignments=assignments,
            features=features,
            pi_objectives=pi_objectives or [],
            risks=risks or [],
            negotiation_rounds=negotiation_rounds,
        )
        
        # Generate AI insights (AI capabilities handled by base class)
        insights_json = self._generate_insights(board, teams, features, assignments)
        print(f"\nAI Insights:\n{insights_json}")
        
        # Parse and store insights in board
        try:
            insights_dict = json.loads(insights_json) if isinstance(insights_json, str) else insights_json
            board.ai_insights = insights_dict
        except:
            # If parsing fails, store as string
            board.ai_insights = {"raw": insights_json}
            
        return board
    
    def generate_transcript(
        self,
        session_id: str,
        start_time: datetime,
        messages: List[Message],
        final_plan: Optional[ProgramBoard] = None
    ) -> Transcript:
        """
        Generate conversation transcript.
        """
        return Transcript(
            session_id=session_id,
            start_time=start_time,
            end_time=datetime.now(timezone.utc),
            messages=messages,
            final_plan=final_plan,
        )

    def _generate_insights(
        self,
        board: ProgramBoard,
        teams: List[Team],
        features: List[Feature],
        assignments: List[Assignment]
    ) -> str:
        """Generate AI insights about the plan."""
        # Calculate utilization per team per iteration
        team_utilization = {}
        for team in teams:
            team_utilization[team.name] = {}
            for iter_name in board.iterations:
                utilization = self._calculate_utilization(team.name, iter_name, assignments, teams)
                team_utilization[team.name][iter_name] = utilization
        
        # Count unassigned features
        assigned_feature_ids = {a.feature_id for a in assignments if a.feature_id}
        unassigned_features = [f for f in features if f.id not in assigned_feature_ids]
        
        # Calculate total effort per iteration
        effort_per_iteration = {}
        for iteration in board.iterations:
            effort_per_iteration[iteration] = sum(
                a.effort for a in assignments if a.iteration == iteration
            )
        
        # Team details with capacity
        team_details = []
        for team in teams:
            team_info = {
                "name": team.name,
                "id": team.id,
                "capacity_per_iteration": team.capacity_per_iteration if hasattr(team, 'capacity_per_iteration') else 40
            }
            if hasattr(team, 'capacity_per_sprint') and team.capacity_per_sprint:
                team_info["capacity_per_sprint"] = {}
                for sprint_name, sprint_cap in team.capacity_per_sprint.items():
                    if isinstance(sprint_cap, dict):
                        team_info["capacity_per_sprint"][sprint_name] = sprint_cap.get("total", team_info["capacity_per_iteration"])
                    else:
                        team_info["capacity_per_sprint"][sprint_name] = sprint_cap
            team_details.append(team_info)
        
        context = {
            "assignments_count": len(assignments),
            "features_count": len(features),
            "unassigned_features_count": len(unassigned_features),
            "teams_count": len(teams),
            "iterations": board.iterations,
            "iterations_count": len(board.iterations),
            "team_utilization": team_utilization,
            "effort_per_iteration": effort_per_iteration,
            "team_details": team_details,
            "risks_count": len(board.risks) if board.risks else 0,
            "objectives_count": len(board.pi_objectives) if board.pi_objectives else 0,
            "average_assignments_per_feature": round(len(assignments) / len(features), 1) if features else 0
        }
        
        system_prompt = """You are a Program Manager analyzing a PI plan.
    Provide key insights, recommendations, and potential issues.
    Be specific and actionable in your observations."""
        
        user_prompt = f"""PI Plan Summary:
    {json.dumps(context, indent=2, default=str)}
    
    Analyze this plan and provide insights:
    1. Key observations (what stands out?)
    2. Potential issues (what could go wrong?)
    3. Recommendations (what should be done?)
    4. Success factors (what will make this plan successful?)
    
    Return JSON:
    {{
      "observations": ["insight 1", "insight 2"],
      "issues": ["issue 1", "issue 2"],
      "recommendations": ["rec 1", "rec 2"],
      "success_factors": ["factor 1", "factor 2"]
    }}"""
        
        # Check if AI is available
        if not self.client:
            print("DEBUG: AI client not available - insights generation skipped")
            return "No insights generated"
        
        # Estimate context size
        context_size = len(json.dumps(context, default=str))
        print(f"DEBUG: Context size: {context_size} characters")
        
        response = self.call_llm(system_prompt, user_prompt, temperature=1.0, max_tokens=8000)
        
        if not response:
            print("DEBUG: call_llm returned None - AI may not be configured or error occurred")
            return "No insights generated"
        
        print(f"DEBUG: LLM response length: {len(response)}")
        if len(response) == 0:
            print("DEBUG: WARNING - LLM returned empty string. This may indicate:")
            print("DEBUG: 1. Model returned empty response")
            print("DEBUG: 2. Response was filtered/blocked")
            print("DEBUG: 3. max_tokens too small (but should not cause empty response)")
            return "No insights generated"
        
        print(f"DEBUG: LLM response preview: {response[:500]}...")
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                insights = json.loads(json_str)
                print(f"DEBUG: Successfully parsed insights JSON")
                return json.dumps(insights, indent=2)
            else:
                print(f"DEBUG: Could not find JSON in response. json_start={json_start}, json_end={json_end}")
                print(f"DEBUG: Full response: {response}")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Error parsing AI insights JSON: {e}")
            print(f"DEBUG: JSON string attempted: {response[json_start:json_end] if json_start >= 0 else 'N/A'}")
        except Exception as e:
            print(f"DEBUG: Unexpected error parsing AI insights: {e}")
            import traceback
            traceback.print_exc()
        
        return "No insights generated"
    
    def _calculate_utilization(
        self,
        team_name: str,
        iteration: str,
        assignments: List[Assignment],
        teams: List[Team]
    ) -> float:
        """Calculate team utilization for iteration."""
        # Find team by name (assignments use team.name, not team.id)
        team = next((t for t in teams if t.name == team_name), None)
        if not team:
            return 0.0
        
        # Sum effort for this team in this iteration
        assigned_effort = sum(
            a.effort for a in assignments
            if a.team_id == team_name and a.iteration == iteration
        )
        
        # Get capacity for this iteration
        capacity = team.capacity_per_iteration if hasattr(team, 'capacity_per_iteration') else 40
        
        # Use capacity_per_sprint if available for this iteration
        if hasattr(team, 'capacity_per_sprint') and team.capacity_per_sprint and iteration in team.capacity_per_sprint:
            sprint_capacity = team.capacity_per_sprint[iteration]
            if isinstance(sprint_capacity, dict):
                capacity = sprint_capacity.get("total", capacity)
            else:
                capacity = sprint_capacity
        
        return (assigned_effort / capacity * 100) if capacity > 0 else 0.0
