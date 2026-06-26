"""Textual TUI for chess."""

from __future__ import annotations

import os
import sys
from typing import Optional, List, Tuple

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Grid
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Header, Footer, Static, Button, Input, Label
from textual.worker import Worker, WorkerState, WorkerCancelled

from chess_cli.board import Board, Position
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.moves import Move, algebraic_to_pos, pos_to_algebraic, is_in_check
from chess_cli.game import Game
from chess_cli.ai import get_best_move


CSS_PATH = os.path.join(os.path.dirname(__file__), "tui_styles", "tui.tcss")


class Square(Static):
    """A single square on the chess board."""

    pos: Position

    class Clicked(Message):
        square: "Square"
        def __init__(self, square: "Square") -> None:
            super().__init__()
            self.square = square

    def __init__(self, pos: Position) -> None:
        self.pos = pos
        r, c = pos
        shade = "light" if (r + c) % 2 == 0 else "dark"
        super().__init__("", classes=f"square {shade}")

    def on_click(self) -> None:
        self.post_message(self.Clicked(self))

    def set_piece(self, piece: Optional[Piece]) -> None:
        if piece:
            # Use Rich markup to ensure piece color is always visible
            # regardless of the square's CSS color property.
            # White pieces -> dark foreground, black pieces -> light foreground.
            fg = "#000000" if piece.color == Color.WHITE else "#ffffff"
            self.update(f"[{fg}]{piece}[/]")
        else:
            self.update("")


