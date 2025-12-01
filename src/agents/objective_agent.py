"""Hybrid Objective Agent - generates PI Objectives using Standard heuristics and AI."""
import json
import uuid
from typing import List
from src.core.models import Feature, Team, PIObjective
from src.agents.base_agents import IObjectiveAgent
from src.agents.ai_agent_base import AIAgentBase


class ObjectiveAgent(AIAgentBase, IObjectiveAgent):
    """Hybrid agent for generating PI Objectives."""
    
    def generate_objectives(
        self,
        features: List[Feature],
        teams: List[Team]
    ) -> List[PIObjective]:
        """
        Generate PI Objectives.
        """
        return self._generate_with_ai(features, teams)
            
    def _generate_standard(self, features: List[Feature], teams: List[Team]) -> List[PIObjective]:
        """Standard grouping logic."""
        objectives = []
        
        # Group features by priority
        critical_features = [f for f in features if f.priority.value == "critical"]
        high_features = [f for f in features if f.priority.value == "high"]
        medium_features = [f for f in features if f.priority.value == "medium"]
        
        # Objective 1: Critical features
        if critical_features:
            obj = PIObjective(
                id=f"obj-{uuid.uuid4().hex[:8]}",
                title="Deliver Critical Business Features",
                description=f"Complete {len(critical_features)} critical priority features",
                business_value=9.0,
                features=[f.id for f in critical_features],
                team_commitments={team.id: False for team in teams},
                status="draft"
            )
            objectives.append(obj)
        
        # Objective 2: High priority features
        if high_features:
            obj = PIObjective(
                id=f"obj-{uuid.uuid4().hex[:8]}",
                title="Deliver High Priority Features",
                description=f"Complete {len(high_features)} high priority features",
                business_value=7.0,
                features=[f.id for f in high_features],
                team_commitments={team.id: False for team in teams},
                status="draft"
            )
            objectives.append(obj)
        
        # Objective 3: Medium priority features (if many)
        if len(medium_features) >= 3:
            obj = PIObjective(
                id=f"obj-{uuid.uuid4().hex[:8]}",
                title="Deliver Medium Priority Features",
                description=f"Complete {len(medium_features)} medium priority features",
                business_value=5.0,
                features=[f.id for f in medium_features],
                team_commitments={team.id: False for team in teams},
                status="draft"
            )
            objectives.append(obj)
        
        return objectives

    def _generate_with_ai(self, features: List[Feature], teams: List[Team]) -> List[PIObjective]:
        """Use AI to generate intelligent PI Objectives."""
        # Limit to top features by business value/WSJF to reduce prompt size
        # Sort by WSJF score (if available) or business value
        sorted_features = sorted(
            features, 
            key=lambda f: (f.wsjf_score if hasattr(f, 'wsjf_score') and f.wsjf_score else 0, f.business_value or 0),
            reverse=True
        )
        # Take top 15 features to keep prompt manageable
        top_features = sorted_features[:15]
        
        # Simplify feature data - only essential fields
        features_json = json.dumps([
            {
                "id": f.id,
                "title": f.title[:100],  # Limit title length
                "business_value": f.business_value,
                "priority": f.priority.value if hasattr(f, 'priority') else "medium"
            }
            for f in top_features
        ], indent=2)
        
        # Add summary if there are more features
        total_features = len(features)
        if total_features > len(top_features):
            features_summary = f"\nNote: Showing top {len(top_features)} of {total_features} features by priority/business value."
        else:
            features_summary = ""
        
        system_prompt = """You are a Program Manager creating PI Objectives for a SAFe Program Increment.
    Group features into meaningful business objectives that align with strategic goals.
    Each objective should have clear business value and measurable outcomes."""
        
        user_prompt = f"""Features to organize:
    {features_json}{features_summary}
    
    Create 3-5 PI Objectives that:
    1. Group related features by business value/theme
    2. Have clear, measurable outcomes
    3. Align with strategic goals
    4. Have business value scores (1-10)
    
    Focus on the features provided above. If there are additional features not shown, you can create objectives that would logically include them based on themes.
    
    Return JSON array:
    [
      {{
        "title": "Objective title",
        "description": "Objective description",
        "business_value": 9.0,
        "feature_ids": [1, 2, 3],
        "metrics": {{"key_metric": "target_value"}}
      }},
      ...
    ]"""
        
        # Log prompt size for debugging
        prompt_size = len(system_prompt) + len(user_prompt)
        print(f"DEBUG: Objective agent prompt size: {prompt_size} characters")
        print(f"DEBUG: Features in prompt: {len(top_features)} of {len(features)} total")
        
        response = self.call_llm(system_prompt, user_prompt, temperature=1.0, max_tokens=4000)
        
        print(f"DEBUG: Objective agent response received: {bool(response)}, length: {len(response) if response else 0}")
        
        if response:
            try:
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    objectives_data = json.loads(json_str)
                    
                    objectives = []
                    for obj_data in objectives_data:
                        obj = PIObjective(
                            id=f"obj-{uuid.uuid4().hex[:8]}",
                            title=obj_data.get("title", "Untitled Objective"),
                            description=obj_data.get("description", ""),
                            business_value=float(obj_data.get("business_value", 5.0)),
                            features=obj_data.get("feature_ids", []),
                            team_commitments={team.id: False for team in teams},
                            status="draft",
                            metrics=obj_data.get("metrics")
                        )
                        objectives.append(obj)
                    
                    return objectives
            except Exception as e:
                print(f"Error parsing AI response: {e}, using standard grouping")
        
        return self._generate_standard(features, teams)
