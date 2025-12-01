"""Visualization components for PI Planning."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from typing import List

def visualize_team_utilization(assignments: List, teams: List, iterations: List[str]):
    """Create team utilization chart."""
    if not assignments or not teams:
        return None
    
    # Calculate utilization per team/iteration
    data = []
    for team in teams:
        for iteration in iterations:
            # team_id in assignments is team name, not team.id
            team_assignments = [a for a in assignments if a.team_id == team.name and a.iteration == iteration]
            total_effort = sum(a.effort for a in team_assignments)
            
            # Use capacity_per_sprint if available, otherwise fallback to capacity_per_iteration
            capacity = None
            if hasattr(team, 'capacity_per_sprint') and team.capacity_per_sprint:
                # Try exact match first
                if iteration in team.capacity_per_sprint:
                    sprint_capacity = team.capacity_per_sprint[iteration]
                    if isinstance(sprint_capacity, dict):
                        capacity = sprint_capacity.get("total", None)
                    else:
                        capacity = sprint_capacity
                else:
                    # Try to find by partial match (e.g., "Sprint 1" vs "Sprint 1")
                    for sprint_key, sprint_value in team.capacity_per_sprint.items():
                        if sprint_key.strip() == iteration.strip() or sprint_key == iteration:
                            if isinstance(sprint_value, dict):
                                capacity = sprint_value.get("total", None)
                            else:
                                capacity = sprint_value
                            break
            
            # Fallback to capacity_per_iteration if capacity_per_sprint not found
            if capacity is None:
                capacity = team.capacity_per_iteration if hasattr(team, 'capacity_per_iteration') else 40
            
            utilization = (total_effort / capacity * 100) if capacity > 0 else 0
            
            # Debug: Print if utilization seems wrong
            if utilization > 99.5 and utilization < 100.5 and total_effort < capacity:
                # This shouldn't happen - utilization should be less than 100% if total_effort < capacity
                print(f"DEBUG: {team.name} {iteration}: total_effort={total_effort}, capacity={capacity}, utilization={utilization}%")
            
            data.append({
                "Team": team.name,
                "Iteration": iteration,
                "Used": total_effort,
                "Capacity": capacity,
                "Utilization %": min(utilization, 150)  # Cap at 150% for visualization
            })
    
    df = pd.DataFrame(data)
    
    # Create bar chart
    fig = px.bar(
        df,
        x="Iteration",
        y="Utilization %",
        color="Team",
        barmode="group",
        title="Team Capacity Utilization",
        labels={"Utilization %": "Utilization (%)"},
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    # Add 100% line
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% Capacity")
    
    fig.update_layout(height=400)
    return fig


def visualize_feature_timeline(assignments: List, features: List, iterations: List[str]):
    """Create feature timeline visualization."""
    if not assignments:
        return None
    
    # Group by feature and iteration
    feature_iter_data = {}
    for assignment in assignments:
        feat_id = assignment.feature_id
        if feat_id not in feature_iter_data:
            feature = next((f for f in features if f.id == feat_id), None)
            feature_iter_data[feat_id] = {
                "Feature": feature.title if feature else f"Feature {feat_id}",
                "Effort": {}
            }
        
        iter_name = assignment.iteration
        if iter_name not in feature_iter_data[feat_id]["Effort"]:
            feature_iter_data[feat_id]["Effort"][iter_name] = 0
        feature_iter_data[feat_id]["Effort"][iter_name] += assignment.effort
    
    # Create data for heatmap
    heatmap_data = []
    for feat_id, data in feature_iter_data.items():
        for iteration in iterations:
            effort = data["Effort"].get(iteration, 0)
            # Use feature ID + title to ensure uniqueness
            feature_label = f"{feat_id}: {data['Feature'][:30]}"
            heatmap_data.append({
                "Feature": feature_label,
                "Iteration": iteration,
                "Effort (SP)": effort
            })
    
    if not heatmap_data:
        return None
    
    df = pd.DataFrame(heatmap_data)
    
    # Create heatmap using pivot_table to handle duplicates (e.g., split stories)
    # Sum effort if same feature appears multiple times in same iteration
    pivot_df = df.pivot_table(
        index="Feature", 
        columns="Iteration", 
        values="Effort (SP)", 
        aggfunc='sum',
        fill_value=0
    )
    
    fig = px.imshow(
        pivot_df,
        labels=dict(x="Iteration", y="Feature", color="Effort (SP)"),
        title="Feature Effort Distribution Across Iterations",
        color_continuous_scale="Blues",
        aspect="auto"
    )
    
    fig.update_layout(height=max(400, len(pivot_df) * 40))
    return fig


def visualize_dependencies(features: List, assignments: List = None, iterations: List[str] = None):
    """Create dependency graph visualization with iteration-based positioning."""
    if not features:
        return None
    
    # Create mapping of assignments to iterations and sequence order
    assignment_map = {}  # {us_id: (iteration, sequence_order)}
    feature_iteration_map = {}  # {feature_id: iteration}
    
    if assignments and iterations:
        for assignment in assignments:
            if assignment.user_story_id:
                assignment_map[assignment.user_story_id] = (
                    assignment.iteration,
                    assignment.sequence_order or 999
                )
            if assignment.feature_id:
                # Feature iteration is the LATEST iteration of its US (when feature is completed)
                if assignment.feature_id not in feature_iteration_map:
                    feature_iteration_map[assignment.feature_id] = assignment.iteration
                else:
                    # Keep latest iteration (completion iteration)
                    current_iter_idx = iterations.index(feature_iteration_map[assignment.feature_id])
                    new_iter_idx = iterations.index(assignment.iteration)
                    if new_iter_idx > current_iter_idx:
                        feature_iteration_map[assignment.feature_id] = assignment.iteration
    
    # Create NetworkX graph
    G = nx.DiGraph()
    
    # Add nodes and edges
    feature_nodes = []
    story_nodes = []
    
    # Add Feature nodes
    for feature in features:
        node_id = f"F{feature.id}"
        iteration = feature_iteration_map.get(feature.id, None)
        iter_label = f" (ends {iteration})" if iteration else ""
        G.add_node(node_id, 
                   label=f"F{feature.id}: {feature.title[:30]}{iter_label}",
                   type="feature",
                   size=20,
                   color="#1f77b4",
                   iteration=iteration)
        feature_nodes.append(node_id)
        
        # Add Feature -> Feature dependencies
        for dep_feat_id in feature.depends_on_features:
            dep_node_id = f"F{dep_feat_id}"
            G.add_edge(dep_node_id, node_id, type="feature_dep", color="#1f77b4")
    
    # Add User Story nodes and dependencies
    for feature in features:
        for us in feature.user_stories:
            us_node_id = f"US{us.id}"
            iteration, sequence_order = assignment_map.get(us.id, (None, 999))
            iter_label = f" ({iteration})" if iteration else ""
            G.add_node(us_node_id,
                      label=f"US{us.id}: {us.title[:25]}{iter_label}",
                      type="user_story",
                      size=10,
                      color="#ff7f0e",
                      iteration=iteration,
                      sequence_order=sequence_order)
            story_nodes.append(us_node_id)
            
            # Link US to parent Feature
            feat_node_id = f"F{feature.id}"
            G.add_edge(feat_node_id, us_node_id, type="contains", color="#888888", style="dashed")
            
            # Add US -> Feature dependencies
            for dep_feat_id in us.depends_on_features:
                dep_node_id = f"F{dep_feat_id}"
                if dep_node_id in G:
                    G.add_edge(dep_node_id, us_node_id, type="us_feat_dep", color="#ff7f0e")
            
            # Add US -> US dependencies
            for dep_us_id in us.depends_on_stories:
                dep_us_node_id = f"US{dep_us_id}"
                if dep_us_node_id in G:
                    G.add_edge(dep_us_node_id, us_node_id, type="us_dep", color="#ff7f0e")
    
    if len(G.nodes()) == 0:
        return None
    
    # Position nodes based on iterations (left to right) and sequence order (top to bottom)
    pos = {}
    if iterations:
        # Group nodes by iteration
        iteration_groups = {iter: [] for iter in iterations}
        unassigned = []
        
        for node_id in G.nodes():
            node_data = G.nodes[node_id]
            iteration = node_data.get("iteration")
            if iteration and iteration in iteration_groups:
                iteration_groups[iteration].append(node_id)
            else:
                unassigned.append(node_id)
        
        # Position nodes: x based on iteration index, y based on sequence order
        x_spacing = 3.0
        y_spacing = 1.5
        
        for iter_idx, iteration in enumerate(iterations):
            nodes_in_iter = iteration_groups[iteration]
            if not nodes_in_iter:
                continue
            
            # Sort by sequence_order (if available) or by node_id
            nodes_in_iter.sort(key=lambda n: (
                G.nodes[n].get("sequence_order", 999),
                n
            ))
            
            # Position nodes in this iteration
            num_nodes = len(nodes_in_iter)
            start_y = (num_nodes - 1) * y_spacing / 2
            
            for node_idx, node_id in enumerate(nodes_in_iter):
                x = iter_idx * x_spacing
                y = start_y - node_idx * y_spacing
                pos[node_id] = (x, y)
        
        # Position unassigned nodes to the right
        if unassigned:
            unassigned.sort(key=lambda n: (
                G.nodes[n].get("sequence_order", 999),
                n
            ))
            num_unassigned = len(unassigned)
            start_y = (num_unassigned - 1) * y_spacing / 2
            for node_idx, node_id in enumerate(unassigned):
                x = len(iterations) * x_spacing
                y = start_y - node_idx * y_spacing
                pos[node_id] = (x, y)
    else:
        # Fallback to spring layout if no iterations
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Prepare edge traces
    edge_traces = []
    edge_types = {
        "feature_dep": {"color": "#1f77b4", "width": 3},
        "us_feat_dep": {"color": "#ff7f0e", "width": 2},
        "us_dep": {"color": "#ff7f0e", "width": 2},
        "contains": {"color": "#888888", "width": 1, "dash": "dash"}
    }
    
    for edge_type, style in edge_types.items():
        edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("type") == edge_type]
        if edges:
            edge_x = []
            edge_y = []
            for u, v in edges:
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
            
            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=style["width"], color=style["color"], dash=style.get("dash", "solid")),
                hoverinfo='none',
                mode='lines',
                showlegend=True,
                name=edge_type.replace("_", " ").title()
            )
            edge_traces.append(edge_trace)
    
    # Prepare node traces (separate for Features and User Stories)
    feature_x = []
    feature_y = []
    feature_text = []
    feature_hover = []
    
    story_x = []
    story_y = []
    story_text = []
    story_hover = []
    
    for node_id in G.nodes():
        x, y = pos[node_id]
        node_data = G.nodes[node_id]
        label = node_data.get("label", node_id)
        node_type = node_data.get("type", "unknown")
        
        if node_type == "feature":
            feature_x.append(x)
            feature_y.append(y)
            feature_text.append(node_id)
            feature_hover.append(label)
        else:
            story_x.append(x)
            story_y.append(y)
            story_text.append(node_id)
            story_hover.append(label)
    
    # Create node traces
    node_traces = []
    
    if feature_x:
        feature_trace = go.Scatter(
            x=feature_x, y=feature_y,
            mode='markers+text',
            name='Features',
            text=feature_text,
            textposition="middle center",
            textfont=dict(size=10, color="white"),
            hovertext=feature_hover,
            hoverinfo='text',
            marker=dict(
                size=30,
                color='#1f77b4',
                line=dict(width=2, color='white')
            )
        )
        node_traces.append(feature_trace)
    
    if story_x:
        story_trace = go.Scatter(
            x=story_x, y=story_y,
            mode='markers+text',
            name='User Stories',
            text=story_text,
            textposition="middle center",
            textfont=dict(size=8, color="white"),
            hovertext=story_hover,
            hoverinfo='text',
            marker=dict(
                size=20,
                color='#ff7f0e',
                line=dict(width=1, color='white')
            )
        )
        node_traces.append(story_trace)
    
    # Create figure
    fig = go.Figure(data=edge_traces + node_traces)
    
    fig.update_layout(
        title="Dependency Graph",
        showlegend=True,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        annotations=[dict(
            text="Blue = Features, Orange = User Stories<br>Blue lines = Feature dependencies, Orange = Story dependencies",
            showarrow=False,
            xref="paper", yref="paper",
            x=0.005, y=-0.002,
            xanchor="left", yanchor="bottom",
            font=dict(size=10, color="#666")
        )],
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600,
        plot_bgcolor='white'
    )
    
    return fig
