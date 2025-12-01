import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

def map_target_date_to_sprint(target_date, sprint_configs):
    """Map a target date to the appropriate sprint."""
    if not target_date or not sprint_configs:
        return None
    if isinstance(target_date, str):
        try:
            target_date = datetime.fromisoformat(target_date.replace('Z', '+00:00')).date()
        except:
            return None
    elif isinstance(target_date, datetime):
        target_date = target_date.date()
    
    for sprint_name, config in sorted(sprint_configs.items(), key=lambda x: x[1]["index"]):
        sprint_end = config["end_date"]
        if isinstance(sprint_end, str):
            sprint_end = datetime.strptime(sprint_end, "%Y-%m-%d").date()
        if target_date <= sprint_end:
            return sprint_name
    if sprint_configs:
        last_sprint = max(sprint_configs.items(), key=lambda x: x[1]["index"])
        return last_sprint[0]
    return None

def display_features_preview(features: List, teams: List, sprint_configs: Dict[str, Any] = None):
    """Display features and teams for review before planning, with team assignment editing."""
    st.subheader("📋 Data Preview & Team Assignment")
    
    # Get available team names
    team_names = [t.name for t in teams] if teams else []
    
    # Always include default teams (Team Ivy and Team Riddler) if not already present
    default_teams = ["Team Ivy", "Team Riddler"]
    for default_team in default_teams:
        if default_team not in team_names:
            team_names.append(default_team)
    
    if not team_names:
        # Fallback teams if none loaded
        team_names = ["Team Ivy", "Team Riddler", "Team Apollo", "Team Other"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Features")
        if features:
            # Map milestone target dates to sprints if deadline_sprint is not set
            for f in features:
                if not f.deadline_sprint and f.milestones and sprint_configs:
                    # Find earliest milestone target date and map to sprint
                    milestone_dates = [m.target_date for m in f.milestones if m.target_date]
                    if milestone_dates:
                        earliest_date = min(milestone_dates)
                        mapped_sprint = map_target_date_to_sprint(earliest_date, sprint_configs)
                        if mapped_sprint:
                            f.deadline_sprint = mapped_sprint
            
            # Create table with team assignment info and target iteration
            # Calculate planning priority (same logic as in sequencing agent)
            def get_planning_priority(f):
                """Get planning priority for display (same logic as sequencing)."""
                # Priority order: 1) target_date, 2) deadline_sprint, 3) cost_of_delay
                priority_parts = []
                
                # 1. Target Date (earliest milestone)
                if f.milestones:
                    milestone_dates = [m.target_date for m in f.milestones if m.target_date]
                    if milestone_dates:
                        earliest_date = min(milestone_dates)
                        if isinstance(earliest_date, str):
                            from datetime import datetime
                            try:
                                earliest_date = datetime.fromisoformat(earliest_date.replace('Z', '+00:00'))
                            except:
                                pass
                        if hasattr(earliest_date, 'strftime'):
                            priority_parts.append(f"Date: {earliest_date.strftime('%Y-%m-%d')}")
                        elif hasattr(earliest_date, 'isoformat'):
                            priority_parts.append(f"Date: {earliest_date.isoformat()}")
                
                # 2. Target Iteration (deadline_sprint)
                if f.deadline_sprint:
                    try:
                        sprint_num = int(''.join(filter(str.isdigit, f.deadline_sprint)) or '999')
                        priority_parts.append(f"Sprint {sprint_num}")
                    except:
                        priority_parts.append(f.deadline_sprint)
                
                # 3. Cost of Delay
                if f.cost_of_delay:
                    priority_parts.append(f"CoD: {f.cost_of_delay:.1f}")
                
                if priority_parts:
                    return " | ".join(priority_parts)
                else:
                    # If no priority info, show that it will be planned last, after dependencies
                    return "N/A (last, by dependencies & load order)"
            
            features_df = pd.DataFrame([
                {
                    "ID": f.id,
                    "Title": f.title[:50] + "..." if len(f.title) > 50 else f.title,
                    "Priority": f.priority.value,
                    "Planning Priority": get_planning_priority(f),
                    "User Stories": len(f.user_stories),
                    "Team": f.assigned_team or (f.area_path.split("\\")[-1] if f.area_path else "Unassigned"),
                    "Target Iteration": f.deadline_sprint or "None",
                    "Target Date": (
                        min([m.target_date for m in f.milestones if m.target_date]).strftime("%Y-%m-%d")
                        if f.milestones and any(m.target_date for m in f.milestones)
                        else "None"
                    )
                }
                for f in features
            ])
            
            # Sort by Target Iteration (None last, then by sprint number)
            if not features_df.empty and "Target Iteration" in features_df.columns:
                # Create sort key: extract sprint number for sorting
                def sort_key(row):
                    target = row["Target Iteration"]
                    if target == "None":
                        return (1, 999)  # None values go last
                    # Extract sprint number (e.g., "Sprint 1" -> 1)
                    try:
                        sprint_num = int(''.join(filter(str.isdigit, target)) or '999')
                        return (0, sprint_num)  # Sort by sprint number
                    except:
                        return (0, 999)
                
                features_df['_sort_key'] = features_df.apply(sort_key, axis=1)
                features_df = features_df.sort_values('_sort_key').drop(columns=['_sort_key'])
            
            st.dataframe(features_df, width='stretch', hide_index=True)
            st.info(f"Total: {len(features)} features")
        else:
            st.warning("No features found")
    
    with col2:
        st.markdown("### Teams")
        if teams:
            # Build teams dataframe with capacity per sprint
            teams_data = []
            for t in teams:
                team_row = {
                    "ID": t.id,
                    "Name": t.name,
                    "Capacity/Iteration": t.capacity_per_iteration if hasattr(t, 'capacity_per_iteration') and t.capacity_per_iteration else "N/A"
                }
                
                # Add capacity per sprint columns if sprint_configs are available
                if sprint_configs and hasattr(t, 'capacity_per_sprint') and t.capacity_per_sprint:
                    for sprint_name in sorted(sprint_configs.keys(), key=lambda x: sprint_configs[x]["index"]):
                        sprint_capacity = t.capacity_per_sprint.get(sprint_name, {})
                        if isinstance(sprint_capacity, dict):
                            capacity_value = sprint_capacity.get("total", sprint_capacity.get("dev", 0) + sprint_capacity.get("tst", 0))
                        else:
                            capacity_value = sprint_capacity
                        team_row[sprint_name] = capacity_value if capacity_value else "N/A"
                elif sprint_configs:
                    # If team doesn't have capacity_per_sprint, show N/A for all sprints
                    for sprint_name in sorted(sprint_configs.keys(), key=lambda x: sprint_configs[x]["index"]):
                        team_row[sprint_name] = "N/A"
                
                teams_data.append(team_row)
            
            teams_df = pd.DataFrame(teams_data)
            st.dataframe(teams_df, width='stretch', hide_index=True)
            st.info(f"Total: {len(teams)} teams")
        else:
            st.warning("No teams found")
    
    # Team assignment editor
    if features:
        st.markdown("---")
        st.markdown("### ✏️ Edit Team Assignments")
        
        # Create a selectbox for each feature
        feature_options = [f"{f.id} - {f.title[:60]}..." if len(f.title) > 60 else f"{f.id} - {f.title}" for f in features]
        selected_feature_idx = st.selectbox(
            "Select Feature to Edit Team Assignment",
            options=range(len(features)),
            format_func=lambda i: feature_options[i],
            key="feature_selector"
        )
        
        if selected_feature_idx is not None:
            selected_feature = features[selected_feature_idx]
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                # Determine current team (from assigned_team or area_path)
                current_team = selected_feature.assigned_team
                if not current_team and selected_feature.area_path:
                    # Try to extract from area_path
                    area_parts = selected_feature.area_path.split("\\")
                    if area_parts:
                        current_team = area_parts[-1]
                
                # Find current team index in dropdown
                current_index = 0  # Default to "Unassigned"
                if current_team:
                    # Try to find exact match
                    if current_team in team_names:
                        current_index = team_names.index(current_team) + 1
                    else:
                        # Try partial match (e.g., "Team Ivy" matches "Ivy")
                        for idx, team_name in enumerate(team_names):
                            if current_team.lower() in team_name.lower() or team_name.lower() in current_team.lower():
                                current_index = idx + 1
                                break
                
                # Team selection dropdown - always shows all available teams
                team_options = ["Unassigned"] + team_names
                new_team = st.selectbox(
                    "Assign Team",
                    options=team_options,
                    index=current_index,
                    key=f"team_assign_{selected_feature.id}"
                )
                
                if st.button("💾 Save Team Assignment", key=f"save_team_{selected_feature.id}"):
                    selected_feature.assigned_team = new_team if new_team != "Unassigned" else None
                    st.success(f"✅ Team assigned: {new_team if new_team != 'Unassigned' else 'None'}")
                    st.rerun()
            
            with col_b:
                # Show feature details and edit target iteration
                st.markdown("**Feature Details:**")
                st.caption(f"**ID:** {selected_feature.id}")
                st.caption(f"**Title:** {selected_feature.title}")
                st.caption(f"**Area Path:** {selected_feature.area_path or 'N/A'}")
                st.caption(f"**Current Team:** {selected_feature.assigned_team or 'Unassigned'}")
                
                # Edit Target Iteration
                st.markdown("---")
                st.markdown("**🎯 Target Iteration:**")
                
                # Map milestone target dates to sprints if deadline_sprint is not set
                if not selected_feature.deadline_sprint and selected_feature.milestones and sprint_configs:
                    milestone_dates = [m.target_date for m in selected_feature.milestones if m.target_date]
                    if milestone_dates:
                        earliest_date = min(milestone_dates)
                        mapped_sprint = map_target_date_to_sprint(earliest_date, sprint_configs)
                        if mapped_sprint:
                            selected_feature.deadline_sprint = mapped_sprint
                
                # Show milestone info
                if selected_feature.milestones:
                    st.markdown("**Milestones:**")
                    for milestone in selected_feature.milestones:
                        target_date_str = milestone.target_date.strftime("%Y-%m-%d") if milestone.target_date else "No date"
                        target_sprint = map_target_date_to_sprint(milestone.target_date, sprint_configs) if milestone.target_date else None
                        st.caption(f"• {milestone.title}: {target_date_str} → {target_sprint or 'No sprint'}")
                else:
                    st.caption("No milestones")
                
                # Target iteration dropdown
                sprint_options = ["None"] + (list(sprint_configs.keys()) if sprint_configs else [])
                current_sprint_idx = 0
                if selected_feature.deadline_sprint:
                    try:
                        current_sprint_idx = sprint_options.index(selected_feature.deadline_sprint)
                    except ValueError:
                        current_sprint_idx = 0
                
                new_target_sprint = st.selectbox(
                    "Target Iteration",
                    options=sprint_options,
                    index=current_sprint_idx,
                    key=f"target_sprint_{selected_feature.id}",
                    help="Select the sprint by which this feature must be completed"
                )
                
                if st.button("💾 Save Target Iteration", key=f"save_target_{selected_feature.id}"):
                    selected_feature.deadline_sprint = new_target_sprint if new_target_sprint != "None" else None
                    st.success(f"✅ Target iteration set: {new_target_sprint if new_target_sprint != 'None' else 'None'}")
                    st.rerun()
    
    # User Stories summary
    total_us = sum(len(f.user_stories) for f in features) if features else 0
    st.markdown(f"### 📊 Summary: {total_us} User Stories across {len(features)} Features")

