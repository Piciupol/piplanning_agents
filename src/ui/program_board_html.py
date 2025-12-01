"""HTML generator for Program Board visualization."""
from pathlib import Path
from typing import List
from datetime import datetime

from src.core.models import ProgramBoard, Risk, PIObjective


def generate_html_program_board(board: ProgramBoard) -> str:
    """
    Generate HTML Program Board visualization.
    
    Args:
        board: ProgramBoard object
        
    Returns:
        HTML content as string
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Program Board - {board.project}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .board {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
            }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .risk-high {{
            background-color: #ffebee;
        }}
        .risk-medium {{
            background-color: #fff3e0;
        }}
        .risk-low {{
            background-color: #e8f5e9;
        }}
        .objective {{
            background-color: #e3f2fd;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #2196f3;
        }}
        .risk {{
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #f44336;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Program Board - {board.project}</h1>
        <p>PI Start: {board.pi_start} | Iterations: {', '.join(board.iterations)}</p>
        <p>Generated: {board.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="board">
        <h2>Feature Assignments</h2>
        <table>
            <thead>
                <tr>
                    <th>Feature ID</th>
                    <th>Title</th>
                    <th>Team</th>
                    <th>Iteration</th>
                    <th>Effort (SP)</th>
                    <th>WSJF</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Sort assignments by iteration, then team
    sorted_assignments = sorted(
        board.assignments,
        key=lambda a: (a.iteration, a.team_id)
    )
    
    for assignment in sorted_assignments:
        feature = next((f for f in board.features if f.id == assignment.feature_id), None)
        if feature:
            wsjf_val = f"{feature.wsjf_score:.2f}" if feature.wsjf_score is not None else "N/A"
            html += f"""
                <tr>
                    <td>{feature.id}</td>
                    <td>{feature.title[:50]}</td>
                    <td>{assignment.team_id}</td>
                    <td>{assignment.iteration}</td>
                    <td>{assignment.effort:.1f}</td>
                    <td>{wsjf_val}</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
    </div>
"""
    
    # PI Objectives
    if board.pi_objectives:
        html += """
    <div class="board">
        <h2>PI Objectives</h2>
"""
        for obj in board.pi_objectives:
            html += f"""
        <div class="objective">
            <h3>{obj.title}</h3>
            <p>{obj.description}</p>
            <p><strong>Business Value:</strong> {obj.business_value}/10 | <strong>Features:</strong> {len(obj.features)} | <strong>Status:</strong> {obj.status}</p>
        </div>
"""
        html += """
    </div>
"""
    
    # Risks
    if board.risks:
        html += """
    <div class="board">
        <h2>Identified Risks</h2>
"""
        # Sort by risk score
        sorted_risks = sorted(board.risks, key=lambda r: r.risk_score, reverse=True)
        
        for risk in sorted_risks:
            risk_class = f"risk-{risk.impact.value}"
            html += f"""
        <div class="risk {risk_class}">
            <h3>{risk.title}</h3>
            <p>{risk.description}</p>
            <p><strong>Impact:</strong> {risk.impact.value.upper()} | <strong>Probability:</strong> {risk.probability:.1%} | <strong>Risk Score:</strong> {risk.risk_score:.2f}</p>
            {f'<p><strong>Mitigation:</strong> {risk.mitigation}</p>' if risk.mitigation else ''}
        </div>
"""
        html += """
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html
