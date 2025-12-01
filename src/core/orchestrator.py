"""Orchestrator - runs the multi-agent PI planning workflow."""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from src.core.models import Feature, Team, Message, Transcript

from src.agents.data_agent import DataAgent
from src.agents.program_manager import ProgramManager
from src.agents.reporting_agent import ReportingAgent
from src.ui.console_ui import ConsoleUI
from src.ui.program_board_html import generate_html_program_board
from src.core.agent_factory import AgentFactory


class Orchestrator:
    """Orchestrates the PI planning workflow."""
    
    def __init__(self, console_ui: Optional[ConsoleUI] = None):
        """
        Initialize orchestrator.
        
        Args:
            console_ui: Optional console UI instance
        """
        self.console_ui = console_ui or ConsoleUI()
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.messages: List[Message] = []
    
    async def run_pi_planning(
        self,
        project: str,
        pi_start: str,
        iterations: List[str],
        teams: List[str],
        use_mock_data: bool = False,
        use_ai_agents: bool = False
    ) -> dict:
        """
        Run the complete PI planning workflow.
        
        Args:
            project: Project name
            pi_start: PI start date
            iterations: List of iteration names
            teams: List of team IDs
            use_mock_data: Use mock data instead of ADO
            
        Returns:
            Final plan dictionary
        """
        self.console_ui.display_header(
            f"Starting PI Planning for {project}",
            f"PI Start: {pi_start} | Iterations: {', '.join(iterations)}"
        )
        
        # Step 1: Data Agent - Fetch features and teams
        self.console_ui.display_info("Fetching data from ADO...")
        data_agent = DataAgent()
        features = data_agent.fetch_features(project, use_mock=use_mock_data)
        all_teams = data_agent.fetch_teams(project, use_mock=use_mock_data)
        
        # Filter teams if specified
        if teams:
            all_teams = [t for t in all_teams if t.id in teams]
        
        if not features:
            self.console_ui.display_error("No features found. Exiting.")
            return {}
        
        if not all_teams:
            self.console_ui.display_error("No teams found. Exiting.")
            return {}
        
        self.console_ui.display_success(f"Found {len(features)} features and {len(all_teams)} teams")
        
        # Step 2: WSJF Agent - Calculate rankings
        self.console_ui.display_info("Calculating WSJF scores...")
        agent_factory = AgentFactory(use_ai=use_ai_agents)
        wsjf_agent = agent_factory.create_wsjf_agent()
        ranked_features = wsjf_agent.calculate_wsjf(features)
        
        self.console_ui.display_success(f"Ranked {len(ranked_features)} features by WSJF")
        
        # Step 3: Program Manager - Run User Story sequencing negotiations
        self.console_ui.display_info("Starting User Story sequencing negotiations...")
        program_manager = agent_factory.create_program_manager(
            teams=all_teams,
            features=ranked_features,  # Features with User Stories
            iterations=iterations,
            max_rounds=3
        )
        
        # Collect all messages from negotiation
        async for message in program_manager.run_negotiation():
            self.messages.append(message)
            self.console_ui.log_message(message)
        
        # Step 4: Get final plan
        final_plan_data = program_manager.get_final_plan()
        accepted_assignments = [
            a for a in program_manager.assignments
            if a.status == "accepted"
        ]
        
        # Step 4: Objective Agent - Generate PI Objectives
        self.console_ui.display_info("Generating PI Objectives...")
        objective_agent = agent_factory.create_objective_agent()
        pi_objectives = objective_agent.generate_objectives(ranked_features, all_teams)
        self.console_ui.display_success(f"Generated {len(pi_objectives)} PI Objectives")
        
        # Step 5: Risk Agent - Identify risks
        self.console_ui.display_info("Identifying risks...")
        risk_agent = agent_factory.create_risk_agent()
        risks = risk_agent.identify_risks(
            ranked_features,
            program_manager.assignments,
            all_teams,
            team_agents=program_manager.team_agents
        )
        self.console_ui.display_success(f"Identified {len(risks)} risks")
        
        # Display risks summary
        if risks:
            self.console_ui.display_risks_summary(risks)
        
        # Step 6: Reporting Agent - Generate program board
        self.console_ui.display_info("Generating program board...")
        reporting_agent = agent_factory.create_reporting_agent()
        
        program_board = reporting_agent.generate_program_board(
            project=project,
            pi_start=pi_start,
            iterations=iterations,
            teams=all_teams,
            features=ranked_features,
            assignments=accepted_assignments,
            negotiation_rounds=len(program_manager.negotiation_rounds),
            pi_objectives=pi_objectives,
            risks=risks
        )
        
        # Generate transcript
        transcript = reporting_agent.generate_transcript(
            session_id=self.session_id,
            start_time=self.start_time,
            messages=self.messages,
            final_plan=program_board
        )
        
        # Display summary
        self.console_ui.display_summary(program_board)
        
        # Display objectives if available
        if pi_objectives:
            self.console_ui.display_objectives_summary(pi_objectives)
        
        return {
            "program_board": program_board,
            "transcript": transcript,
            "assignments": accepted_assignments,
            "features": ranked_features,
        }

