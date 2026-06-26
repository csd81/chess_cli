"""Chess CLI/TUI - Entry point."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Chess CLI/TUI")
    parser.add_argument("--tui", "-t", action="store_true",
                        help="Launch the Textual TUI (default: classic CLI)")
    args = parser.parse_args()

    if args.tui:
        try:
            from chess_cli.tui import run_tui
            run_tui()
        except ImportError as e:
            print(f"Error: TUI mode requires 'textual' library. {e}", file=sys.stderr)
            sys.exit(1)
    else:
        from chess_cli.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
