"""Main entry point for PI Planning Console Application."""
import asyncio
import sys
from pathlib import Path

from src.ui.console_ui import ConsoleUI
from src.core.orchestrator import Orchestrator
from src.utils.cli_parser import create_parser, parse_iterations, parse_teams
from src.utils.output_manager import OutputManager
from src.utils.status_checker import check_ado_connection, check_ai_config
from src.utils.config import Config


async def run_pi_planning(args, console_ui: ConsoleUI):
    """
    Run PI planning workflow.
    
    Args:
        args: Parsed CLI arguments
        console_ui: Console UI instance
    """
    # Parse arguments
    iterations = parse_iterations(args)
    teams = parse_teams(args)
    output_dir = Path(args.output_dir)
    
    # Check AI config if requested
    if args.use_ai:
        check_ai_config(console_ui)
    
    # Create orchestrator and run planning
    orchestrator = Orchestrator(console_ui=console_ui)
    
    try:
        result = await orchestrator.run_pi_planning(
            project=args.project,
            pi_start=args.pi_start,
            iterations=iterations,
            teams=teams or [],
            use_mock_data=args.mock,
            use_ai_agents=args.use_ai
        )
        
        if not result:
            console_ui.display_error("PI planning failed")
            sys.exit(1)
        
        # Save outputs
        output_manager = OutputManager(output_dir)
        saved_files = output_manager.save_all(
            program_board=result["program_board"],
            transcript=result["transcript"]
        )
        
        # Display saved files
        console_ui.display_success("Output files saved:")
        for file_type, file_path in saved_files.items():
            console_ui.display_info(f"  {file_type}: {file_path}")
        
    except KeyboardInterrupt:
        console_ui.display_warning("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        console_ui.display_error(f"Error: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_status_check(args, console_ui: ConsoleUI):
    """
    Run status checks.
    
    Args:
        args: Parsed CLI arguments
        console_ui: Console UI instance
    """
    if args.check_ado:
        success = check_ado_connection(console_ui)
        sys.exit(0 if success else 1)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    console_ui = ConsoleUI(verbose=not (args.quiet if hasattr(args, 'quiet') else False))
    
    if args.command == "start":
        asyncio.run(run_pi_planning(args, console_ui))
    elif args.command == "status":
        run_status_check(args, console_ui)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
