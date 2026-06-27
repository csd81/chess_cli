"""AI opponent using minimax with alpha-beta pruning, piece-square tables,
and transposition tables (Zobrist hashing)."""

import random
from typing import Optional, List, Tuple, NamedTuple
from dataclasses import dataclass
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board, Position
from chess_cli.moves import (
    Move, generate_legal_moves, is_in_check,
    is_checkmate, is_stalemate, pos_to_algebraic
)
from chess_cli.zobrist import (
    piece_index, square_index,
    compute_zobrist_hash, derive_castling, update_castling,
    PIECE_KEYS, SIDE_KEY, EN_PASSANT_KEYS,
    CASTLE_KEYS,
)

# Transposition table entry flags
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


@dataclass
class TTEntry:
    """A single entry in the transposition table."""
    score: int
    depth: int
    flag: int


# Global transposition table
TRANSPOSITION_TABLE: dict[int, TTEntry] = {}


def clear_tt() -> None:
    """Clear the transposition table (call between games)."""
    TRANSPOSITION_TABLE.clear()

# Piece values (standard)
PIECE_VALUES = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}

# Piece-square tables (8x8, indexed by [row][col] from white perspective)
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


def simulate_move(board: Board, move: Move,
                  en_passant_target, current_hash: int, castling: int):
    """Apply a move to a deep copy of the board grid.

    Returns:
        (new_grid, new_en_passant_target, new_hash, new_castling_bitmask)
    """
    new_grid = [row[:] for row in board.grid]
    new_ep = None
    h = current_hash

    fr, fc = move.from_pos
    tr, tc = move.to_pos

    piece = new_grid[fr][fc]
    captured = new_grid[tr][tc]

    # Hash: remove piece from source square
    h ^= PIECE_KEYS[square_index(fr, fc)][piece_index(piece)]

    # Handle en passant capture
    if move.is_en_passant:
        ep_captured = new_grid[fr][tc]
        if ep_captured is not None:
            h ^= PIECE_KEYS[square_index(fr, tc)][piece_index(ep_captured)]
            new_grid[fr][tc] = None
            captured = ep_captured

    # Hash: remove captured piece from destination
    if captured is not None and not move.is_en_passant:
        h ^= PIECE_KEYS[square_index(tr, tc)][piece_index(captured)]

    # Execute the move on the grid
    new_grid[tr][tc] = piece
    new_grid[fr][fc] = None

    # Handle promotion
    if move.promotion:
        promoted = Piece(piece.color, move.promotion)
        new_grid[tr][tc] = promoted
        h ^= PIECE_KEYS[square_index(tr, tc)][piece_index(promoted)]
    else:
        h ^= PIECE_KEYS[square_index(tr, tc)][piece_index(piece)]

    # Handle castling rook movement
    if move.is_castle:
        if tc > fc:  # Kingside
            rook = new_grid[fr][7]
            if rook is not None:
                h ^= PIECE_KEYS[square_index(fr, 7)][piece_index(rook)]
                new_grid[fr][5] = rook
                new_grid[fr][7] = None
                h ^= PIECE_KEYS[square_index(fr, 5)][piece_index(rook)]
        else:  # Queenside
            rook = new_grid[fr][0]
            if rook is not None:
                h ^= PIECE_KEYS[square_index(fr, 0)][piece_index(rook)]
                new_grid[fr][3] = rook
                new_grid[fr][0] = None
                h ^= PIECE_KEYS[square_index(fr, 3)][piece_index(rook)]

    # Flip side to move
    h ^= SIDE_KEY

    # Update en passant target
    old_ep_idx = en_passant_target[1] if en_passant_target is not None else 8
    if piece.piece_type == PieceType.PAWN and abs(tr - fr) == 2:
        mid_row = (fr + tr) // 2
        new_ep = (mid_row, fc)
    new_ep_idx = new_ep[1] if new_ep is not None else 8
    h ^= EN_PASSANT_KEYS[old_ep_idx]
    h ^= EN_PASSANT_KEYS[new_ep_idx]

    # Update castling rights
    new_castling = update_castling(castling, piece, fr, fc, captured, tr, tc)
    changed = castling ^ new_castling
    if changed & 0b0001:
        h ^= CASTLE_KEYS["K"]
    if changed & 0b0010:
        h ^= CASTLE_KEYS["Q"]
    if changed & 0b0100:
        h ^= CASTLE_KEYS["k"]
    if changed & 0b1000:
        h ^= CASTLE_KEYS["q"]

    return new_grid, new_ep, h, new_castling


QS_DELTA = 900  # Largest possible material gain in a single capture (queen)
QS_MAX_DEPTH = 8  # Safety limit to prevent runaway recursion


