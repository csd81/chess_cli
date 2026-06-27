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

    def __init__(self, fen: str = None) -> None:
        if fen:
            self._init_from_fen(fen)
        else:
            self._init_standard()

    def _init_standard(self) -> None:
        """Initialize from the standard starting position."""
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

    def _init_from_fen(self, fen: str) -> None:
        """Initialize from a FEN string."""
        parts = fen.split()
        self.board = Board.from_fen(parts[0])
        self.current_turn = Color.WHITE if len(parts) > 1 and parts[1] == 'w' else Color.BLACK
        self.move_history = []
        self.selected_pos = None
        self.legal_moves = []
        self.game_over = False
        self.winner = None
        self.draw_reason = ""
        self.halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
        self._halfmove_clock_history = []
        self.position_history = {}

        # Parse castling rights
        cr = parts[2] if len(parts) > 2 else "-"
        self.castling_rights = {
            Color.WHITE: {"kingside": "K" in cr, "queenside": "Q" in cr},
            Color.BLACK: {"kingside": "k" in cr, "queenside": "q" in cr},
        }

        # Fix has_moved flags for kings and rooks based on castling rights
        self._fix_has_moved_from_fen()

        # Parse en passant target
        ep_str = parts[3] if len(parts) > 3 else "-"
        if ep_str != "-":
            self.en_passant_target = algebraic_to_pos(ep_str)
        else:
            self.en_passant_target = None

        # Record initial position for threefold repetition
        key = self._get_position_key()
        self.position_history[key] = 1

        # Check for game-over conditions at the start position
        self._check_game_over()

    def _check_game_over(self) -> None:
        """Check if the current position is checkmate, stalemate, or draw."""
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

    def _fix_has_moved_from_fen(self) -> None:
        """Set has_moved=True on kings/rooks that have lost castling rights."""
        g = self.board.grid
        rights = self.castling_rights

        # White king
        wk = g[7][4]
        if wk and wk.piece_type == PieceType.KING and wk.color == Color.WHITE:
            if not (rights[Color.WHITE]["kingside"] or rights[Color.WHITE]["queenside"]):
                wk.has_moved = True

        # White rooks
        wr1 = g[7][7]
        if wr1 and wr1.piece_type == PieceType.ROOK and wr1.color == Color.WHITE:
            if not rights[Color.WHITE]["kingside"]:
                wr1.has_moved = True
        wr2 = g[7][0]
        if wr2 and wr2.piece_type == PieceType.ROOK and wr2.color == Color.WHITE:
            if not rights[Color.WHITE]["queenside"]:
                wr2.has_moved = True

        # Black king
        bk = g[0][4]
        if bk and bk.piece_type == PieceType.KING and bk.color == Color.BLACK:
            if not (rights[Color.BLACK]["kingside"] or rights[Color.BLACK]["queenside"]):
                bk.has_moved = True

        # Black rooks
        br1 = g[0][7]
        if br1 and br1.piece_type == PieceType.ROOK and br1.color == Color.BLACK:
            if not rights[Color.BLACK]["kingside"]:
                br1.has_moved = True
        br2 = g[0][0]
        if br2 and br2.piece_type == PieceType.ROOK and br2.color == Color.BLACK:
            if not rights[Color.BLACK]["queenside"]:
                br2.has_moved = True

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

    def make_move_from_uci(self, uci_str: str) -> bool:
        """Execute a move from a UCI string (e.g. 'e2e4', 'e7e8q').

        Returns True if successful.
        """
        if len(uci_str) < 4:
            return False
        from_pos = algebraic_to_pos(uci_str[:2])
        to_pos = algebraic_to_pos(uci_str[2:4])
        if from_pos is None or to_pos is None:
            return False

        promo_letter = uci_str[4] if len(uci_str) >= 5 else None
        promo_map = {"q": PieceType.QUEEN, "r": PieceType.ROOK,
                     "b": PieceType.BISHOP, "n": PieceType.KNIGHT}
        promo_pt = promo_map.get(promo_letter) if promo_letter else None

        legal = self.get_legal_moves()
        for move in legal:
            if (move.from_pos == from_pos and move.to_pos == to_pos
                    and move.promotion == promo_pt):
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