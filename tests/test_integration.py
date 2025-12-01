import unittest
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from src.main import run_pi_planning
from src.ui.console_ui import ConsoleUI
from src.utils.config import Config
from src.integrations.ado_client import ADOClient
from src.core.models import Feature, Team, UserStory, Assignment

# Ensure config is loaded for tests
Config.load_config()

class TestFullFlow(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.output_dir = Path("test_output")
        self.output_dir.mkdir(exist_ok=True)
        self.console_ui = ConsoleUI(verbose=False) # Suppress verbose output during tests

        # Mock args for CLI parser
        self.base_args = MagicMock()
        self.base_args.project = "TestProject"
        self.base_args.pi_start = "2025-01-01"
        self.base_args.iterations = 3
        self.base_args.iteration_names = None
        # Updated to include 3 teams for generic scenario
        self.base_args.teams = "team-a,team-b,team-c"
        self.base_args.output_dir = str(self.output_dir)
        self.base_args.quiet = True
        self.base_args.command = "start"

    async def asyncSetUp(self):
        # Clean up any existing output files before each test
        for f in self.output_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass

    async def asyncTearDown(self):
        # Clean up output files after each test
        for f in self.output_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            self.output_dir.rmdir()
        except Exception:
            pass

    async def test_full_flow_with_ai(self):
        """Test full PI planning flow with generic mock data (3 teams) and AI agents enabled."""
        print("\n>>> Running Test: AI Flow (Mock Data - 3 Teams)...")
        args = self.base_args
        args.mock = True
        args.use_ai = True

        # Ensure AI config is present for this test
        if not (Config.AZURE_OPENAI_KEY and Config.AZURE_OPENAI_ENDPOINT and Config.AZURE_OPENAI_DEPLOYMENT):
            self.skipTest("Azure OpenAI credentials not configured in config.yaml or environment variables.")

        await run_pi_planning(args, self.console_ui)

        # Assertions
        # Find any program board JSON file
        program_board_files = list(self.output_dir.glob("program_board_*.json"))
        self.assertTrue(len(program_board_files) > 0, "Should have generated at least one program_board JSON file")
        
        # Find any transcript file
        transcript_files = list(self.output_dir.glob("transcript_*.json"))
        self.assertTrue(len(transcript_files) > 0, "Should have generated at least one transcript file")

        with open(program_board_files[0], "r", encoding="utf-8") as f:
            board_data = json.load(f)

        self.assertGreater(len(board_data["assignments"]), 0)
        # AI might be smart enough to mitigate risks or identify 0 risks if everything fits perfectly (unlikely here), 
        # so let's just check the board structure
        self.assertIn("risks", board_data)
        
        # Check if we have 3 teams
        self.assertEqual(len(board_data["teams"]), 3, "Should load 3 teams from mock data")
        
        print(">>> Test Passed: AI flow completed successfully.")

    def test_ado_data_structure(self):
        """Test fetching data from ADO and verify its structure."""
        print("\n>>> Running Test: ADO Data Structure Check...")
        ado_client = ADOClient()
        is_valid, error_msg = Config.validate_ado_config()
        if not is_valid:
            self.skipTest(f"ADO configuration invalid: {error_msg}")
        
        if not ado_client.is_connected():
            self.skipTest("ADO client is not connected. Check org_url and pat in config.yaml")

        # Get project from environment or use a default
        # Extract project name from org_url if available, or use default
        # Note: Project name is "GN", not "ONEGN" (ONEGN is the organization)
        project = os.getenv("TEST_ADO_PROJECT") or "GN"  # Default project name
        
        # Specific filters for this test
        area_path = "GN\\Applications\\SWART\\Team Ivy"  # Team area path
        iteration_path = "GN\\2026 Q1 PI"  # PI iteration path
        
        try:
            # ADOClient methods are synchronous, not async
            print(f">>> Fetching features from project: {project}")
            print(f">>>   Area Path: {area_path}")
            print(f">>>   Iteration Path: {iteration_path}")
            features = ado_client.fetch_features(
                project=project,
                area_path=area_path,
                iteration_path=iteration_path
            )
            print(f">>> Fetching teams from project: {project}")
            teams = ado_client.fetch_teams(project)

            self.assertGreater(len(features), 0, f"Should fetch some features from ADO project '{project}'")
            # Teams might be optional/empty depending on project, but usually there's at least 1 default
            self.assertGreater(len(teams), 0, f"Should fetch at least one team from ADO project '{project}'")

            # Verify structure of a sample feature
            sample_feature = features[0]
            self.assertIsInstance(sample_feature, Feature, "Feature should be a Feature instance")
            self.assertIsInstance(sample_feature.id, int, "Feature.id should be an integer")
            self.assertIsNotNone(sample_feature.title, "Feature should have a title")
            self.assertIsInstance(sample_feature.title, str, "Feature.title should be a string")
            self.assertIsInstance(sample_feature.user_stories, list, "Feature.user_stories should be a list")
            
            # Verify feature has required fields
            self.assertIsNotNone(sample_feature.priority, "Feature should have a priority")
            self.assertIsNotNone(sample_feature.state, "Feature should have a state")
            
            # Note: ADOClient.fetch_features() doesn't populate user_stories
            # They would need to be fetched separately via parent-child relationships
            # So we just verify the list exists (even if empty)
            
            # Verify structure of a sample team
            if teams:
                sample_team = teams[0]
                self.assertIsNotNone(sample_team.id, "Team should have an id")
                self.assertIsNotNone(sample_team.name, "Team should have a name")
                self.assertIsInstance(sample_team.name, str, "Team.name should be a string")
                self.assertIsInstance(sample_team.capacity_per_iteration, (int, float), "Team should have capacity")
            
            print(f">>> Found {len(features)} features and {len(teams)} teams")
            print(f">>> Sample feature: ID={sample_feature.id}, Title={sample_feature.title[:50]}")
            if teams:
                print(f">>> Sample team: ID={teams[0].id}, Name={teams[0].name}, Capacity={teams[0].capacity_per_iteration}")

            print(">>> Test Passed: ADO data fetched and structured correctly.")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.fail(f"Failed to fetch or validate ADO data: {e}\n{error_details}")

if __name__ == "__main__":
    unittest.main()
