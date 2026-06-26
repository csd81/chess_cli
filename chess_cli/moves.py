"""Move generation and validation for chess."""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board, Position


DIRECTIONS = {
    PieceType.ROOK: [(-1, 0), (1, 0), (0, -1), (0, 1)],
    PieceType.BISHOP: [(-1, -1), (-1, 1), (1, -1), (1, 1)],
    PieceType.QUEEN: [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)],
}

KNIGHT_OFFSETS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                  (1, -2), (1, 2), (2, -1), (2, 1)]

KING_OFFSETS = [(-1, -1), (-1, 0), (-1, 1),
                (0, -1),          (0, 1),
                (1, -1),  (1, 0), (1, 1)]


@dataclass
class Move:
    """Represents a single move."""
    from_pos: Position
    to_pos: Position
    piece: Piece
    captured: Optional[Piece] = None
    promotion: Optional[PieceType] = None
    is_castle: bool = False
    is_en_passant: bool = False
    piece_had_moved: bool = False
    gave_check: bool = False
    gave_mate: bool = False

    def uci(self) -> str:
        """Return the move in UCI notation (e.g. e2e4, e7e8q)."""
        from_str = pos_to_algebraic(self.from_pos)
        to_str = pos_to_algebraic(self.to_pos)
        result = from_str + to_str
        if self.promotion:
            m = {PieceType.QUEEN: "q", PieceType.ROOK: "r",
                 PieceType.BISHOP: "b", PieceType.KNIGHT: "n"}
            result += m.get(self.promotion, "")
        return result

    def __repr__(self) -> str:
        return "Move(" + self.uci() + ")"

def pos_to_algebraic(pos: Position) -> str:
    """Convert (row, col) to algebraic notation."""
    row, col = pos
    return chr(ord("a") + col) + str(8 - row)


def algebraic_to_pos(algebraic: str) -> Optional[Position]:
    """Convert algebraic notation to (row, col)."""
    if len(algebraic) < 2:
        return None
    algebraic = algebraic.lower()
    fc = algebraic[0]
    rc = algebraic[1]
    if fc < "a" or fc > "h" or rc < "1" or rc > "8":
        return None
    return (8 - int(rc), ord(fc) - ord("a"))


def is_in_check(board: Board, color: Color) -> bool:
    """Check if the given color king is in check."""
    king_pos = board.find_king(color)
    if king_pos is None:
        return False
    opponent = color.opponent()
    for (pos, piece) in board.get_all_pieces(opponent):
        captures = _get_pseudo_legal_moves_for_piece(board, pos, piece, check_king=False)
        if any(m.to_pos == king_pos for m in captures):
            return True
    return False


def is_checkmate(board: Board, color: Color) -> bool:
    if not is_in_check(board, color):
        return False
    return not _has_any_legal_move(board, color)


def is_stalemate(board: Board, color: Color) -> bool:
    if is_in_check(board, color):
        return False
    return not _has_any_legal_move(board, color)


def is_insufficient_material(board: Board) -> bool:
    """Check if the position has insufficient material for either side to checkmate.

    Returns True if the position is a draw due to insufficient material.
    Following standard FIDE rules: K vs K, K+B vs K, K+N vs K,
    and K+B vs K+B with bishops on the same color.
    """
    # Collect non-king pieces by type
    white_minor: List[PieceType] = []
    black_minor: List[PieceType] = []

    for (pos, piece) in board.get_all_pieces(Color.WHITE):
        if piece.piece_type != PieceType.KING:
            white_minor.append(piece.piece_type)
    for (pos, piece) in board.get_all_pieces(Color.BLACK):
        if piece.piece_type != PieceType.KING:
            black_minor.append(piece.piece_type)

    # If either side has a pawn, rook, queen, or multiple minor pieces, material is sufficient
    # (2 knights can theoretically checkmate, though rare — treat as sufficient)
    for pt_list in (white_minor, black_minor):
        for pt in pt_list:
            if pt in (PieceType.PAWN, PieceType.ROOK, PieceType.QUEEN):
                return False
        if len(pt_list) >= 2:
            return False  # multiple bishops/knights can checkmate

    # King vs King
    if not white_minor and not black_minor:
        return True

    # King + single bishop/knight vs King (either side)
    if not white_minor and len(black_minor) == 1:
        return black_minor[0] in (PieceType.BISHOP, PieceType.KNIGHT)
    if not black_minor and len(white_minor) == 1:
        return white_minor[0] in (PieceType.BISHOP, PieceType.KNIGHT)

    # King + Bishop vs King + Bishop (same color squares)
    if (len(white_minor) == 1 and len(black_minor) == 1 and
            white_minor[0] == PieceType.BISHOP and black_minor[0] == PieceType.BISHOP):
        white_bishop_pos = None
        black_bishop_pos = None
        for r in range(8):
            for c in range(8):
                p = board.grid[r][c]
                if p is not None and p.piece_type == PieceType.BISHOP:
                    if p.color == Color.WHITE:
                        white_bishop_pos = (r, c)
                    else:
                        black_bishop_pos = (r, c)
        if white_bishop_pos and black_bishop_pos:
            w_sq_color = (white_bishop_pos[0] + white_bishop_pos[1]) % 2
            b_sq_color = (black_bishop_pos[0] + black_bishop_pos[1]) % 2
            if w_sq_color == b_sq_color:
                return True

    return False


