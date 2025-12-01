import streamlit as st
from datetime import date, timedelta, datetime
from src.utils.config import Config

def render_sidebar():
    """Render sidebar configuration and return config dictionary."""
    st.sidebar.header("⚙️ Configuration")
    
    # --- Mode Selection ---
    use_mock_data = st.sidebar.checkbox("🛠️ Demo Mode (Use Mock Data)", value=False, help="Run with sample data instead of connecting to Azure DevOps")
    
    if use_mock_data:
        st.sidebar.info("ℹ️ Running in Demo Mode. ADO settings are ignored.")
        ado_org = "https://dev.azure.com/demo"
        ado_project = "DemoProject"
        ado_pat = ""
        query_id = None
        area_path = "Demo\\Area"
        iteration_path = "Demo\\Iteration"
    else:
        # --- ADO Configuration ---
        with st.sidebar.expander("Azure DevOps Settings", expanded=True):
            ado_org = st.text_input("Organization URL", value=Config.ADO_ORG_URL or "https://dev.azure.com/ONEGN", key="ado_org")
            ado_project = st.text_input("Project Name", value=Config.ADO_PROJECT or "GN", key="ado_project")
            ado_pat = st.text_input("Personal Access Token (PAT)", value=Config.ADO_PAT or "", type="password", key="ado_pat")
            
            # Work Item Query
            default_query_id = Config.DEFAULT_QUERIES.get("features_query_id", "")
            query_id = st.text_input(
                "Feature Query ID (Optional)", 
                value=default_query_id,
                help="UUID of the saved query in ADO that returns Features."
            )
            
            st.caption("Alternatively, define scope manually:")
            default_area = Config.DEFAULT_QUERIES.get("area_path", "GN\\Applications\\SWART\\Team Ivy")
            default_iter = Config.DEFAULT_QUERIES.get("iteration_path", "GN\\2026 Q1 PI")
            
            area_path = st.text_input("Area Path", value=default_area)
            iteration_path = st.text_input("Iteration Path", value=default_iter)

    # --- Planning Configuration ---
    with st.sidebar.expander("Planning Settings", expanded=True):
        # Sprints defaults
        sprint_conf = Config.DEFAULT_SPRINTS_CONFIG
        default_start = date.fromisoformat(sprint_conf.get("start_date", "2025-12-04")) if sprint_conf.get("start_date") else date.today()
        default_count = sprint_conf.get("count", 5)
        default_len = sprint_conf.get("length_weeks", 2)
        
        start_date = st.date_input("PI Start Date", value=default_start)
        num_sprints = st.number_input("Number of Sprints", min_value=1, max_value=10, value=default_count)
        sprint_length = st.number_input("Sprint Length (weeks)", min_value=1, max_value=4, value=default_len)
        
        # AI Settings (Hidden logic, just keys if needed)
        st.divider()
        st.caption("🤖 AI Configuration (Optional)")
        openai_key = st.text_input("Azure OpenAI Key", value=Config.AZURE_OPENAI_KEY or "", type="password")
        openai_endpoint = st.text_input("Azure OpenAI Endpoint", value=Config.AZURE_OPENAI_ENDPOINT or "")
        openai_deployment = st.text_input("Model Deployment Name", value=Config.AZURE_OPENAI_DEPLOYMENT)

    # --- Sprint Definition ---
    sprint_dates = []
    current_date = start_date
    
    # Pre-defined sprint end dates from config (if any)
    config_end_dates = sprint_conf.get("end_dates", [])
    
    st.sidebar.subheader("Sprint Schedule")
    sprint_configs = {}
    
    for i in range(num_sprints):
        # Determine default end date
        if i < len(config_end_dates):
            try:
                default_end = date.fromisoformat(config_end_dates[i])
            except ValueError:
                default_end = current_date + timedelta(weeks=sprint_length)
        else:
            default_end = current_date + timedelta(weeks=sprint_length)
            
        end_date = st.sidebar.date_input(f"Sprint {i+1} End Date", value=default_end, key=f"sprint_{i}_end")
        sprint_name = f"Sprint {i+1}"
        sprint_dates.append((sprint_name, end_date))
        
        sprint_configs[sprint_name] = {
            "end_date": end_date,
            "index": i
        }
        
        current_date = end_date + timedelta(days=1) # Next sprint starts day after

    # --- Teams Configuration ---
    st.sidebar.subheader("👥 Teams Configuration")
    
    default_teams = Config.DEFAULT_TEAMS
    # If demo mode and no teams in config, provide dummy teams
    if use_mock_data and not default_teams:
        default_teams = [
            {"name": "Demo Team A", "id": "demo_a", "default_capacity": 40},
            {"name": "Demo Team B", "id": "demo_b", "default_capacity": 35}
        ]
        
    num_teams = st.number_input("Number of Teams", min_value=1, max_value=10, value=max(len(default_teams), 2), key="num_teams")
    
    teams_config = {}
    sprint_names = [s[0] for s in sprint_dates]
    
    for i in range(num_teams):
        # Get defaults for this team index if available
        team_default = default_teams[i] if i < len(default_teams) else {}
        default_name = team_default.get("name", f"Team {i+1}")
        default_capacity = team_default.get("default_capacity", 40)
        capacity_pattern = team_default.get("capacity_pattern", [])
        
        with st.sidebar.expander(f"{default_name}", expanded=(i < 2)):
            team_name = st.text_input(f"Team Name", value=default_name, key=f"team_name_{i}")
            team_id = team_name.lower().replace(" ", "-")
            
            st.markdown(f"**Capacity per Sprint:**")
            sprint_capacity = {}
            
            for idx, sprint_name in enumerate(sprint_names):
                # Use pattern if available, else default capacity
                val = capacity_pattern[idx] if idx < len(capacity_pattern) else default_capacity
                
                capacity = st.number_input(
                    f"{sprint_name} Capacity (SP)",
                    min_value=0, max_value=200, value=val,
                    key=f"team_{i}_sprint_{idx}_cap"
                )
                sprint_capacity[sprint_name] = {"total": capacity}
            
            teams_config[team_id] = {
                "name": team_name,
                "id": team_id,
                "capacity_per_sprint": sprint_capacity
            }

    return {
        "ado_org": ado_org,
        "ado_project": ado_project,
        "ado_pat": ado_pat,
        "query_id": query_id.strip() if query_id else None,
        "area_path": area_path,
        "iteration_path": iteration_path,
        "sprint_dates": sprint_dates,
        "sprint_configs": sprint_configs,
        "iterations": [s[0] for s in sprint_dates],
        "teams_config": teams_config,
        "use_mock_data": use_mock_data,
        "openai_key": openai_key,
        "openai_endpoint": openai_endpoint,
        "openai_deployment": openai_deployment,
        "pi_start": start_date.strftime("%Y-%m-%d"),
        "project": ado_project
    }
