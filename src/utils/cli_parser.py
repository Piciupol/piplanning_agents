"""CLI argument parser for PI Planning."""
import argparse
from typing import List, Optional


def create_parser() -> argparse.ArgumentParser:
    """Create and configure CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="AI-driven PI Planning Console Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with mock data (standard agents)
  python -m src.main start --project MyProject --pi-start 2025-12-01 --iterations 3 --teams team-a,team-b --mock

  # Run with AI agents
  python -m src.main start --project MyProject --pi-start 2025-12-01 --iterations 3 --teams team-a,team-b --mock --use-ai

  # Check ADO connection
  python -m src.main status --check-ado
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start PI planning")
    start_parser.add_argument(
        "--project",
        required=True,
        help="Azure DevOps project name"
    )
    start_parser.add_argument(
        "--pi-start",
        required=True,
        help="PI start date (YYYY-MM-DD)"
    )
    start_parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations (default: 3)"
    )
    start_parser.add_argument(
        "--iteration-names",
        help="Comma-separated iteration names (e.g., 'Sprint 1,Sprint 2,Sprint 3')"
    )
    start_parser.add_argument(
        "--teams",
        help="Comma-separated team IDs (e.g., 'team-a,team-b')"
    )
    start_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of ADO"
    )
    start_parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output)"
    )
    start_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode (less verbose output)"
    )
    start_parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Use AI-powered agents (requires Azure OpenAI credentials)"
    )
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check system status")
    status_parser.add_argument(
        "--check-ado",
        action="store_true",
        help="Check Azure DevOps connection"
    )
    
    return parser


def parse_iterations(args) -> List[str]:
    """
    Parse iteration names from arguments.
    
    Args:
        args: Parsed arguments
        
    Returns:
        List of iteration names
    """
    if args.iteration_names:
        return [name.strip() for name in args.iteration_names.split(",")]
    else:
        return [f"Iteration {i+1}" for i in range(args.iterations)]


def parse_teams(args) -> Optional[List[str]]:
    """
    Parse team IDs from arguments.
    
    Args:
        args: Parsed arguments
        
    Returns:
        List of team IDs or None
    """
    if args.teams:
        return [t.strip() for t in args.teams.split(",")]
    return None

