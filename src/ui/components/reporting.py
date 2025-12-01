import streamlit as st
import pandas as pd
from datetime import datetime
from src.ui.visualizations import visualize_team_utilization, visualize_feature_timeline, visualize_dependencies
from src.utils.output_manager import generate_excel_report, generate_html_report

def display_final_report(features, teams, iterations, assignments, ai_insights=None, risks=None, objectives=None):
    """Display final PI planning report with visualizations and export options."""
    
    st.markdown("---")
    st.header("📊 Final PI Plan")
    
    if not assignments:
        st.error("No assignments found. Planning may have failed.")
        return

    # --- Metrics ---
    total_stories = sum(len(f.user_stories) for f in features)
    assigned_stories = len(assignments)
    assigned_features = len(set(a.feature_id for a in assignments if a.feature_id))
    num_teams = len(teams) if teams else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Features Planned", f"{assigned_features}/{len(features)}")
    col2.metric("User Stories Assigned", f"{assigned_stories}/{total_stories}")
    col3.metric("Completion Rate", f"{assigned_stories/total_stories*100:.1f}%" if total_stories else "0%")
    col4.metric("Number of Teams", num_teams)

    # --- AI Insights ---
    if ai_insights:
        st.markdown("---")
        st.subheader("🤖 AI Insights & Recommendations")
        
        if isinstance(ai_insights, dict):
            # Display structured insights
            if "observations" in ai_insights and ai_insights["observations"]:
                with st.expander("🔍 Key Observations", expanded=True):
                    for obs in ai_insights["observations"]:
                        st.markdown(f"• {obs}")
            
            if "issues" in ai_insights and ai_insights["issues"]:
                with st.expander("⚠️ Potential Issues", expanded=False):
                    for issue in ai_insights["issues"]:
                        st.markdown(f"• {issue}")
            
            if "recommendations" in ai_insights and ai_insights["recommendations"]:
                with st.expander("💡 Recommendations", expanded=False):
                    for rec in ai_insights["recommendations"]:
                        st.markdown(f"• {rec}")
            
            if "success_factors" in ai_insights and ai_insights["success_factors"]:
                with st.expander("✅ Success Factors", expanded=False):
                    for factor in ai_insights["success_factors"]:
                        st.markdown(f"• {factor}")
        else:
            # Display raw insights if not structured
            st.info(ai_insights)

    # --- Visualizations ---
    st.subheader("📈 Plan Visualizations")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Capacity", "Dependencies", "Risks"])
    
    with tab1:
        fig_timeline = visualize_feature_timeline(assignments, features, iterations)
        if fig_timeline:
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("Not enough data for timeline.")
            
    with tab2:
        fig_util = visualize_team_utilization(assignments, teams, iterations)
        if fig_util:
            st.plotly_chart(fig_util, use_container_width=True)
        else:
            st.info("Not enough data for capacity chart.")
            
    with tab3:
        fig_dep = visualize_dependencies(features, assignments, iterations)
        if fig_dep:
            st.plotly_chart(fig_dep, use_container_width=True)
        else:
            st.info("No dependencies to visualize.")
            
    with tab4:
        st.markdown("#### ⚠️ Identified Risks")
        
        # Debug: Show what we received
        if risks is None:
            st.warning("⚠️ No risks data received from planning.")
        elif len(risks) == 0:
            st.info("ℹ️ Risk agent returned empty list.")
        
        # Display risks from risk_agent
        if risks and len(risks) > 0:
            risks_data = []
            for risk in risks:
                # Handle Risk objects (from risk_agent) or dicts
                if hasattr(risk, 'title'):
                    risks_data.append({
                        "Title": risk.title,
                        "Description": risk.description or "",
                        "Impact": risk.impact.value if hasattr(risk.impact, 'value') else str(risk.impact),
                        "Probability": f"{risk.probability*100:.0f}%" if hasattr(risk, 'probability') else "N/A",
                        "Risk Score": f"{risk.risk_score:.1f}" if hasattr(risk, 'risk_score') else "N/A",
                        "Mitigation": risk.mitigation or "",
                        "Status": risk.status if hasattr(risk, 'status') else "identified"
                    })
                elif isinstance(risk, dict):
                    risks_data.append({
                        "Title": risk.get("title", "Unknown Risk"),
                        "Description": risk.get("description", ""),
                        "Impact": risk.get("impact", "N/A"),
                        "Probability": f"{risk.get('probability', 0)*100:.0f}%" if risk.get('probability') else "N/A",
                        "Risk Score": f"{risk.get('risk_score', 0):.1f}" if risk.get('risk_score') else "N/A",
                        "Mitigation": risk.get("mitigation", ""),
                        "Status": risk.get("status", "identified")
                    })
            
            if risks_data:
                df_risks = pd.DataFrame(risks_data)
                st.dataframe(df_risks, use_container_width=True, hide_index=True)
                
                # Summary
                st.info(f"**Total Risks Identified:** {len(risks_data)}")
            else:
                st.success("No risks identified by risk agent.")
        else:
            # Fallback: Check for overdue stories if no risks from agent
            overdue_risks = []
            for assignment in assignments:
                feature = next((f for f in features if f.id == assignment.feature_id), None)
                if feature and feature.deadline_sprint:
                    try:
                        # Simple check: if assigned iteration index > deadline iteration index
                        if assignment.iteration in iterations and feature.deadline_sprint in iterations:
                            assigned_idx = iterations.index(assignment.iteration)
                            deadline_idx = iterations.index(feature.deadline_sprint)
                            
                            if assigned_idx > deadline_idx:
                                overdue_risks.append({
                                    "Type": "Overdue",
                                    "Item": f"US {assignment.user_story_id}",
                                    "Description": f"Planned in {assignment.iteration}, but deadline was {feature.deadline_sprint}",
                                    "Severity": "High"
                                })
                    except ValueError:
                        pass # Iteration not found in list
            
            if overdue_risks:
                st.table(pd.DataFrame(overdue_risks))
            else:
                st.success("No major scheduling risks identified.")

    # --- PI Objectives ---
    if objectives and len(objectives) > 0:
        st.markdown("---")
        st.subheader("🎯 PI Objectives")
        
        objectives_data = []
        for obj in objectives:
            # Handle PIObjective objects or dicts
            if hasattr(obj, 'title'):
                obj_data = {
                    "Title": obj.title,
                    "Description": obj.description or "",
                    "Business Value": f"{obj.business_value:.1f}" if hasattr(obj, 'business_value') else "N/A",
                    "Features": ", ".join([str(fid) for fid in obj.features]) if hasattr(obj, 'features') and obj.features else "None",
                    "Status": obj.status if hasattr(obj, 'status') else "draft"
                }
                # Add metrics if available
                if hasattr(obj, 'metrics') and obj.metrics:
                    metrics_str = ", ".join([f"{k}: {v}" for k, v in obj.metrics.items()])
                    obj_data["Metrics"] = metrics_str
                objectives_data.append(obj_data)
            elif isinstance(obj, dict):
                obj_data = {
                    "Title": obj.get("title", "Unknown Objective"),
                    "Description": obj.get("description", ""),
                    "Business Value": f"{obj.get('business_value', 0):.1f}",
                    "Features": ", ".join([str(fid) for fid in obj.get("feature_ids", [])]),
                    "Status": obj.get("status", "draft")
                }
                if obj.get("metrics"):
                    metrics_str = ", ".join([f"{k}: {v}" for k, v in obj["metrics"].items()])
                    obj_data["Metrics"] = metrics_str
                objectives_data.append(obj_data)
        
        if objectives_data:
            df_objectives = pd.DataFrame(objectives_data)
            st.dataframe(df_objectives, use_container_width=True, hide_index=True)
            st.info(f"**Total PI Objectives:** {len(objectives_data)}")
        else:
            st.info("No objectives data to display.")
    else:
        st.markdown("---")
        st.subheader("🎯 PI Objectives")
        st.info("No PI Objectives generated.")

    # --- Detailed Plan Table ---
    st.subheader("📋 Detailed Plan")
    
    plan_data = []
    for a in assignments:
        feature = next((f for f in features if f.id == a.feature_id), None)
        plan_data.append({
            "Iteration": a.iteration,
            "Team": a.team_id, # This is the team name
            "Feature": feature.title if feature else "Unknown",
            "User Story ID": a.user_story_id,
            "Effort": a.effort
        })
        
    st.dataframe(pd.DataFrame(plan_data))

    # --- Export Options ---
    st.subheader("💾 Export Plan")
    col_ex1, col_ex2 = st.columns(2)
    
    with col_ex1:
        if st.button("📥 Download Excel Report"):
            filename = f"pi_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            try:
                # Prepare data dictionary - ensure all required keys are present
                data = {
                    "features": features or [],
                    "teams": teams or [],
                    "iterations": iterations or [],
                    "assignments": assignments or []
                }
                # Call with single dict argument
                excel_bytes = generate_excel_report(data)
                st.download_button(
                    label="Click to Download Excel",
                    data=excel_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                import traceback
                st.error(f"Error generating Excel: {e}")
                st.code(traceback.format_exc())

    with col_ex2:
        if st.button("🌐 Download HTML Report"):
            filename = f"pi_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
            try:
                # Prepare data dictionary
                data = {
                    "features": features,
                    "teams": teams,
                    "iterations": iterations,
                    "assignments": assignments
                }
                html_content = generate_html_report(data)
                st.download_button(
                    label="Click to Download HTML",
                    data=html_content.encode('utf-8'),
                    file_name=filename,
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Error generating HTML: {e}")