def generate_legal_moves(board: Board, color: Color,
                         en_passant_target: Optional[Position] = None) -> List[Move]:
    """Generate all legal moves for the given color."""
    legal_moves = []
    for (pos, piece) in board.get_all_pieces(color):
        pseudo = _get_pseudo_legal_moves_for_piece(
            board, pos, piece, en_passant_target=en_passant_target)
        for move in pseudo:
            if _is_move_legal(board, move, color, en_passant_target):
                legal_moves.append(move)
    return legal_moves


def _has_any_legal_move(board: Board, color: Color,
                        en_passant_target: Optional[Position] = None) -> bool:
    for (pos, piece) in board.get_all_pieces(color):
        for move in _get_pseudo_legal_moves_for_piece(
            board, pos, piece, en_passant_target=en_passant_target):
            if _is_move_legal(board, move, color, en_passant_target):
                return True
    return False


def _get_pseudo_legal_moves_for_piece(board, pos, piece, check_king=True,
                                       en_passant_target=None):
    """Generate pseudo-legal moves (may leave king in check)."""
    pt = piece.piece_type
    if pt == PieceType.PAWN:
        moves = _pawn_moves(board, pos, piece, en_passant_target)
    elif pt == PieceType.KNIGHT:
        moves = _knight_moves(board, pos, piece)
    elif pt == PieceType.BISHOP:
        moves = _sliding_moves(board, pos, piece, DIRECTIONS[PieceType.BISHOP])
    elif pt == PieceType.ROOK:
        moves = _sliding_moves(board, pos, piece, DIRECTIONS[PieceType.ROOK])
    elif pt == PieceType.QUEEN:
        moves = _sliding_moves(board, pos, piece, DIRECTIONS[PieceType.QUEEN])
    elif pt == PieceType.KING:
        moves = _king_moves(board, pos, piece)
        if check_king:
            moves += _castling_moves(board, pos, piece)
    else:
        moves = []
    return moves


def _pawn_moves(board, pos, piece, en_passant_target=None):
    """Generate pawn moves (including promotion and en passant)."""
    row, col = pos
    moves = []
    direction = -1 if piece.color == Color.WHITE else 1
    start_row = 6 if piece.color == Color.WHITE else 1
    promo_row = 0 if piece.color == Color.WHITE else 7

    nr, nc = row + direction, col
    if board._in_bounds(nr, nc) and board.grid[nr][nc] is None:
        _add_pawn_move(moves, pos, (nr, nc), piece, promo_row)
        if row == start_row:
            nr2 = row + 2 * direction
            if board.grid[nr2][nc] is None:
                moves.append(Move(from_pos=pos, to_pos=(nr2, nc), piece=piece))

    for dc in [-1, 1]:
        nr, nc = row + direction, col + dc
        if not board._in_bounds(nr, nc):
            continue
        target = board.grid[nr][nc]
        if target and target.color != piece.color:
            _add_pawn_move(moves, pos, (nr, nc), piece, promo_row, captured=target)

    # En passant capture
    if en_passant_target is not None:
        for dc in [-1, 1]:
            if (row + direction, col + dc) == en_passant_target:
                captured_pawn = board.grid[row][col + dc]
                if captured_pawn and captured_pawn.color != piece.color:
                    moves.append(Move(from_pos=pos, to_pos=en_passant_target,
                                      piece=piece, captured=captured_pawn,
                                      is_en_passant=True))

    return moves


