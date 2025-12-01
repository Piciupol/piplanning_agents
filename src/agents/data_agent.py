"""Data Agent - fetches and normalizes data from ADO."""
import json
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from src.core.models import Feature, Team, Priority, UserStory, FeatureStatus

if TYPE_CHECKING:
    from src.integrations.ado_client import ADOClient


class DataAgent:
    """Agent responsible for fetching and normalizing data."""
    
    def __init__(self, ado_client: Optional['ADOClient'] = None):
        """
        Initialize DataAgent.
        
        Args:
            ado_client: Optional ADO client instance
        """
        if ado_client:
            self.ado_client = ado_client
        else:
            from src.integrations.ado_client import ADOClient
            self.ado_client = ADOClient()
    
    def fetch_features(
        self,
        project: str,
        area_path: Optional[str] = None,
        iteration_path: Optional[str] = None,
        use_mock: bool = False,
        query_id: Optional[str] = None
    ) -> List[Feature]:
        """
        Fetch features from ADO or use mock data.
        
        Args:
            project: Project name
            area_path: Optional area path filter (e.g., "GN\\Applications\\SWART\\Team Ivy")
            iteration_path: Optional iteration path filter (e.g., "GN\\2026 Q1 PI")
            use_mock: Force use of mock data
            
        Returns:
            List of Feature objects
        """
        if use_mock or not self.ado_client.is_connected():
            return self._load_mock_features()
        
        return self.ado_client.fetch_features(project, area_path, iteration_path, query_id=query_id)
    
    def fetch_teams(self, project: str, use_mock: bool = False) -> List[Team]:
        """
        Fetch teams from ADO or use mock data.
        
        Args:
            project: Project name
            use_mock: Force use of mock data
            
        Returns:
            List of Team objects
        """
        if use_mock or not self.ado_client.is_connected():
            return self._load_mock_teams()
        
        teams = self.ado_client.fetch_teams(project)
        if not teams:
            return self._load_mock_teams()
        
        return teams
    
    def _load_mock_features(self) -> List[Feature]:
        """Load mock features from sample snapshot."""
        # Calculate path relative to project root
        # src/agents/data_agent.py -> src/agents -> src -> root
        root_dir = Path(__file__).parent.parent.parent
        sample_path = root_dir / "samples" / "sample_snapshot.json"
        
        if not sample_path.exists():
            return self._get_hardcoded_mock_features()
        
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            features = []
            for feat_data in data.get("features", []):
                # 1. Przygotowanie słownika danych (kopia)
                feat_dict = feat_data.copy()
                
                # 2. Wyciągnięcie i usunięcie user_stories z głównego słownika
                #    (Feature oczekuje listy obiektów UserStory, a nie dictów)
                user_stories_data = feat_dict.pop("user_stories", [])
                
                # 3. Mapowanie pól specyficznych dla JSON -> Model
                if "dependencies" in feat_dict:
                    feat_dict["depends_on_features"] = feat_dict.pop("dependencies")
                
                # 4. Czyszczenie pól, których nie ma w modelu
                feat_dict.pop("blockers", None)
                
                # 5. Tworzenie obiektów UserStory (tylko w stanie "new" lub "active")
                user_stories_objs = []
                for us_data in user_stories_data:
                    try:
                        # UserStory(**us_data) zadziała, Pydantic sam skonwertuje 
                        # stringi (np. "state": "new") na Enumy.
                        user_story = UserStory(**us_data)
                        # Only consider User Stories in "new" or "active" state
                        if user_story.state in [FeatureStatus.NEW, FeatureStatus.ACTIVE]:
                            user_stories_objs.append(user_story)
                    except Exception as e:
                        print(f"Warning: Skipping invalid UserStory (ID: {us_data.get('id')}): {e}")
                
                # 6. Tworzenie obiektu Feature z jawnym przekazaniem listy user_stories
                try:
                    feature = Feature(
                        **feat_dict,
                        user_stories=user_stories_objs
                    )
                    features.append(feature)
                except Exception as e:
                    print(f"Error creating Feature (ID: {feat_dict.get('id')}): {e}")
                    
            return features
            
        except Exception as e:
            print(f"Error loading mock features from file: {e}")
            import traceback
            traceback.print_exc()
            return self._get_hardcoded_mock_features()

    def _get_hardcoded_mock_features(self) -> List[Feature]:
        """Return hardcoded features if file load fails."""
        return [
            Feature(
                id=1,
                title="User Authentication System (Fallback)",
                description="Implement OAuth2 authentication",
                priority=Priority.HIGH,
                business_value=80.0,
                effort=40.0,
            )
        ]
    
    def _load_mock_teams(self) -> List[Team]:
        """Load mock teams."""
        # Calculate path relative to project root
        root_dir = Path(__file__).parent.parent.parent
        sample_path = root_dir / "samples" / "sample_snapshot.json"
        
        default_teams = [
            Team(id="team-a", name="Team Alpha", capacity_per_iteration=40),
            Team(id="team-b", name="Team Beta", capacity_per_iteration=40),
        ]
        
        if not sample_path.exists():
            return default_teams
        
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                teams_data = data.get("teams", [])
                if not teams_data:
                    return default_teams
                return [Team(**team) for team in teams_data]
        except Exception:
            return default_teams
