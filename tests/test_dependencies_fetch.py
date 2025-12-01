"""Test to verify that dependencies are correctly fetched."""
import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.integrations.ado_client import ADOClient
from src.core.models import UserStory, FeatureStatus

class TestDependencyFetch(unittest.TestCase):
    
    def setUp(self):
        self.ado_client = ADOClient(
            organization_url="https://dev.azure.com/mockorg",
            personal_access_token="mock_pat"
        )
        # Mock connection to bypass connectivity check
        self.ado_client.connection = MagicMock()

    @patch('src.integrations.ado_client.requests.get')
    def test_fetch_user_stories_with_dependencies(self, mock_get):
        """Test fetching User Stories and identifying dependencies."""
        print("=" * 80)
        print("Testing dependency fetching (Mocked)")
        print("=" * 80)
        
        feature_id = 1001
        project = "MockProject"
        
        # Mock successful REST API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'relations': [
                {'url': f'https://dev.azure.com/mockorg/{project}/_apis/wit/workItems/2001'},
                {'url': f'https://dev.azure.com/mockorg/{project}/_apis/wit/workItems/2002'}, # Dependency
                {'url': f'https://dev.azure.com/mockorg/{project}/_apis/wit/workItems/2003'}  # Direct US
            ]
        }
        mock_get.return_value = mock_response
        
        # Mock wit_client.get_work_items
        mock_wit_client = MagicMock()
        
        # Mock Work Items
        # 1. Dependency (Type: Dependency)
        wi_dep1 = MagicMock()
        wi_dep1.id = 2001
        wi_dep1.fields = {
            "System.WorkItemType": "Dependency",
            "System.Title": "External Dependency",
            "System.Description": "Desc",
            "System.AssignedTo": "External Team",
            "Microsoft.VSTS.Scheduling.StoryPoints": 5.0,
            "System.State": "New",
            "System.AreaPath": "External\\Area"
        }
        
        # 2. Dependency (Type: User Story, Title convention)
        wi_dep2 = MagicMock()
        wi_dep2.id = 2002
        wi_dep2.fields = {
            "System.WorkItemType": "User Story",
            "System.Title": "[From Team X to Ivy] Some dependency",
            "System.Description": "Desc",
            "System.AssignedTo": "Team X",
            "Microsoft.VSTS.Scheduling.StoryPoints": 3.0,
            "System.State": "Active",
            "System.AreaPath": "External\\Area"
        }
        
        # 3. Direct User Story
        wi_direct = MagicMock()
        wi_direct.id = 2003
        wi_direct.fields = {
            "System.WorkItemType": "User Story",
            "System.Title": "Regular Story",
            "System.Description": "Desc",
            "System.AssignedTo": "Team Ivy",
            "Microsoft.VSTS.Scheduling.StoryPoints": 8.0,
            "System.State": "New",
            "System.AreaPath": "Internal\\Area"
        }
        
        mock_wit_client.get_work_items.return_value = [wi_dep1, wi_dep2, wi_direct]
        
        # Execute method
        direct_stories, dependencies = self.ado_client._fetch_user_stories_for_feature(
            wit_client=mock_wit_client,
            project=project,
            feature_id=feature_id,
            team_area_path="Internal\\Area"
        )
        
        # Assertions
        print(f"Found {len(direct_stories)} direct stories and {len(dependencies)} dependencies")
        
        self.assertEqual(len(direct_stories), 1, "Should have 1 direct user story")
        self.assertEqual(direct_stories[0].id, 2003)
        
        self.assertEqual(len(dependencies), 2, "Should have 2 dependencies")
        dep_ids = sorted([d.id for d in dependencies])
        self.assertEqual(dep_ids, [2001, 2002])
        
        print("✅ SUCCESS: Dependencies correctly identified from mock data")

if __name__ == "__main__":
    unittest.main()
