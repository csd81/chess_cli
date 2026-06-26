"""CLI interface for the chess game."""

import os
import sys
import time
from typing import Optional
from chess_cli.game import Game
from chess_cli.pieces import Color
from chess_cli.moves import algebraic_to_pos, pos_to_algebraic
from chess_cli.ai import get_best_move


class ChessCLI:
    """Command-line interface for playing chess."""

    MODES = {1: "Player vs Player", 2: "Player vs CPU", 3: "CPU vs Player", 4: "AI vs AI"}

    def __init__(self) -> None:
        self.game = Game()
        self.highlighted_squares: list = []
        self.highlighted_piece: Optional[str] = None
        self.cpu_color: Optional[Color] = None
        self.ai_vs_ai = False
        self.ai_depth_white = 3
        self.ai_depth_black = 3
        self._select_mode()

    def _select_mode(self) -> None:
        """Prompt the user to select game mode at startup."""
        self.clear_screen()
        print("=== CHESS CLI ===")
        print()
        print("Select mode:")
        print("  1. Player vs Player")
        print("  2. Player vs CPU (play as White)")
        print("  3. CPU vs Player (play as Black)")
        print("  4. AI vs AI (Spectator)")
        print()
        while True:
            try:
                choice = input("Enter choice (1-4): ").strip()
                if choice == "1":
                    self.cpu_color = None
                    break
                elif choice == "2":
                    self.cpu_color = Color.BLACK
                    break
                elif choice == "3":
                    self.cpu_color = Color.WHITE
                    break
                elif choice == "4":
                    self.cpu_color = None
                    self.ai_vs_ai = True
                    break
                print("Invalid choice. Enter 1, 2, 3, or 4.")
            except (EOFError, KeyboardInterrupt):
                print()
                print("Goodbye!")
                sys.exit(0)

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    def display(self) -> None:
        """Display the current board state."""
        self.clear_screen()
        mode_name = self.MODES.get(
            4 if self.ai_vs_ai else (
                1 if self.cpu_color is None else (2 if self.cpu_color == Color.BLACK else 3)
            ),
            "?"
        )
        print(f"=== CHESS CLI [{mode_name}] ===")
        print()
        print(self.game.board.display(
            highlight_squares=self.highlighted_squares,
            last_move=(self.game.move_history[-1].from_pos, self.game.move_history[-1].to_pos)
            if self.game.move_history else None
        ))
        print()
        if self.game.move_history:
            moves = [self.game.get_move_notation(m) for m in self.game.move_history]
            print("Moves:", " ".join(moves[-10:]))
            print()
        if self.game.game_over:
            if self.game.winner:
                print(f"Checkmate! {self.game.winner.value.capitalize()} wins!")
            elif self.game.draw_reason == "insufficient material":
                print("Draw! Insufficient material.")
            elif self.game.draw_reason == "50-move rule":
                print("Draw by 50-move rule!")
            elif self.game.draw_reason == "threefold repetition":
                print("Draw by threefold repetition!")
            else:
                print("Stalemate! The game is a draw.")
        else:
            turn_name = self.game.current_turn.value.capitalize()
            status = f"{turn_name}'s turn"
            if self.highlighted_piece:
                status += f" — showing moves for {self.highlighted_piece}"
            print(status)

    def parse_move(self, move_str: str):
        """Parse a move string like e2e4 or e7e8q into positions."""
        move_str = move_str.strip().lower()
        if move_str in ("quit", "q", "exit"):
            return "quit"
        if move_str in ("help", "h", "?"):
            return "help"
        if move_str in ("undo", "u"):
            return "undo"
        # Handle "moves" and "moves e2"
        if move_str.startswith("moves"):
            parts = move_str.split()
            if len(parts) >= 2:
                sq = parts[1]
                pos = algebraic_to_pos(sq)
                if pos:
                    return ("moves_sq", pos)
            return "moves"
        if len(move_str) < 4:
            return None
        from_sq = move_str[:2]
        to_sq = move_str[2:4]
        from_pos = algebraic_to_pos(from_sq)
        to_pos = algebraic_to_pos(to_sq)
        if from_pos is None or to_pos is None:
            return None
        return (from_pos, to_pos)

    def show_help(self) -> None:
        """Display help information."""
        print()
        print("=== HELP ===")
        print("Enter moves in UCI notation: <from><to>")
        print("  Example: e2e4 (move pawn from e2 to e4)")
        print("  Example: e7e8q (promote pawn to queen)")
        print()
        print("Commands:")
        print("  moves       - Show all legal moves")
        print("  moves <sq>  - Highlight moves for a piece (e.g. moves e2)")
        print("  undo        - Undo the last move")
        print("  help        - Show this help")
        print("  quit        - Exit the game")
        print()
        print("Press Enter to continue...")
        input()

    def show_legal_moves(self, square_pos=None) -> None:
        """Display legal moves. If square_pos given, highlight targets on board."""
        legal = self.game.get_legal_moves()
        if not legal:
            print()
            print("No legal moves available.")
            print("Press Enter to continue...")
            input()
            return

        if square_pos:
            # Highlight moves for a specific piece
            targets = [m.to_pos for m in legal if m.from_pos == square_pos]
            if not targets:
                sq = pos_to_algebraic(square_pos)
                print()
                print(f"No legal moves for {sq}.")
                print("Press Enter to continue...")
                input()
                return
            self.highlighted_squares = [square_pos] + targets
            self.highlighted_piece = pos_to_algebraic(square_pos)
            # Do NOT pause — redraw on next loop iteration
            return

        print()
        print(f"Legal moves ({len(legal)}):")
        for move in legal:
            notation = self.game.get_move_notation(move)
            print(f"  {notation:8s} ({move.uci()})")
        print()
        print("Press Enter to continue...")
        input()

    def _prompt_save_pgn(self) -> None:
        """Ask the user if they want to save the game as a PGN file."""
        if not self.game.move_history:
            return
        try:
            print()
            resp = input("Save game to PGN file? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if resp != "y" and resp != "yes":
            return

        # Get player names
        try:
            white_name = input("White player name [White]: ").strip()
            black_name = input("Black player name [Black]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not white_name:
            white_name = "White"
        if not black_name:
            black_name = "Black"

        # Get filename
        date_str = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"chess_game_{date_str}.pgn"
        try:
            fname = input(f"Filename [{default_name}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not fname:
            fname = default_name

        pgn = self.game.export_pgn(white_name=white_name, black_name=black_name)
        try:
            with open(fname, "w") as f:
                f.write(pgn)
            print(f"Game saved to {fname}")
        except OSError as e:
            print(f"Error saving file: {e}")
        print("Press Enter to continue...")
        input()

    def _run_ai_move(self) -> bool:
        """Compute and execute one AI move. Returns False if no legal move."""
        depth = self.ai_depth_white if self.game.current_turn == Color.WHITE else self.ai_depth_black
        if self.ai_vs_ai:
            delay = 1.0
            label = "AI White" if self.game.current_turn == Color.WHITE else "AI Black"
        else:
            delay = 0.5
            label = "CPU"
        time.sleep(delay)
        move = get_best_move(
            self.game.board, self.game.current_turn,
            en_passant_target=self.game.en_passant_target,
            depth=depth,
        )
        if move:
            notation = self.game.get_move_notation(move)
            print(f"{label} plays: {notation} ({move.uci()})")
            self.game.make_move_from_move(move)
            self.highlighted_squares = []
            self.highlighted_piece = None
            return True
        else:
            print(f"{label} has no legal moves!")
            return False

    def _auto_save_pgn(self) -> None:
        """Auto-save PGN for AI vs AI games."""
        if not self.game.move_history:
            return
        from datetime import datetime
        fname = f"ai_vs_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
        pgn = self.game.export_pgn(white_name="AI White", black_name="AI Black")
        try:
            with open(fname, "w") as f:
                f.write(pgn)
            print(f"Game saved to {fname}")
        except OSError as e:
            print(f"Error saving file: {e}")

    def run(self) -> None:
        """Main game loop."""
        while not self.game.game_over:
            # AI turn: auto-compute and play
            is_ai_turn = self.ai_vs_ai or (
                self.cpu_color is not None and self.game.current_turn == self.cpu_color
            )
            if is_ai_turn:
                self.display()
                if self.ai_vs_ai:
                    label = "AI White" if self.game.current_turn == Color.WHITE else "AI Black"
                    print(f"{label} is thinking...")
                else:
                    print("CPU is thinking...")
                print()
                ok = self._run_ai_move()
                if not ok:
                    input("Press Enter to continue...")
                    break
                if self.game.game_over:
                    continue
                if not self.ai_vs_ai:
                    print("Press Enter to continue...")
                    input()
                continue

            # Human turn
            self.display()
            try:
                cmd = input("Enter move: ")
            except (EOFError, KeyboardInterrupt):
                print()
                print("Goodbye!")
                self._prompt_save_pgn()
                return
            result = self.parse_move(cmd)
            if result == "quit":
                print("Goodbye!")
                self._prompt_save_pgn()
                return
            elif result == "help":
                self.show_help()
                continue
            elif result == "moves":
                self.show_legal_moves()
                continue
            elif isinstance(result, tuple) and result[0] == "moves_sq":
                _, sq_pos = result
                self.show_legal_moves(square_pos=sq_pos)
                continue
            elif result == "undo":
                if self.game.undo_move():
                    print("Move undone.")
                else:
                    print("No moves to undo!")
                print("Press Enter to continue...")
                input()
                continue
            elif result is None:
                print("Invalid input. Try again or type 'help'.")
                continue
            from_pos, to_pos = result
            success = self.game.make_move(from_pos, to_pos)
            if success:
                self.highlighted_squares = []
                self.highlighted_piece = None
            if not success:
                print("Illegal move! Press Enter to continue...")
                input()
        self.display()
        print()
        if self.ai_vs_ai:
            self._auto_save_pgn()
        else:
            self._prompt_save_pgn()
        print("Press Enter to exit...")
        input()


def main() -> None:
    """Entry point for the chess CLI."""
    cli = ChessCLI()
    cli.run()


if __name__ == "__main__":
    main()