def _quiescence_search(grid, alpha, beta, is_maximizing,
                       ai_color, en_passant_target, current_turn,
                       zobrist_hash, castling, qs_depth=0):
    """Search only capture moves until the position is quiet.

    Eliminates the horizon effect by ensuring tactical sequences
    (captures) are fully resolved before static evaluation.
    Uses MVV-LVA (Most Valuable Victim - Least Valuable Attacker) ordering.
    """
    # Safety depth limit
    if qs_depth >= QS_MAX_DEPTH:
        temp_board = Board.__new__(Board)
        temp_board.grid = grid
        return evaluate(temp_board, ai_color)

    temp_board = Board.__new__(Board)
    temp_board.grid = grid

    # Stand-pat evaluation: score if we stop searching now
    stand_pat = evaluate(temp_board, ai_color)

    # Beta cutoff checks
    if is_maximizing:
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return alpha
        if stand_pat < beta:
            beta = stand_pat

    # Generate only capture moves (and promotions == captures)
    legal = generate_legal_moves(temp_board, current_turn,
                                 en_passant_target=en_passant_target)
    captures = [m for m in legal if m.captured is not None or m.is_en_passant]

    if not captures:
        return stand_pat

    # MVV-LVA ordering: sort captures by victim_value * 10 - attacker_value
    def mvv_lva(m):
        victim = m.captured
        if victim is None:
            return 0
        victim_val = PIECE_VALUES.get(victim.piece_type, 0)
        attacker = m.piece
        attacker_val = PIECE_VALUES.get(attacker.piece_type, 0)
        return victim_val * 10 - attacker_val

    captures.sort(key=mvv_lva, reverse=True)

    if is_maximizing:
        for move in captures:
            # Delta pruning: if stand_pat + max_gain can't beat alpha, skip
            if move.captured:
                gain = PIECE_VALUES.get(move.captured.piece_type, 0)
                if stand_pat + gain + 200 < alpha:  # 200 = margin for positional
                    continue

            ng, nep, nh, ncast = simulate_move(
                temp_board, move, en_passant_target, zobrist_hash, castling)
            nt = current_turn.opponent()
            score = _quiescence_search(ng, alpha, beta, False,
                                      ai_color, nep, nt, nh, ncast,
                                      qs_depth + 1)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha
    else:
        for move in captures:
            # Delta pruning (negated for minimizing side)
            if move.captured:
                gain = PIECE_VALUES.get(move.captured.piece_type, 0)
                if stand_pat - gain - 200 > beta:
                    continue

            ng, nep, nh, ncast = simulate_move(
                temp_board, move, en_passant_target, zobrist_hash, castling)
            nt = current_turn.opponent()
            score = _quiescence_search(ng, alpha, beta, True,
                                      ai_color, nep, nt, nh, ncast,
                                      qs_depth + 1)
            if score <= alpha:
                return alpha
            if score < beta:
                beta = score
        return beta


def _minimax(grid, depth, alpha, beta, is_maximizing,
             ai_color, en_passant_target, current_turn,
             zobrist_hash, castling):
    """Minimax search on a raw grid with alpha-beta and transposition table."""
    temp_board = Board.__new__(Board)
    temp_board.grid = grid

    # Transposition table lookup
    entry = TRANSPOSITION_TABLE.get(zobrist_hash)
    if entry is not None and entry.depth >= depth:
        if entry.flag == EXACT:
            return entry.score
        elif entry.flag == LOWERBOUND:
            alpha = max(alpha, entry.score)
        elif entry.flag == UPPERBOUND:
            beta = min(beta, entry.score)
        if alpha >= beta:
            return entry.score

    original_alpha = alpha

    # Check terminal conditions
    if is_checkmate(temp_board, current_turn):
        return -99999 + (10 - depth)
    if is_stalemate(temp_board, current_turn):
        return 0

    if depth == 0:
        return _quiescence_search(grid, alpha, beta, is_maximizing,
                                  ai_color, en_passant_target, current_turn,
                                  zobrist_hash, castling)

    legal = generate_legal_moves(temp_board, current_turn,
                                 en_passant_target=en_passant_target)
    if not legal:
        if is_in_check(temp_board, current_turn):
            return -99999 + (10 - depth)
        return 0

    if is_maximizing:
        best = -999999
        for move in legal:
            ng, nep, nh, ncast = simulate_move(
                temp_board, move, en_passant_target, zobrist_hash, castling)
            nt = current_turn.opponent()
            score = _minimax(ng, depth - 1, alpha, beta, False,
                            ai_color, nep, nt, nh, ncast)
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
    else:
        best = 999999
        for move in legal:
            ng, nep, nh, ncast = simulate_move(
                temp_board, move, en_passant_target, zobrist_hash, castling)
            nt = current_turn.opponent()
            score = _minimax(ng, depth - 1, alpha, beta, True,
                            ai_color, nep, nt, nh, ncast)
            if score < best:
                best = score
            if score < beta:
                beta = score
            if beta <= alpha:
                break

    # Store in transposition table
    flag = EXACT
    if best <= original_alpha:
        flag = UPPERBOUND
    elif best >= beta:
        flag = LOWERBOUND
    TRANSPOSITION_TABLE[zobrist_hash] = TTEntry(best, depth, flag)

    return best


def get_best_move(board: Board, current_turn: Color,
                  en_passant_target=None,
                  depth: int = 3):
    """Find the best move using minimax + alpha-beta + transposition table."""
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

    # Compute initial castling rights and Zobrist hash
    castling = derive_castling(board.grid)
    zobrist_hash = compute_zobrist_hash(
        board.grid, current_turn, en_passant_target, castling)

    # Depth 1: pick the move with best immediate evaluation
    if depth <= 1:
        best_move = None
        best_score = -999999
        for move in legal:
            ng, _, _, _ = simulate_move(
                board, move, en_passant_target, zobrist_hash, castling)
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

    # Order moves: captures first (on higher-value pieces first)
    def move_key(m):
        if m.captured:
            return -PIECE_VALUES.get(m.captured.piece_type, 0)
        return 0
    legal.sort(key=move_key)

    for move in legal:
        ng, nep, nh, ncast = simulate_move(
            board, move, en_passant_target, zobrist_hash, castling)
        nt = current_turn.opponent()
        score = _minimax(ng, depth - 1, -999999, 999999, False,
                        ai_color, nep, nt, nh, ncast)
        if score > best_score:
            best_score = score
            best_move = move

    return best_move
