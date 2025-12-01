"""Console UI for displaying agent conversations."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from src.core.models import Message, ProgramBoard, Transcript, Risk, PIObjective


class ConsoleUI:
    """Console UI for displaying agent conversations and results."""
    
    def __init__(self, verbose: bool = True):
        """
        Initialize console UI.
        
        Args:
            verbose: Enable verbose output
        """
        self.console = Console()
        self.verbose = verbose
        self.messages: list[Message] = []
    
    def log_message(self, message: Message):
        """
        Log and display a message between agents.
        
        Args:
            message: Message object to display
        """
        self.messages.append(message)
        
        if not self.verbose:
            return
        
        # Format timestamp
        ts = message.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Color coding
        sender_color = self._get_agent_color(message.from_agent)
        receiver_color = self._get_agent_color(message.to_agent)
        
        # Build message display
        msg_text = Text()
        msg_text.append(f"[{ts}] ", style="dim cyan")
        msg_text.append(message.from_agent, style=f"bold {sender_color}")
        msg_text.append(" -> ", style="dim")
        msg_text.append(message.to_agent, style=f"bold {receiver_color}")
        msg_text.append(f": {message.message_type}", style="yellow")
        
        # Display main message
        self.console.print(msg_text)
        
        # Display payload if present
        if message.payload:
            payload_str = json.dumps(message.payload, indent=2, default=str)
            self.console.print(f"  Payload: {payload_str}", style="dim")
        
        # Display response if present
        if message.response:
            response_str = json.dumps(message.response, indent=2, default=str)
            self.console.print(f"  Response: {response_str}", style="dim green")
    
    def _get_agent_color(self, agent_name: str) -> str:
        """Get color for agent name."""
        colors = {
            "DataAgent": "blue",
            "WSJFAgent": "cyan",
            "ProgramManager": "magenta",
            "TeamAgent": "green",
            "DependencyAgent": "yellow",
            "ReportingAgent": "red",
        }
        
        # Check if it's a TeamAgent with team name
        if "TeamAgent" in agent_name:
            return "green"
        
        return colors.get(agent_name, "white")
    
    def display_header(self, title: str, subtitle: Optional[str] = None):
        """Display a header panel."""
        content = title
        if subtitle:
            content += f"\n[dim]{subtitle}[/dim]"
        
        panel = Panel(
            content,
            title="[bold cyan]PI Planning Console[/bold cyan]",
            border_style="cyan"
        )
        self.console.print(panel)
    
    def display_summary(self, plan: ProgramBoard):
        """Display final plan summary."""
        table = Table(title="Final PI Plan Summary", show_header=True, header_style="bold magenta")
        table.add_column("Feature ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Team", style="green")
        table.add_column("Iteration", style="yellow")
        table.add_column("Effort", style="blue", justify="right")
        table.add_column("WSJF", style="magenta", justify="right")
        
        # Sort assignments by iteration, then team
        sorted_assignments = sorted(
            plan.assignments,
            key=lambda a: (a.iteration, a.team_id)
        )
        
        for assignment in sorted_assignments:
            feature = next((f for f in plan.features if f.id == assignment.feature_id), None)
            if feature:
                table.add_row(
                    str(feature.id),
                    feature.title[:50] + "..." if len(feature.title) > 50 else feature.title,
                    assignment.team_id,
                    assignment.iteration,
                    str(assignment.effort),
                    f"{feature.wsjf:.2f}" if feature.wsjf else "N/A"
                )
        
        self.console.print("\n")
        self.console.print(table)
        
        # Display PI Objectives if available
        if plan.pi_objectives:
            self.display_objectives_summary(plan.pi_objectives)
        
        # Display team capacity utilization
        self.console.print("\n")
        self._display_team_utilization(plan)
    
    def _display_team_utilization(self, plan: ProgramBoard):
        """Display team capacity utilization."""
        table = Table(title="Team Capacity Utilization", show_header=True, header_style="bold green")
        table.add_column("Team", style="cyan")
        table.add_column("Iteration", style="yellow")
        table.add_column("Used", style="blue", justify="right")
        table.add_column("Capacity", style="blue", justify="right")
        table.add_column("Utilization", style="magenta", justify="right")
        
        # Calculate utilization per team per iteration
        team_iteration_load = {}
        for assignment in plan.assignments:
            key = (assignment.team_id, assignment.iteration)
            if key not in team_iteration_load:
                team_iteration_load[key] = 0
            team_iteration_load[key] += assignment.effort
        
        for team in plan.teams:
            for iteration in plan.iterations:
                key = (team.id, iteration)
                used = team_iteration_load.get(key, 0)
                capacity = team.capacity_per_iteration
                utilization = (used / capacity * 100) if capacity > 0 else 0
                
                table.add_row(
                    team.name,
                    iteration,
                    f"{used:.1f}",
                    str(capacity),
                    f"{utilization:.1f}%"
                )
        
        self.console.print(table)
    
    def save_transcript(self, transcript: Transcript, filepath: Path):
        """Save transcript to JSON file."""
        transcript_dict = transcript.model_dump(mode="json")
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(transcript_dict, f, indent=2, default=str)
        
        self.console.print(f"\n[green]✓[/green] Transcript saved to {filepath}")
    
    def save_program_board(self, plan: ProgramBoard, filepath: Path):
        """Save program board to JSON file."""
        plan_dict = plan.model_dump(mode="json")
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2, default=str)
        
        self.console.print(f"[green]✓[/green] Program board saved to {filepath}")
    
    def prompt_commit(self) -> bool:
        """Prompt user to commit plan to ADO."""
        response = self.console.input("\n[bold yellow]Commit plan to ADO?[/bold yellow] (y/N): ")
        return response.lower() in ("y", "yes")
    
    def display_error(self, error: str):
        """Display an error message."""
        self.console.print(f"[bold red]Error:[/bold red] {error}")
    
    def display_info(self, info: str):
        """Display an info message."""
        self.console.print(f"[cyan]ℹ[/cyan] {info}")
    
    def display_success(self, message: str):
        """Display a success message."""
        self.console.print(f"[green]✓[/green] {message}")
    
    def display_risks_summary(self, risks: List[Risk]):
        """Display risks summary table."""
        table = Table(title="Identified Risks", show_header=True, header_style="bold red")
        table.add_column("Risk", style="cyan")
        table.add_column("Impact", style="yellow")
        table.add_column("Probability", style="blue", justify="right")
        table.add_column("Score", style="magenta", justify="right")
        table.add_column("Mitigation", style="white")
        
        # Sort by risk score
        sorted_risks = sorted(risks, key=lambda r: r.risk_score, reverse=True)
        
        for risk in sorted_risks[:10]:  # Show top 10
            table.add_row(
                risk.title[:50] + "..." if len(risk.title) > 50 else risk.title,
                risk.impact.value.upper(),
                f"{risk.probability:.1%}",
                f"{risk.risk_score:.2f}",
                risk.mitigation[:40] + "..." if risk.mitigation and len(risk.mitigation) > 40 else (risk.mitigation or "N/A")
            )
        
        self.console.print("\n")
        self.console.print(table)
    
    def display_objectives_summary(self, objectives: List[PIObjective]):
        """Display PI Objectives summary."""
        table = Table(title="PI Objectives", show_header=True, header_style="bold cyan")
        table.add_column("Objective", style="white")
        table.add_column("Business Value", style="green", justify="right")
        table.add_column("Features", style="blue", justify="right")
        table.add_column("Status", style="yellow")
        
        for obj in objectives:
            table.add_row(
                obj.title[:50] + "..." if len(obj.title) > 50 else obj.title,
                str(obj.business_value),
                str(len(obj.features)),
                obj.status.upper()
            )
        
        self.console.print("\n")
        self.console.print(table)
