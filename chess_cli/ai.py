"""AI opponent using minimax with alpha-beta pruning and piece-square tables."""

import random
from typing import Optional, List, Tuple
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board, Position
from chess_cli.moves import (
    Move, generate_legal_moves, is_in_check,
    is_checkmate, is_stalemate, pos_to_algebraic
)

# ---------------------------------------------------------------------------
# Piece values (standard)
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}

# ---------------------------------------------------------------------------
# Piece-square tables (8x8, indexed by [row][col] from white perspective)
# Rows 0-7 = rank 8 to rank 1. For black, mirror row index (7-row).
# ---------------------------------------------------------------------------

PAWN_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5,  5, 10, 25, 25, 10,  5,  5],
    [0,  0,  0, 20, 20,  0,  0,  0],
    [5, -5,-10,  0,  0,-10, -5,  5],
    [5, 10, 10,-20,-20, 10, 10,  5],
    [0,  0,  0,  0,  0,  0,  0,  0],
]

KNIGHT_TABLE = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50],
]

BISHOP_TABLE = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20],
]

ROOK_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [0,  0,  0,  5,  5,  0,  0,  0],
]

QUEEN_TABLE = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [-5,   0,  5,  5,  5,  5,  0, -5],
    [0,   0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20],
]

KING_TABLE = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [20, 20,  0,  0,  0,  0, 20, 20],
    [20, 30, 10,  0,  0, 10, 30, 20],
]

PIECE_TABLES = {
    PieceType.PAWN: PAWN_TABLE,
    PieceType.KNIGHT: KNIGHT_TABLE,
    PieceType.BISHOP: BISHOP_TABLE,
    PieceType.ROOK: ROOK_TABLE,
    PieceType.QUEEN: QUEEN_TABLE,
    PieceType.KING: KING_TABLE,
}

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(board: Board, color: Color) -> int:
    """Evaluate the board from the perspective of the given color."""
    score = 0
    opponent = color.opponent()

    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p is None:
                continue

            value = PIECE_VALUES.get(p.piece_type, 0)
            table = PIECE_TABLES.get(p.piece_type)
            if table is not None:
                table_row = r if p.color == Color.WHITE else 7 - r
                value += table[table_row][c]

            if p.color == color:
                score += value
            else:
                score -= value

    return score


# ---------------------------------------------------------------------------
# Move simulation (on a copied grid, no mutation of original)
# ---------------------------------------------------------------------------

def _simulate_move(board: Board, move: Move,
                    en_passant_target=None):
    """Apply a move to a deep copy of the board grid.
    Returns (new_grid, new_en_passant_target).
    """
    new_grid = [row[:] for row in board.grid]
    new_ep = None

    fr, fc = move.from_pos
    tr, tc = move.to_pos

    piece = new_grid[fr][fc]
    new_grid[tr][tc] = piece
    new_grid[fr][fc] = None

    # En passant capture: remove the captured pawn
    if move.is_en_passant:
        new_grid[fr][tc] = None

    # Castling: move rook
    if move.is_castle:
        if tc > fc:  # kingside
            new_grid[fr][5] = new_grid[fr][7]
            new_grid[fr][7] = None
        else:  # queenside
            new_grid[fr][3] = new_grid[fr][0]
            new_grid[fr][0] = None

    # Promotion: replace piece
    if move.promotion:
        new_grid[tr][tc] = Piece(piece.color, move.promotion)

    # Set new en passant target for the next search node
    if piece.piece_type == PieceType.PAWN and abs(tr - fr) == 2:
        new_ep = ((fr + tr) // 2, fc)

    return new_grid, new_ep

# ---------------------------------------------------------------------------
# Minimax with alpha-beta pruning
# ---------------------------------------------------------------------------

def _minimax(grid, depth, alpha, beta, is_maximizing,
             ai_color, en_passant_target, current_turn):
    """Minimax search on a raw grid (no Board object overhead)."""
    temp_board = Board.__new__(Board)
    temp_board.grid = grid

    opponent = current_turn.opponent()

    # Check terminal conditions
    if is_checkmate(temp_board, current_turn):
        return -99999 + (10 - depth)  # prefer faster checkmates
    if is_stalemate(temp_board, current_turn):
        return 0

    if depth == 0:
        return evaluate(temp_board, ai_color)

    legal = generate_legal_moves(temp_board, current_turn,
                                 en_passant_target=en_passant_target)
    if not legal:
        if is_in_check(temp_board, current_turn):
            return -99999 + (10 - depth)
        return 0

    if is_maximizing:
        best = -999999
        for move in legal:
            ng, nep = _simulate_move(temp_board, move, en_passant_target)
            nt = current_turn.opponent()
            score = _minimax(ng, depth - 1, alpha, beta, False,
                            ai_color, nep, nt)
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best
    else:
        best = 999999
        for move in legal:
            ng, nep = _simulate_move(temp_board, move, en_passant_target)
            nt = current_turn.opponent()
            score = _minimax(ng, depth - 1, alpha, beta, True,
                            ai_color, nep, nt)
            if score < best:
                best = score
            if score < beta:
                beta = score
            if beta <= alpha:
                break
        return best

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_best_move(board: Board, current_turn: Color,
                  en_passant_target=None,
                  depth: int = 3):
    """Find the best move for the given turn using minimax + alpha-beta."""
    legal = generate_legal_moves(board, current_turn,
                                 en_passant_target=en_passant_target)
    if not legal:
        return None

    # Check opening book first (instant response)
    from chess_cli.opening_book import get_book_move
    book_move = get_book_move(board, current_turn, en_passant_target, legal)
    if book_move is not None:
        return book_move

    # If only one legal move, return it immediately
    if len(legal) == 1:
        return legal[0]

    # Depth 1: pick the move with best immediate evaluation
    if depth <= 1:
        best_move = None
        best_score = -999999
        for move in legal:
            ng, _ = _simulate_move(board, move, en_passant_target)
            tb = Board.__new__(Board)
            tb.grid = ng
            score = evaluate(tb, current_turn)
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    best_move = None
    best_score = -999999
    ai_color = current_turn

    # Order moves: captures first (captures on higher-value pieces first)
    def move_key(m):
        if m.captured:
            return -PIECE_VALUES.get(m.captured.piece_type, 0)
        return 0
    legal.sort(key=move_key)

    for move in legal:
        ng, nep = _simulate_move(board, move, en_passant_target)
        nt = current_turn.opponent()
        score = _minimax(ng, depth - 1, -999999, 999999, False,
                        ai_color, nep, nt)
        if score > best_score:
            best_score = score
            best_move = move

    return best_move