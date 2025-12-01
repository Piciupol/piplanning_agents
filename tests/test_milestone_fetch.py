"""Test for fetching milestones for specific feature (Mocked)."""
import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.integrations.ado_client import ADOClient
from src.utils.config import Config

class TestMilestoneFetch(unittest.TestCase):
    
    def setUp(self):
        # Mock Config to avoid loading real one
        Config.ADO_MAPPING = {
            "work_item_type": "System.WorkItemType",
            "title": "System.Title",
            "target_date": "System.TargetDate"
        }
        
        self.ado_client = ADOClient(
            organization_url="https://dev.azure.com/mockorg",
            personal_access_token="mock_pat"
        )
        self.ado_client.connection = MagicMock()
    
    @patch('src.integrations.ado_client.requests.get')
    def test_fetch_milestone_for_feature(self, mock_get):
        """Test fetching milestone for a feature."""
        print("\n>>> Testing milestone fetch (Mocked)...")
        
        project = "MockProject"
        feature_id = 1001
        milestone_id = 5001
        
        # Mock REST API response for links
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'relations': [
                {'url': f'https://dev.azure.com/mockorg/{project}/_apis/wit/workItems/{milestone_id}'}
            ]
        }
        mock_get.return_value = mock_response
        
        # Mock wit_client
        mock_wit_client = MagicMock()
        
        # Mock Milestone Work Item
        wi_milestone = MagicMock()
        wi_milestone.id = milestone_id
        wi_milestone.fields = {
            "System.WorkItemType": "Milestone",
            "System.Title": "Q1 Release",
            "System.TargetDate": "2025-03-31T00:00:00Z"
        }
        
        mock_wit_client.get_work_items.return_value = [wi_milestone]
        
        # Execute
        milestones = self.ado_client._fetch_milestones_for_feature(
            mock_wit_client,
            project,
            feature_id
        )
        
        # Verify
        self.assertEqual(len(milestones), 1)
        self.assertEqual(milestones[0].id, milestone_id)
        self.assertEqual(milestones[0].title, "Q1 Release")
        self.assertIsInstance(milestones[0].target_date, datetime)
        self.assertEqual(milestones[0].target_date.year, 2025)
        
        print("✅ SUCCESS: Milestone correctly fetched and parsed from mock data")

if __name__ == '__main__':
    unittest.main()
