"""Streamlit Web UI for PI Planning."""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import asyncio
import time
import warnings
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Suppress Streamlit warnings globally
warnings.filterwarnings('ignore', message='.*ScriptRunContext.*')
warnings.filterwarnings('ignore', message='.*bare mode.*')
warnings.filterwarnings('ignore', category=UserWarning, module='streamlit')

# Suppress Streamlit loggers
logging.getLogger('streamlit.runtime.scriptrunner.script_runner').setLevel(logging.CRITICAL)
logging.getLogger('streamlit.runtime.state').setLevel(logging.CRITICAL)
logging.getLogger('streamlit').setLevel(logging.CRITICAL)

# Import core logic
from src.core.agent_factory import AgentFactory
from src.agents.data_agent import DataAgent
from src.utils.config import Config
from src.core.events import ProposalEvent, AssignmentAcceptedEvent, AssignmentRejectedEvent, GapFillingStartEvent

# Import UI components
from src.ui.state_manager import StateManager
from src.ui.components.sidebar import render_sidebar
from src.ui.components.data_preview import display_features_preview
from src.ui.components.reporting import display_final_report

# Page config
st.set_page_config(
    page_title="PI Planning AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stProgress > div > div > div {
        background-color: #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)


async def run_planning_async(config: Dict[str, Any], progress_container=None, log_container=None, cached_features=None, agent_status_container=None):
    """Run PI planning asynchronously with live updates directly to UI."""
    start_time = time.time()
    
    try:
        # Step 1: Fetch data or use cached
        step_start = time.time()
        features = None
        
        if cached_features:
            if progress_container:
                progress_container.progress(0.05, text="✅ Using cached features data...")
            features = cached_features
            await asyncio.sleep(0.5)
        else:
            if progress_container:
                progress_container.progress(0.05, text="📥 Fetching data from ADO...")
            
            data_agent = DataAgent()
            
            if config.get("query_id"):
                features = data_agent.fetch_features(
                    config["project"], 
                    use_mock=config["use_mock_data"],
                    query_id=config["query_id"]
                )
            else:
                features = data_agent.fetch_features(
                    config["project"],
                    area_path=config.get("area_path"),
                    iteration_path=config.get("iteration_path"),
                    use_mock=config["use_mock_data"]
                )
        
        # Create teams
        # Use configuration directly from sidebar/config
        from src.core.models import Team
        teams = []
        
        # First, try to use teams defined in config
        if config.get("teams_config"):
            for team_id, team_data in config["teams_config"].items():
                team = Team(
                    id=team_id,
                    name=team_data["name"],
                    capacity_per_iteration=40, # Default fallback
                    capacity_per_sprint=team_data.get("capacity_per_sprint", {})
                )
                teams.append(team)
        else:
            # Fallback to ADO fetch if no config provided
            teams = DataAgent().fetch_teams(config["project"], use_mock=config["use_mock_data"])

        # Ensure at least minimal teams exist if fetch failed or config empty
        if not teams:
            # Use defaults from Config class if available
            default_teams = Config.DEFAULT_TEAMS
            if default_teams:
                for dt in default_teams:
                    teams.append(Team(
                        id=dt.get("id"),
                        name=dt.get("name"),
                        capacity_per_iteration=dt.get("default_capacity", 40)
                    ))
        
        if not features or not teams:
            StateManager.set("planning_status", {"step": "error", "message": "❌ No features or teams found"})
            return None
        
        # Step 2: Initialize Program Manager & Prioritize
        if progress_container:
            progress_container.progress(0.10, text="📊 Calculating business priorities (WSJF)...")
        
        if agent_status_container:
            agent_status_container.info(f"📊 **Prioritization Strategy** - Calculating WSJF for {len(features)} features")
            
        agent_factory = AgentFactory()
        
        program_manager = agent_factory.create_program_manager(
            teams=teams,
            features=features,
            iterations=config["iterations"],
            max_rounds=3
        )
        
        # Prioritize features (Calculates WSJF and Sorts)
        ranked_features = program_manager.prioritize_work(sprint_configs=config.get("sprint_configs"))
        
        if agent_status_container:
            agent_status_container.success(f"✅ **Prioritization** - Ranked {len(ranked_features)} features by priority")
        
        # Step 3: Negotiations
        total_stories = sum(len(f.user_stories) for f in ranked_features)
        StateManager.set("total_stories", total_stories)
        
        # Build sequence
        if progress_container:
            progress_container.progress(0.15, text=f"📋 Building execution sequence for {total_stories} stories...")
        
        if agent_status_container:
            agent_status_container.info(f"📋 **Planning Strategy** - Building sequence for {total_stories} user stories")
        
        user_stories_sequence = await asyncio.to_thread(program_manager.build_sequence)
        
        if agent_status_container:
            agent_status_container.success(f"✅ **Planning Strategy** - Sequence built with {len(user_stories_sequence)} stories")
        
        # Run Negotiations
        messages = []
        processed_count = 0
        accepted_count = 0
        rejected_count = 0
        processed_story_ids = set()  # Track unique stories to avoid double counting
        
        # Initialize log in session state if not exists
        import streamlit as st
        if "negotiation_log_lines" not in st.session_state:
            st.session_state.negotiation_log_lines = []
        
        if progress_container:
            progress_container.progress(0.20, text=f"🤝 Starting negotiations... Processing 0/{total_stories} stories...")
        
        if agent_status_container:
            agent_status_container.info(f"🤝 **Team Agents** - Starting negotiations for {total_stories} user stories")
            
        async for event in program_manager.run_negotiation(user_stories_sequence):
            
            if isinstance(event, GapFillingStartEvent):
                if progress_container:
                    progress_container.progress(0.95, text="🔧 Filling remaining capacity gaps...")
                if agent_status_container:
                    agent_status_container.info(f"🔧 **Gap Filling** - Filling remaining capacity gaps...")
                continue
            
            accepted = False
            team_name = ""
            us_id = 0
            iteration = ""
            effort = 0.0
            reason = ""
            is_new_story = False
            
            if isinstance(event, AssignmentAcceptedEvent):
                # Only count if this story hasn't been processed yet
                if event.story_id not in processed_story_ids:
                    processed_story_ids.add(event.story_id)
                    processed_count += 1
                    is_new_story = True
                accepted_count += 1
                accepted = True
                team_name = event.team_id
                us_id = event.story_id
                iteration = event.iteration
                effort = event.effort
                reason = event.reason
                
            elif isinstance(event, AssignmentRejectedEvent):
                # Only count if this story hasn't been processed yet
                if event.story_id not in processed_story_ids:
                    processed_story_ids.add(event.story_id)
                    processed_count += 1
                    is_new_story = True
                rejected_count += 1
                accepted = False
                team_name = event.team_id
                us_id = event.story_id
                iteration = "Rejected"
                effort = 0.0 # Info missing in reject event usually or irrelevant
                reason = event.reason
                
            elif isinstance(event, ProposalEvent):
                # Update agent status to show which team is being negotiated with
                if agent_status_container:
                    agent_status_container.info(f"💬 **Team Agent ({event.team_id})** - Proposing story #{event.story_id}: {event.story_title[:50]}...")
                continue

            StateManager.update_negotiation_stats(processed_count, accepted_count, rejected_count)
            
            # Update UI Log (only for Accept/Reject decisions)
            if log_container and (isinstance(event, AssignmentAcceptedEvent) or isinstance(event, AssignmentRejectedEvent)):
                
                # Find title
                story_title = "?"
                for f in ranked_features:
                    for us in f.user_stories:
                        if us.id == us_id:
                            story_title = us.title[:70]
                            break
                
                StateManager.add_log_entry({
                    "team": team_name,
                    "story_id": us_id,
                    "story_title": story_title,
                    "iteration": iteration,
                    "accepted": accepted,
                    "reason": reason,
                    "effort": effort
                })

                status_icon = "✅" if accepted else "❌"
                effort_str = f" ({effort:.1f} SP)" if effort > 0 else ""
                log_line = f"{status_icon} Story {us_id} → {team_name} ({iteration}){effort_str} | {story_title[:60]}... | {reason[:100]}"
                st.session_state.negotiation_log_lines.append(log_line)
                
                # Update the log display
                if log_container:
                    log_text = "\n".join(st.session_state.negotiation_log_lines)
                    log_container.code(log_text, language="")
            
            # Update progress bar (only if we processed a new story)
            if is_new_story:
                progress = min(max(processed_count / total_stories, 0.20), 0.95)
                if progress_container:
                    progress_container.progress(progress, text=f"🔄 Processing {processed_count}/{total_stories}... ✅ {accepted_count} accepted")
            
            await asyncio.sleep(0.05) # Yield to UI
        
        # Negotiations completed
        if agent_status_container:
            agent_status_container.success(f"✅ **Team Agents** - Negotiations completed: {accepted_count} accepted, {rejected_count} rejected")
        
        # Step 4: Objectives & Risks (Simplified)
        if progress_container:
            progress_container.progress(0.98, text="🎯 Generating Objectives & Risks...")
        
        # Generate Objectives
        if progress_container:
            progress_container.progress(0.985, text="🤖 AI Agent: Generating PI Objectives...")
        try:
            objective_agent = agent_factory.create_objective_agent()
            objectives_context = f"**Objective Agent** - Analyzing {len(ranked_features)} features across {len(teams)} teams"
            if agent_status_container:
                agent_status_container.info(f"🤖 {objectives_context}")
            pi_objectives = await asyncio.to_thread(objective_agent.generate_objectives, ranked_features, teams)
            if agent_status_container:
                agent_status_container.success(f"✅ **Objective Agent** - Generated {len(pi_objectives)} PI Objectives")
        except Exception as e:
            if agent_status_container:
                agent_status_container.error(f"❌ **Objective Agent** - Error: {str(e)[:100]}")
            pi_objectives = []
        
        # Identify Risks
        if progress_container:
            progress_container.progress(0.990, text="🤖 AI Agent: Identifying Risks...")
        try:
            risk_agent = agent_factory.create_risk_agent()
            accepted_count = len([a for a in program_manager.assignments if a.status == "accepted"])
            risks_context = f"**Risk Agent** - Analyzing {len(ranked_features)} features, {accepted_count} assignments, {len(teams)} teams, {len(config.get('iterations', []))} iterations"
            if agent_status_container:
                agent_status_container.info(f"🤖 {risks_context}")
            risks = await asyncio.to_thread(
                risk_agent.identify_risks,
                ranked_features,
                program_manager.assignments,
                teams,
                team_agents=program_manager.team_agents,
                iterations=config.get("iterations", [])
            )
            if agent_status_container:
                agent_status_container.success(f"✅ **Risk Agent** - Identified {len(risks)} risks")
        except Exception as e:
            import traceback
            print(f"Error identifying risks: {e}")
            traceback.print_exc()
            if agent_status_container:
                agent_status_container.error(f"❌ **Risk Agent** - Error: {str(e)[:100]}")
            risks = []
            
        # Step 5: Final Report
        if progress_container:
            progress_container.progress(0.995, text="🤖 AI Agent: Generating Insights...")
        reporting_agent = agent_factory.create_reporting_agent()
        accepted_assignments = [a for a in program_manager.assignments if a.status == "accepted"]
        
        insights_context = f"**Reporting Agent (Insights)** - Analyzing plan with {len(ranked_features)} features, {len(accepted_assignments)} assignments, {len(teams)} teams"
        if agent_status_container:
            agent_status_container.info(f"🤖 {insights_context}")
        
        program_board = reporting_agent.generate_program_board(
            project=config["project"],
            pi_start=config["pi_start"],
            iterations=config["iterations"],
            teams=teams,
            features=ranked_features,
            assignments=accepted_assignments,
            negotiation_rounds=len(program_manager.negotiation_rounds),
            pi_objectives=pi_objectives,
            risks=risks
        )
        
        if agent_status_container:
            if program_board.ai_insights:
                agent_status_container.success(f"✅ **Reporting Agent** - Generated AI Insights")
            else:
                agent_status_container.warning(f"⚠️ **Reporting Agent** - No insights generated")
        
        transcript = reporting_agent.generate_transcript(
            session_id=str(datetime.now(timezone.utc).timestamp()),
            start_time=datetime.now(timezone.utc),
            messages=messages, # Warning: messages list is now empty as we use events, need to adapt if transcript is critical
            final_plan=program_board
        )
        
        if progress_container:
            progress_container.progress(1.0, text="✅ Planning Complete!")
            
        return {
            "program_board": program_board,
            "transcript": transcript,
            "assignments": accepted_assignments,
            "features": ranked_features,
            "teams": teams,
            "objectives": pi_objectives,
            "risks": risks,
            "messages": messages
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        StateManager.set("planning_status", {"step": "error", "message": str(e)})
        # Return partial result
        return {
            "program_board": {"assignments": [], "features": [], "teams": []},
            "assignments": [],
            "features": [],
            "teams": [],
            "objectives": [],
            "risks": [],
            "messages": []
        }


def main():
    """Main Application Loop."""
    StateManager.init_state()
    
    # Header
    st.markdown('<div class="main-header">📊 PI Planning AI Assistant</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    config = render_sidebar()
    StateManager.set("config", config)
    
    # Main Logic
    if not StateManager.get("planning_complete"):
        
        # 1. Status Dashboard
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Project:** {config['project']} | **Iterations:** {len(config['iterations'])}")
        with col2:
            # Check if OpenAI key is present to determine "AI Available" status
            status = "AI Available" if config.get("openai_key") else "Standard Logic Only"
            st.success(f"**Mode:** {status}")
            
        # 2. Load Data
        if not StateManager.get("data_loaded"):
            if st.button("🚀 Load Data & Preview", type="primary"):
                with st.spinner("Loading ADO Data..."):
                    data_agent = DataAgent()
                    features = None
                    teams = None
                    
                    try:
                        if config.get("query_id"):
                            features = data_agent.fetch_features(config["project"], use_mock=config["use_mock_data"], query_id=config["query_id"])
                        else:
                            features = data_agent.fetch_features(config["project"], area_path=config.get("area_path"), iteration_path=config.get("iteration_path"), use_mock=config["use_mock_data"])
                        
                        # Teams logic (using config directly)
                        from src.core.models import Team
                        teams = []
                        if config.get("teams_config"):
                            for tid, tdata in config["teams_config"].items():
                                teams.append(Team(
                                    id=tid, 
                                    name=tdata["name"], 
                                    capacity_per_sprint=tdata["capacity_per_sprint"]
                                ))
                        else:
                            teams = data_agent.fetch_teams(config["project"], use_mock=config["use_mock_data"])
                            
                        if features:
                            StateManager.set("features_data", features)
                            StateManager.set("teams_data", teams)
                            StateManager.set("data_loaded", True)
                            st.rerun()
                        else:
                            st.error("No features found. Check configuration.")
                            
                    except Exception as e:
                        st.error(f"Error loading data: {e}")
        
        # 3. Data Preview & Confirmation
        if StateManager.get("data_loaded"):
            display_features_preview(
                StateManager.get("features_data"), 
                StateManager.get("teams_data"),
                config.get("sprint_configs")
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm & Start Planning", type="primary"):
                    StateManager.set("planning_started", True)
                    st.rerun()
            with col2:
                if st.button("🔄 Reset Data"):
                    StateManager.clear_all_data()
                    st.rerun()
        
        # 4. Live Planning Execution
        if StateManager.get("planning_started") and not StateManager.get("negotiations_finished"):
            st.markdown("### 🚀 Execution Phase")
            progress_bar = st.empty()
            
            # Agent Status Section
            st.markdown("#### 🤖 AI Agent Status")
            agent_status_container = st.empty()
            agent_status_container.info("⏳ Waiting for planning to start...")
            
            st.write("### 💬 Live Negotiation Log")
            
            # Initialize log in session state if not exists
            if "negotiation_log_lines" not in st.session_state:
                st.session_state.negotiation_log_lines = []
            
            # Display current log lines in a scrollable container
            with st.container(height=400):
                log_placeholder = st.empty()
                log_text = "\n".join(st.session_state.negotiation_log_lines) if st.session_state.negotiation_log_lines else "Negotiations will appear here..."
                log_placeholder.code(log_text, language="")
            
            # Execute Async Planning
            result = asyncio.run(run_planning_async(
                config, 
                progress_bar, 
                log_placeholder, 
                cached_features=StateManager.get("features_data"),
                agent_status_container=agent_status_container
            ))
            
            if result:
                StateManager.set("planning_result", result)
                StateManager.set("negotiations_finished", True)
                st.rerun()
                
        # 5. Negotiation Review (Post-Planning)
        if StateManager.get("negotiations_finished"):
            st.success("✅ Negotiations completed!")
            
            with st.expander("📜 Review Full Negotiation Log", expanded=False):
                log = StateManager.get("negotiation_log", [])
                for entry in reversed(log):
                    st.text(f"{'✅' if entry['accepted'] else '❌'} {entry['team']} - {entry['story_title'][:50]}... ({entry['iteration']})")
            
            if st.button("📊 Generate Final Report", type="primary"):
                StateManager.set("planning_complete", True)
                st.rerun()

    # 6. Final Report
    else:
        if StateManager.get("planning_result"):
            result = StateManager.get("planning_result")
            program_board = result.get("program_board")
            ai_insights = program_board.ai_insights if program_board and hasattr(program_board, 'ai_insights') else None
            
            display_final_report(
                features=result.get("features", []),
                teams=result.get("teams", []),
                iterations=config.get("iterations", []),
                assignments=result.get("assignments", []),
                ai_insights=ai_insights,
                risks=result.get("risks", []),
                objectives=result.get("objectives", [])
            )
            
            if st.button("🔄 Start New Session"):
                StateManager.reset_planning()
                st.rerun()


if __name__ == "__main__":
    Config.load_config()
    main()
