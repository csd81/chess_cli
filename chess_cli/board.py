"""Board representation and display for chess."""

import os
from typing import Optional, List, Tuple
from chess_cli.pieces import Piece, Color, PieceType

# Convenience type for a board position
Position = Tuple[int, int]  # (row, col) where 0,0 is a8 (top-left in standard display)

# Enable ANSI escape sequences on Windows
if os.name == "nt":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# ANSI 256-color codes for board display
BG_LIGHT = "\033[48;5;255m"      # Near-white
BG_DARK = "\033[48;5;95m"        # Warm brown (wooden board feel)
BG_LAST_MOVE = "\033[48;5;228m"  # Soft yellow
FG_BLACK_PIECE = "\033[38;5;0m"    # Black text (for white pieces on light/yellow)
FG_WHITE_PIECE = "\033[38;5;255m"  # White text (for black pieces on dark/yellow)
RESET = "\033[0m"


class Board:
    """An 8x8 chess board.

    Internally stored as a list of lists (rows 0-7, cols 0-7).
    Row 0 = rank 8 (top), Row 7 = rank 1 (bottom).
    Col 0 = file 'a' (left), Col 7 = file 'h' (right).
    """

    SIZE = 8

    def __init__(self) -> None:
        """Set up the board in the standard starting position."""
        self.grid: List[List[Optional[Piece]]] = [[None] * self.SIZE for _ in range(self.SIZE)]
        self._setup_initial_position()

    def _setup_initial_position(self) -> None:
        """Place all pieces in the standard starting arrangement."""
        # Back ranks
        back_rank_order = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP,
            PieceType.QUEEN, PieceType.KING,
            PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK,
        ]

        # Black back rank (row 0)
        for col, pt in enumerate(back_rank_order):
            self.grid[0][col] = Piece(Color.BLACK, pt)

        # Black pawns (row 1)
        for col in range(self.SIZE):
            self.grid[1][col] = Piece(Color.BLACK, PieceType.PAWN)

        # White pawns (row 6)
        for col in range(self.SIZE):
            self.grid[6][col] = Piece(Color.WHITE, PieceType.PAWN)

        # White back rank (row 7)
        for col, pt in enumerate(back_rank_order):
            self.grid[7][col] = Piece(Color.WHITE, pt)

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        """Get the piece at a given position, or None if empty."""
        if not self._in_bounds(row, col):
            return None
        return self.grid[row][col]

    def set_piece(self, row: int, col: int, piece: Optional[Piece]) -> None:
        """Place (or remove) a piece at the given position."""
        if self._in_bounds(row, col):
            self.grid[row][col] = piece

    def move_piece(self, from_row: int, from_col: int, to_row: int, to_col: int) -> Optional[Piece]:
        """Move a piece from one square to another. Returns the captured piece, if any."""
        piece = self.grid[from_row][from_col]
        captured = self.grid[to_row][to_col]
        self.grid[to_row][to_col] = piece
        self.grid[from_row][from_col] = None
        if piece is not None:
            piece.has_moved = True
        return captured

    def find_king(self, color: Color) -> Optional[Position]:
        """Find the king of the given color. Returns (row, col) or None."""
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                p = self.grid[r][c]
                if p and p.color == color and p.piece_type == PieceType.KING:
                    return (r, c)
        return None

    def get_all_pieces(self, color: Color) -> List[Tuple[Position, Piece]]:
        """Return all pieces of a given color with their positions."""
        result = []
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                p = self.grid[r][c]
                if p and p.color == color:
                    result.append(((r, c), p))
        return result

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.SIZE and 0 <= col < self.SIZE

    def to_fen(self) -> str:
        """Serialize the board to a FEN string (piece placement only)."""
        fen_rows = []
        for row in range(self.SIZE):
            empty_count = 0
            fen_row = ""
            for col in range(self.SIZE):
                p = self.grid[row][col]
                if p is None:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        fen_row += str(empty_count)
                        empty_count = 0
                    fen_letter = p.fen_letter()
                    fen_row += fen_letter
            if empty_count > 0:
                fen_row += str(empty_count)
            fen_rows.append(fen_row)
        return "/".join(fen_rows)

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        """Create a board from a FEN string (piece placement only)."""
        board = cls.__new__(cls)
        board.grid = [[None] * cls.SIZE for _ in range(cls.SIZE)]
        # Strip trailing FEN metadata (castling, en passant, move counts, etc.)
        board_part = fen.split()[0]
        rows = board_part.split("/")
        for r, row_str in enumerate(rows):
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    c += int(ch)
                else:
                    color = Color.WHITE if ch.isupper() else Color.BLACK
                    piece = Piece.from_letter(ch, color)
                    if piece:
                        board.grid[r][c] = piece
                    c += 1
        return board

    def display(self, reversed_view: bool = True,
                highlight_squares: Optional[List[Position]] = None,
                last_move: Optional[Tuple[Position, Position]] = None) -> str:
        """Return a string representation of the board with ANSI colors.

        Args:
            reversed_view: If True, show from white's perspective (rank 1 at bottom).
                           If False, show from black's perspective.
            highlight_squares: List of (row, col) positions to highlight.
                Empty squares appear as [ ], pieces appear as [P] or [p].
            last_move: Tuple of (from_pos, to_pos) for the last move.
                These squares get a yellow background highlight.
        """
        if highlight_squares is None:
            highlight_squares = []

        # Determine last move squares for yellow background
        last_from = last_move[0] if last_move else None
        last_to = last_move[1] if last_move else None

        lines = []
        rows = range(self.SIZE)
        if reversed_view:
            rows = reversed(range(self.SIZE))

        lines.append("  +---+---+---+---+---+---+---+---+")
        for i, r in enumerate(rows):
            rank_label = (8 - r) if reversed_view else (r + 1)
            row_cells = []
            for c in range(self.SIZE):
                p = self.grid[r][c]

                # Determine background color
                if (r, c) == last_from or (r, c) == last_to:
                    bg = BG_LAST_MOVE
                elif (r + c) % 2 == 0:
                    bg = BG_LIGHT
                else:
                    bg = BG_DARK

                # Determine foreground (text) color for pieces
                if p:
                    fg = FG_BLACK_PIECE if p.color == Color.WHITE else FG_WHITE_PIECE
                else:
                    fg = ""

                # Build visible content (always 3 characters wide)
                if (r, c) in highlight_squares:
                    content = f"[{str(p)}]" if p else "[ ]"
                else:
                    content = f" {str(p)} " if p else "   "

                cell = f"{bg}{fg}{content}{RESET}"
                row_cells.append(cell)
            lines.append(f"{rank_label} |{'|'.join(row_cells)}|")
            if i < self.SIZE - 1:
                lines.append("  +---+---+---+---+---+---+---+---+")
        lines.append("  +---+---+---+---+---+---+---+---+")
        lines.append("    a   b   c   d   e   f   g   h  ")
        return "\n".join(lines)
