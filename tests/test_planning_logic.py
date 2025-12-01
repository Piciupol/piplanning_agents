"""Test core planning logic with in-memory data."""
import unittest
import asyncio
from src.core.models import Feature, UserStory, Team, FeatureStatus, Priority
from src.agents.program_manager import ProgramManager
from src.core.agent_factory import AgentFactory

class TestPlanningLogic(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        # Create Mock Teams
        self.teams = [
            Team(id="team_a", name="Team A", capacity_per_iteration=20),
            Team(id="team_b", name="Team B", capacity_per_iteration=20)
        ]
        
        # Create Mock Features & Stories
        self.features = []
        
        # Feature 1: High Priority (WSJF), Team A
        f1 = Feature(
            id=1, title="Feature 1", state=FeatureStatus.NEW, priority=Priority.HIGH,
            business_value=100, effort=10, assigned_team="Team A"
        )
        f1.user_stories = [
            UserStory(id=101, title="Story 1.1", feature_id=1, assigned_team="Team A", effort=5),
            UserStory(id=102, title="Story 1.2", feature_id=1, assigned_team="Team A", effort=8)
        ]
        self.features.append(f1)
        
        # Feature 2: Low Priority, Team B
        f2 = Feature(
            id=2, title="Feature 2", state=FeatureStatus.NEW, priority=Priority.LOW,
            business_value=10, effort=10, assigned_team="Team B"
        )
        f2.user_stories = [
            UserStory(id=201, title="Story 2.1", feature_id=2, assigned_team="Team B", effort=15)
        ]
        self.features.append(f2)
        
        self.iterations = ["Sprint 1", "Sprint 2", "Sprint 3"]

    async def test_planning_sequence_and_assignment(self):
        """Test that high priority features are planned first."""
        print("\n>>> Testing Planning Logic (In-Memory)...")
        
        # 1. Initialize Program Manager
        factory = AgentFactory()
        pm = factory.create_program_manager(
            teams=self.teams,
            features=self.features,
            iterations=self.iterations
        )
        
        # 2. Prioritize Features (WSJF)
        ranked_features = pm.prioritize_work()
        
        # Verify ranking
        self.assertEqual(ranked_features[0].id, 1, "Feature 1 should be first due to higher BV")
        
        # 3. Build Sequence
        sequence = pm.build_sequence()
        
        # Verify sequence order (Story 1.1/1.2 should be before 2.1)
        us_ids = [us.id for us in sequence]
        print(f"Sequence: {us_ids}")
        
        # Check if stories from Feature 1 are before Feature 2 (roughly)
        idx_101 = us_ids.index(101)
        idx_201 = us_ids.index(201)
        self.assertLess(idx_101, idx_201, "High priority story should be sequenced earlier")
        
        # 4. Run Negotiation (Planning)
        messages = []
        async for msg in pm.run_negotiation(sequence):
            messages.append(msg)
            
        assignments = [a for a in pm.assignments if a.status == "accepted"]
        
        # Verify Assignments
        self.assertEqual(len(assignments), 3, "All 3 stories should be assigned")
        
        # Verify Team Assignments
        a_101 = next(a for a in assignments if a.user_story_id == 101)
        self.assertEqual(a_101.team_id, "Team A")
        self.assertEqual(a_101.iteration, "Sprint 1") # Should fit in first sprint
        
        a_201 = next(a for a in assignments if a.user_story_id == 201)
        self.assertEqual(a_201.team_id, "Team B")
        
        print("✅ SUCCESS: Logic verified correctly")

if __name__ == "__main__":
    unittest.main()
