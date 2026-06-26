"""Game state management for chess."""

from typing import List, Optional, Tuple
from datetime import datetime
from chess_cli.board import Board
from chess_cli.pieces import Color, Piece, PieceType
from chess_cli.moves import (
    Move, generate_legal_moves, is_in_check,
    is_checkmate, is_stalemate, is_insufficient_material,
    algebraic_to_pos, pos_to_algebraic
)


class Game:
    """Represents a complete chess game with move history and state."""

    def __init__(self) -> None:
        self.board = Board()
        self.current_turn: Color = Color.WHITE
        self.move_history: List[Move] = []
        self.selected_pos: Optional[Tuple[int, int]] = None
        self.legal_moves: List[Move] = []
        self.game_over: bool = False
        self.winner: Optional[Color] = None
        self.en_passant_target: Optional[Tuple[int, int]] = None
        self.draw_reason: str = ""
        self.halfmove_clock: int = 0
        self._halfmove_clock_history: list[int] = []
        self.position_history: dict[str, int] = {}
        self.castling_rights = {
            Color.WHITE: {"kingside": True, "queenside": True},
            Color.BLACK: {"kingside": True, "queenside": True},
        }

    def get_legal_moves(self) -> List[Move]:
        """Get all legal moves for the current player."""
        return generate_legal_moves(self.board, self.current_turn,
                                    en_passant_target=self.en_passant_target)

    def make_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """Attempt to make a move. Returns True if successful."""
        legal = self.get_legal_moves()
        for move in legal:
            if move.from_pos == from_pos and move.to_pos == to_pos:
                self._execute_move(move)
                return True
        return False

    def make_move_from_move(self, move: Move) -> None:
        """Execute a pre-validated Move object directly (used by AI)."""
        self._execute_move(move)

    def _execute_move(self, move: Move) -> None:
        """Execute a move on the board and update state."""
        # Record whether the piece had moved before this move (for undo)
        move.piece_had_moved = move.piece.has_moved

        # Reset en passant target
        self.en_passant_target = None

        # Set new en passant target if a pawn moved two squares
        if move.piece.piece_type == PieceType.PAWN:
            dr = abs(move.to_pos[0] - move.from_pos[0])
            if dr == 2:
                mid_row = (move.from_pos[0] + move.to_pos[0]) // 2
                self.en_passant_target = (mid_row, move.from_pos[1])

        # Execute the move
        captured = self.board.move_piece(
            move.from_pos[0], move.from_pos[1],
            move.to_pos[0], move.to_pos[1]
        )

        # Handle en passant: remove the captured pawn
        if move.is_en_passant:
            # The captured pawn is on the same row as the capturing pawn,
            # at the target column (it moved two squares last turn)
            ep_captured = self.board.grid[move.from_pos[0]][move.to_pos[1]]
            if ep_captured:
                captured = ep_captured
                self.board.set_piece(move.from_pos[0], move.to_pos[1], None)

        # Handle castling rook movement
        if move.is_castle:
            row = move.from_pos[0]
            if move.to_pos[1] > move.from_pos[1]:  # Kingside
                self.board.move_piece(row, 7, row, 5)
            else:  # Queenside
                self.board.move_piece(row, 0, row, 3)

        # Handle promotion
        if move.promotion:
            self.board.set_piece(
                move.to_pos[0], move.to_pos[1],
                Piece(self.current_turn, move.promotion)
            )

        # Record check/checkmate status on the move
        opponent = self.current_turn.opponent()
        if is_checkmate(self.board, opponent):
            move.gave_mate = True
        elif is_in_check(self.board, opponent):
            move.gave_check = True

        # Update move history
        move.captured = captured
        self.move_history.append(move)

        # Check for game over
        self.current_turn = opponent

        # Update halfmove clock (resets on pawn move or capture)
        self._halfmove_clock_history.append(self.halfmove_clock)
        if move.piece.piece_type == PieceType.PAWN or captured is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Record position in history (after turn switch)
        key = self._get_position_key()
        self.position_history[key] = self.position_history.get(key, 0) + 1

        if is_checkmate(self.board, self.current_turn):
            self.game_over = True
            self.winner = self.current_turn.opponent()
            self.draw_reason = ""
        elif is_stalemate(self.board, self.current_turn):
            self.game_over = True
            self.draw_reason = "stalemate"
        elif is_insufficient_material(self.board):
            self.game_over = True
            self.winner = None
            self.draw_reason = "insufficient material"
        elif self.halfmove_clock >= 100:
            self.game_over = True
            self.winner = None
            self.draw_reason = "50-move rule"
        elif self.position_history.get(key, 0) >= 3:
            self.game_over = True
            self.winner = None
            self.draw_reason = "threefold repetition"

    def undo_move(self) -> bool:
        """Undo the last move. Returns True if successful."""
        if not self.move_history:
            return False

        # Record the position key of the position being undone (before popping)
        current_key = self._get_position_key()
        move = self.move_history.pop()

        # Switch turn back
        self.current_turn = self.current_turn.opponent()

        # Reset game over states
        self.game_over = False
        self.winner = None
        self.draw_reason = ""

        # Restore halfmove clock from history
        if self._halfmove_clock_history:
            self.halfmove_clock = self._halfmove_clock_history.pop()
        else:
            self.halfmove_clock = 0

        # Decrement position history for the undone position
        if current_key in self.position_history:
            self.position_history[current_key] -= 1
            if self.position_history[current_key] <= 0:
                del self.position_history[current_key]

        # Revert piece position
        piece = self.board.grid[move.to_pos[0]][move.to_pos[1]]
        self.board.set_piece(move.from_pos[0], move.from_pos[1], piece)
        self.board.set_piece(move.to_pos[0], move.to_pos[1], None)

        # Revert has_moved flag
        piece.has_moved = move.piece_had_moved

        # Restore captured piece
        if move.is_en_passant:
            # En passant: restore the captured pawn on its original square
            ep_square = (move.from_pos[0], move.to_pos[1])
            self.board.set_piece(ep_square[0], ep_square[1], move.captured)
            # The capturing pawn is already back at from_pos (handled above)
        elif move.captured:
            # Standard capture: put captured piece back
            self.board.set_piece(move.to_pos[0], move.to_pos[1], move.captured)

        # Revert castling: move rook back
        if move.is_castle:
            row = move.from_pos[0]
            if move.to_pos[1] > move.from_pos[1]:  # Kingside
                rook = self.board.grid[row][5]
                self.board.set_piece(row, 7, rook)
                self.board.set_piece(row, 5, None)
                if rook:
                    rook.has_moved = False
            else:  # Queenside
                rook = self.board.grid[row][3]
                self.board.set_piece(row, 0, rook)
                self.board.set_piece(row, 3, None)
                if rook:
                    rook.has_moved = False

        # Re-enable castling rights if rook/king was moved back to original
        # (simplified: castling is re-allowed if the relevant piece is back home)

        # Recalculate en passant target from the new last move
        self._recalc_en_passant_target()

        return True

    def _recalc_en_passant_target(self) -> None:
        """Recalculate en passant target from the last move in history."""
        self.en_passant_target = None
        if self.move_history:
            last_move = self.move_history[-1]
            if (last_move.piece.piece_type == PieceType.PAWN and
                    abs(last_move.to_pos[0] - last_move.from_pos[0]) == 2):
                mid_row = (last_move.from_pos[0] + last_move.to_pos[0]) // 2
                self.en_passant_target = (mid_row, last_move.from_pos[1])

    def _get_position_key(self) -> str:
        """Generate a unique key for the current position (for threefold repetition)."""
        fen = self.board.to_fen()
        turn = self.current_turn.value
        # Castling rights: encode as KQkq string
        castling = ""
        for color in [Color.WHITE, Color.BLACK]:
            rights = self.castling_rights[color]
            sym = "K" if color == Color.WHITE else "k"
            q_sym = "Q" if color == Color.WHITE else "q"
            if rights["kingside"]:
                castling += sym
            if rights["queenside"]:
                castling += q_sym
        if not castling:
            castling = "-"
        # En passant target
        ep = pos_to_algebraic(self.en_passant_target) if self.en_passant_target else "-"
        return f"{fen} {turn} {castling} {ep}"

    def get_move_notation(self, move: Move) -> str:
        """Return a human-readable notation for a move."""
        piece_letter = move.piece.letter()
        capture = "x" if move.captured else ""
        to_sq = pos_to_algebraic(move.to_pos)
        if move.is_castle:
            notation = "O-O" if move.to_pos[1] > move.from_pos[1] else "O-O-O"
        else:
            promo = f"={move.promotion.name[0]}" if move.promotion else ""
            notation = f"{piece_letter}{capture}{to_sq}{promo}"
        # Append check/checkmate symbol (recorded at move execution time)
        if move.gave_mate:
            notation += "#"
        elif move.gave_check:
            notation += "+"
        return notation

    def export_pgn(self, white_name: str = "White", black_name: str = "Black") -> str:
        """Export the game to a Portable Game Notation (PGN) string."""
        # Result string
        if self.game_over:
            if self.winner == Color.WHITE:
                result = "1-0"
            elif self.winner == Color.BLACK:
                result = "0-1"
            else:
                result = "1/2-1/2"  # draw (stalemate or insufficient material)
        else:
            result = "*"

        # Date
        date_str = datetime.now().strftime("%Y.%m.%d")

        # Build headers (7-tag roster)
        headers = [
            f'[Event "Casual Game"]',
            f'[Site "Chess CLI"]',
            f'[Date "{date_str}"]',
            f'[Round "1"]',
            f'[White "{white_name}"]',
            f'[Black "{black_name}"]',
            f'[Result "{result}"]',
        ]

        # Build move text
        move_text_parts = []
        for i in range(0, len(self.move_history), 2):
            turn_number = (i // 2) + 1
            w_move = self.move_history[i]
            w_notation = self.get_move_notation(w_move)
            if i + 1 < len(self.move_history):
                b_move = self.move_history[i + 1]
                b_notation = self.get_move_notation(b_move)
                move_text_parts.append(f"{turn_number}. {w_notation} {b_notation}")
            else:
                move_text_parts.append(f"{turn_number}. {w_notation}")

        # Join move text into lines of max ~80 chars
        full_move_text = " ".join(move_text_parts)
        if full_move_text:
            full_move_text += f" {result}"
        else:
            full_move_text = result

        # Wrap move text at ~80 chars per line
        wrapped_lines = []
        words = full_move_text.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 > 78:
                wrapped_lines.append(current_line)
                current_line = word
            else:
                current_line = f"{current_line} {word}" if current_line else word
        if current_line:
            wrapped_lines.append(current_line)

        # Assemble PGN
        pgn_lines = headers + [""] + wrapped_lines + [""]
        return "\n".join(pgn_lines)

    def __str__(self) -> str:
        return self.board.display()