class ModeScreen(ModalScreen[int]):
    """Screen to select game mode."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Select Game Mode", classes="title"),
            Button("Player vs Player", variant="primary", id="pvp"),
            Button("Player vs CPU (play White)", id="pvcpu"),
            Button("CPU vs Player (play Black)", id="cpuvp"),
            id="mode-grid",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {"pvp": 1, "pvcpu": 2, "cpuvp": 3}
        choice = mapping.get(event.button.id, 1)
        self.dismiss(choice)


class PromotionDialog(ModalScreen[PieceType]):
    """Dialog to choose promotion piece."""

    def __init__(self, color: Color) -> None:
        self._color = color
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Choose promotion piece:"),
            Button("Queen", variant="primary", id="queen"),
            Button("Rook", id="rook"),
            Button("Bishop", id="bishop"),
            Button("Knight", id="knight"),
            id="promo-grid",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {
            "queen": PieceType.QUEEN,
            "rook": PieceType.ROOK,
            "bishop": PieceType.BISHOP,
            "knight": PieceType.KNIGHT,
        }
        self.dismiss(mapping.get(event.button.id, PieceType.QUEEN))


class SaveDialog(ModalScreen[Optional[Tuple[str, str, str]]]):
    """Dialog to save PGN."""

    def compose(self) -> ComposeResult:
        from datetime import datetime
        default_fn = f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
        yield Grid(
            Label("Save PGN File"),
            Label("White name:"),
            Input(placeholder="White", id="white-name"),
            Label("Black name:"),
            Input(placeholder="Black", id="black-name"),
            Label("Filename:"),
            Input(value=default_fn, id="filename"),
            Button("Save", variant="primary", id="save"),
            Button("Cancel", id="cancel"),
            id="save-grid",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            white = self.query_one("#white-name", Input).value.strip() or "White"
            black = self.query_one("#black-name", Input).value.strip() or "Black"
            fname = self.query_one("#filename", Input).value.strip()
            if not fname:
                from datetime import datetime
                fname = f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
            self.dismiss((fname, white, black))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filename":
            self._do_save()

    def _do_save(self) -> None:
        fake = Button("Save", id="save")
        self.on_button_pressed(Button.Pressed(button=fake))


class HelpScreen(ModalScreen[None]):
    """Help overlay."""

    def compose(self) -> ComposeResult:
        text = chr(10).join([
            "  [bold]Chess TUI - Help[/]",
            "",
            "  Click a piece to select it.",
            "  Click a highlighted square to move.",
            "  Click the same piece again to deselect.",
            "",
            "  [bold]Keyboard[/]",
            "  [green]u[/]       - Undo last move",
            "  [green]q[/]       - Quit",
            "  [green]s[/]       - Save PGN",
            "  [green]n[/]       - New game",
            "  [green]h[/] / [?] - Show help",
            "  [green]Esc[/]     - Cancel / deselect",
            "",
            "  You can also type UCI moves (e.g. e2e4) in the input box.",
            "",
            "  [dim]Press any key to close[/]",
        ])
        yield Static(text, id="help-text")

    def on_key(self, event) -> None:
        self.dismiss(None)



class ChessApp(App):
    """Textual TUI for chess."""

    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("u", "undo", "Undo"),
        Binding("q", "quit", "Quit"),
        Binding("s", "save_pgn", "Save PGN"),
        Binding("n", "new_game", "New Game"),
        Binding("h,?", "show_help", "Help"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.game = Game()
        self.cpu_color: Optional[Color] = None
        self.selected_pos: Optional[Position] = None
        self.legal_targets: List[Position] = []
        self._pending_promotion: Optional[Tuple[Position, Position]] = None
        self._cpu_thinking = False

    def compose(self) -> ComposeResult:
        yield Static("Chess TUI", classes="header", id="title-bar")
        with Horizontal():
            with Vertical(id="board-container"):
                yield Label("    a   b   c   d   e   f   g   h", id="top-labels")
                with Grid(id="board-grid"):
                    for r in range(8):
                        for c in range(8):
                            yield Square((r, c))
                yield Label("    a   b   c   d   e   f   g   h", id="bottom-labels")
            with Vertical(id="sidebar"):
                yield Static(id="status")
                yield Static(id="move-log")
        with Horizontal(id="input-bar"):
            yield Input(placeholder="e2e4", id="move-input")
            yield Button("Send", id="send-btn", variant="primary")
        yield Static(
            "[U]ndo  [Q]uit  [S]ave PGN  [N]ew Game  [H]elp",
            classes="footer",
        )

    def on_mount(self) -> None:
        self.game = Game()
        self._push_mode_screen()

    def _push_mode_screen(self) -> None:
        self.push_screen(ModeScreen(), self._on_mode_selected)

    def _on_mode_selected(self, choice: int) -> None:
        if choice == 1:
            self.cpu_color = None
        elif choice == 2:
            self.cpu_color = Color.BLACK
        else:
            self.cpu_color = Color.WHITE

        mode_names = {None: "PvP", Color.BLACK: "PvCPU", Color.WHITE: "CPUvP"}
        mode_name = mode_names.get(self.cpu_color, "?")
        title = self.query_one("#title-bar", Static)
        title.update(f"Chess TUI  [{mode_name}]")

        self.refresh_board()
        self._update_status()
        self._maybe_run_cpu()

    def refresh_board(self) -> None:
        board = self.game.board
        last_from = self.game.move_history[-1].from_pos if self.game.move_history else None
        last_to = self.game.move_history[-1].to_pos if self.game.move_history else None

        for square in self.query(Square):
            r, c = square.pos
            piece = board.get_piece(r, c)
            square.set_piece(piece)

            square.remove_class("selected", "legal-target", "last-move", "check")

            if square.pos in (last_from, last_to):
                square.add_class("last-move")

            if piece and piece.piece_type == PieceType.KING:
                if is_in_check(board, piece.color):
                    square.add_class("check")

            if self.selected_pos and square.pos == self.selected_pos:
                square.add_class("selected")

            if square.pos in self.legal_targets:
                square.add_class("legal-target")

    def _update_status(self) -> None:
        status = self.query_one("#status", Static)
        move_log = self.query_one("#move-log", Static)

        lines = []
        if self.game.game_over:
            if self.game.winner:
                lines.append(f"[bold green]Checkmate![/] {self.game.winner.value.capitalize()} wins!")
            elif self.game.draw_reason == "insufficient material":
                lines.append("[bold yellow]Draw![/] Insufficient material.")
            elif self.game.draw_reason == "50-move rule":
                lines.append("[bold yellow]Draw![/] 50-move rule.")
            elif self.game.draw_reason == "threefold repetition":
                lines.append("[bold yellow]Draw![/] Threefold repetition.")
            else:
                lines.append("[bold yellow]Draw![/] Stalemate.")
        elif self._cpu_thinking:
            lines.append("[bold orange1]CPU is thinking...[/]")
        else:
            turn = self.game.current_turn.value.capitalize()
            lines.append(f"[bold]{turn}'s turn[/]")
            if is_in_check(self.game.board, self.game.current_turn):
                lines.append("[red]Check![/]")
            lines.append("")
            if self.selected_pos:
                sq = pos_to_algebraic(self.selected_pos)
                lines.append(f"Selected: {sq}  ({len(self.legal_targets)} moves)")

        lines.append(f"\nMoves: {len(self.game.move_history)}")
        status.update("\n".join(lines))

        if self.game.move_history:
            moves = [self.game.get_move_notation(m) for m in self.game.move_history]
            pairs = []
            for i in range(0, len(moves), 2):
                w = moves[i]
                b = moves[i + 1] if i + 1 < len(moves) else ""
                num = (i // 2) + 1
                pairs.append(f"{num:3}. {w:8s} {b}")
            ml_text = "\n".join(pairs[-20:])
            move_log.update(ml_text)
        else:
            move_log.update("[dim]No moves yet[/]")

    def _reset_selection(self) -> None:
        self.selected_pos = None
        self.legal_targets = []

    def _maybe_run_cpu(self) -> None:
        if (not self.game.game_over
                and self.cpu_color is not None
                and self.game.current_turn == self.cpu_color):
            self._run_cpu_move()

    @work(thread=True, exclusive=True)
    def _run_cpu_move(self) -> None:
        self._cpu_thinking = True
        self.call_from_thread(self._update_status)

        import time
        time.sleep(0.2)
        move = get_best_move(
            self.game.board, self.game.current_turn,
            en_passant_target=self.game.en_passant_target,
            depth=3,
        )
        self.call_from_thread(self._on_cpu_move_done, move)

    def _on_cpu_move_done(self, move: Optional[Move]) -> None:
        self._cpu_thinking = False
        if move:
            self.game.make_move_from_move(move)
            self._reset_selection()
            self.refresh_board()
            self._update_status()
            if not self.game.game_over:
                self._maybe_run_cpu()
        else:
            self._update_status()


    def on_square_clicked(self, event: Square.Clicked) -> None:
        if self.game.game_over or self._cpu_thinking:
            return

        pos = event.square.pos
        piece = self.game.board.get_piece(*pos)

        if self.selected_pos is None:
            if piece and piece.color == self.game.current_turn:
                self.selected_pos = pos
                legal = self.game.get_legal_moves()
                self.legal_targets = [m.to_pos for m in legal if m.from_pos == pos]
                self.refresh_board()
                self._update_status()
        else:
            from_pos = self.selected_pos
            if piece and piece.color == self.game.current_turn and pos != from_pos:
                self.selected_pos = pos
                legal = self.game.get_legal_moves()
                self.legal_targets = [m.to_pos for m in legal if m.from_pos == pos]
                self.refresh_board()
                self._update_status()
                return

            if pos == from_pos:
                self._reset_selection()
                self.refresh_board()
                self._update_status()
                return

            if pos in self.legal_targets:
                from_piece = self.game.board.get_piece(*from_pos)
                if (from_piece and from_piece.piece_type == PieceType.PAWN
                        and pos[0] in (0, 7)):
                    self._pending_promotion = (from_pos, pos)
                    self.push_screen(PromotionDialog(self.game.current_turn),
                                     self._on_promotion_chosen)
                    return

                success = self.game.make_move(from_pos, pos)
                if success:
                    self._reset_selection()
                    self.refresh_board()
                    self._update_status()
                    self._maybe_run_cpu()
                else:
                    self._reset_selection()
                    self.refresh_board()
                    self._update_status()
                    self._show_notification("Illegal move!")
            else:
                self._reset_selection()
                self.refresh_board()
                self._update_status()

    def _on_promotion_chosen(self, piece_type: Optional[PieceType]) -> None:
        if piece_type is None or self._pending_promotion is None:
            self._pending_promotion = None
            self._reset_selection()
            self.refresh_board()
            self._update_status()
            return

        from_pos, to_pos = self._pending_promotion
        self._pending_promotion = None

        legal = self.game.get_legal_moves()
        for move in legal:
            if (move.from_pos == from_pos and move.to_pos == to_pos
                    and move.promotion == piece_type):
                self.game.make_move_from_move(move)
                self._reset_selection()
                self.refresh_board()
                self._update_status()
                self._maybe_run_cpu()
                return

        self._reset_selection()
        self.refresh_board()
        self._update_status()
        self._show_notification("Invalid promotion!")


    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "move-input":
            self._do_text_move()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            self._do_text_move()

    def _do_text_move(self) -> None:
        if self.game.game_over or self._cpu_thinking:
            return

        input_widget = self.query_one("#move-input", Input)
        text = input_widget.value.strip().lower()

        if not text:
            return

        if text in ("undo", "u"):
            self._do_undo()
            input_widget.value = ""
            return

        if text in ("quit", "q"):
            self._do_quit()
            return

        if len(text) < 4:
            input_widget.value = ""
            self._show_notification("Invalid move format. Use e.g. e2e4")
            return

        from_sq = text[:2]
        to_sq = text[2:4]
        from_pos = algebraic_to_pos(from_sq)
        to_pos = algebraic_to_pos(to_sq)

        if from_pos is None or to_pos is None:
            input_widget.value = ""
            self._show_notification("Invalid square coordinates")
            return

        promo = None
        if len(text) >= 5:
            promo_map = {"q": PieceType.QUEEN, "r": PieceType.ROOK,
                         "b": PieceType.BISHOP, "n": PieceType.KNIGHT}
            promo = promo_map.get(text[4])

        legal = self.game.get_legal_moves()
        for move in legal:
            if (move.from_pos == from_pos and move.to_pos == to_pos
                    and (promo is None or move.promotion == promo)):
                if move.promotion and promo is None:
                    self._pending_promotion = (from_pos, to_pos)
                    self.push_screen(PromotionDialog(self.game.current_turn),
                                     self._on_promotion_chosen)
                    input_widget.value = ""
                    return
                self.game.make_move_from_move(move)
                self._reset_selection()
                self.refresh_board()
                self._update_status()
                self._maybe_run_cpu()
                input_widget.value = ""
                return

        input_widget.value = ""
        self._show_notification("Illegal move!")


    def action_undo(self) -> None:
        self._do_undo()

    def _do_undo(self) -> None:
        if self._cpu_thinking:
            return
        if self.game.undo_move():
            if self.cpu_color is not None:
                self.game.undo_move()
            self._reset_selection()
            self.refresh_board()
            self._update_status()
        self._show_notification("Move undone.")

    def action_quit(self) -> None:
        self._do_quit()

    def _do_quit(self) -> None:
        if self.game.move_history:
            self.push_screen(SaveDialog(), self._on_save_before_quit)
        else:
            self.exit()

    def _on_save_before_quit(self, result) -> None:
        if result:
            fname, white, black = result
            pgn = self.game.export_pgn(white_name=white, black_name=black)
            try:
                with open(fname, "w") as f:
                    f.write(pgn)
            except OSError:
                pass
        self.exit()

    def action_save_pgn(self) -> None:
        if not self.game.move_history:
            self._show_notification("No moves to save!")
            return
        self.push_screen(SaveDialog(), self._on_save_done)

    def _on_save_done(self, result) -> None:
        if result:
            fname, white, black = result
            pgn = self.game.export_pgn(white_name=white, black_name=black)
            try:
                with open(fname, "w") as f:
                    f.write(pgn)
                self._show_notification(f"Saved to {fname}")
            except OSError as e:
                self._show_notification(f"Error: {e}")

    def action_new_game(self) -> None:
        self.game = Game()
        self.cpu_color = None
        self._reset_selection()
        self._push_mode_screen()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_cancel(self) -> None:
        if self.selected_pos:
            self._reset_selection()
            self.refresh_board()
            self._update_status()

    def _show_notification(self, message: str) -> None:
        try:
            existing = self.query_one("#notification")
            existing.remove()
        except NoMatches:
            pass

        n = Static(message, id="notification")
        self.mount(n)
        self.set_timer(2.0, self._remove_notification)

    def _remove_notification(self) -> None:
        try:
            n = self.query_one("#notification")
            n.remove()
        except NoMatches:
            pass


def run_tui() -> None:
    """Launch the Textual TUI."""
    app = ChessApp()
    app.run()