def _add_pawn_move(moves, from_pos, to_pos, piece, promo_row, captured=None):
    """Add a pawn move, handling promotion."""
    if to_pos[0] == promo_row:
        for promo in [PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT]:
            moves.append(Move(from_pos=from_pos, to_pos=to_pos,
                              piece=piece, captured=captured, promotion=promo))
    else:
        moves.append(Move(from_pos=from_pos, to_pos=to_pos, piece=piece, captured=captured))


def _knight_moves(board, pos, piece):
    """Generate knight moves."""
    row, col = pos
    moves = []
    for dr, dc in KNIGHT_OFFSETS:
        nr, nc = row + dr, col + dc
        if not board._in_bounds(nr, nc):
            continue
        target = board.grid[nr][nc]
        if target is None:
            moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece))
        elif target.color != piece.color:
            moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece, captured=target))
    return moves
def _sliding_moves(board, pos, piece, directions):
    """Generate sliding moves for bishops, rooks, and queens."""
    row, col = pos
    moves = []
    for dr, dc in directions:
        nr, nc = row + dr, col + dc
        while board._in_bounds(nr, nc):
            target = board.grid[nr][nc]
            if target is None:
                moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece))
            else:
                if target.color != piece.color:
                    moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece, captured=target))
                break
            nr += dr
            nc += dc
    return moves


def _king_moves(board, pos, piece):
    """Generate king moves."""
    row, col = pos
    moves = []
    for dr, dc in KING_OFFSETS:
        nr, nc = row + dr, col + dc
        if not board._in_bounds(nr, nc):
            continue
        target = board.grid[nr][nc]
        if target is None:
            moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece))
        elif target.color != piece.color:
            moves.append(Move(from_pos=pos, to_pos=(nr, nc), piece=piece, captured=target))
    return moves


def _castling_moves(board, pos, piece):
    """Generate castling moves if available."""
    if piece.has_moved:
        return []
    row, col = pos
    moves = []
    if _can_castle(board, piece.color, row, col, kingside=True):
        moves.append(Move(from_pos=pos, to_pos=(row, col + 2), piece=piece, is_castle=True))
    if _can_castle(board, piece.color, row, col, kingside=False):
        moves.append(Move(from_pos=pos, to_pos=(row, col - 2), piece=piece, is_castle=True))
    return moves


def _is_square_attacked(board, row, col, by_color):
    """Check if any piece of the given color attacks (row, col)."""
    for (pos, piece) in board.get_all_pieces(by_color):
        moves = _get_pseudo_legal_moves_for_piece(board, pos, piece, check_king=False)
        if any(m.to_pos == (row, col) for m in moves):
            return True
    return False


def _can_castle(board, color, king_row, king_col, kingside):
    """Check if castling is available on one side."""
    direction = 1 if kingside else -1
    rook_col = 7 if kingside else 0
    rook = board.grid[king_row][rook_col]
    if rook is None or rook.piece_type != PieceType.ROOK or rook.has_moved:
        return False
    c = king_col + direction
    while c != rook_col:
        if board.grid[king_row][c] is not None:
            return False
        c += direction

    opponent = color.opponent()

    # King must not currently be in check
    if _is_square_attacked(board, king_row, king_col, opponent):
        return False

    # King must not pass through an attacked square
    end_col = king_col + 2 * direction
    c = king_col + direction
    while c != end_col:  # check pass-through squares (not the destination)
        if _is_square_attacked(board, king_row, c, opponent):
            return False
        c += direction

    return True


def _is_move_legal(board, move, color, en_passant_target=None):
    """Check if a move is legal (does not leave own king in check)."""
    temp_board = Board.__new__(Board)
    temp_board.grid = [row[:] for row in board.grid]

    piece = temp_board.grid[move.from_pos[0]][move.from_pos[1]]
    temp_board.grid[move.to_pos[0]][move.to_pos[1]] = piece
    temp_board.grid[move.from_pos[0]][move.from_pos[1]] = None

    if move.is_castle:
        row = move.from_pos[0]
        if move.to_pos[1] > move.from_pos[1]:
            temp_board.grid[row][5] = temp_board.grid[row][7]
            temp_board.grid[row][7] = None
        else:
            temp_board.grid[row][3] = temp_board.grid[row][0]
            temp_board.grid[row][0] = None

    if move.is_en_passant:
        # Remove the pawn that was captured en passant
        # It sits on the same row as the capturing pawn, at the target column
        temp_board.grid[move.from_pos[0]][move.to_pos[1]] = None

    return not is_in_check(temp_board, color)