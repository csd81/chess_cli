"""Zobrist hashing for transposition tables in chess AI.

Provides 64-bit Zobrist hash computation and incremental updates
for fast board state fingerprinting.
"""

import random
from typing import Optional, Tuple
from chess_cli.pieces import Piece, Color, PieceType

# Deterministic RNG so hashes are reproducible across runs
_RNG = random.Random(123456789)

# ---------------------------------------------------------------------------
# Random keys
# ---------------------------------------------------------------------------

# PIECE_KEYS[square][piece_index] — 64 squares × 12 piece types
# piece_index = color_index * 6 + piece_type_index
# color_index: WHITE=0, BLACK=1
# piece_type_index: PAWN=0, KNIGHT=1, BISHOP=2, ROOK=3, QUEEN=4, KING=5
PIECE_KEYS: list[list[int]] = [
    [_RNG.getrandbits(64) for _ in range(12)]
    for _ in range(64)
]

# XOR this in when it is Black's turn to move
SIDE_KEY: int = _RNG.getrandbits(64)

# Castling rights — one key per flag
CASTLE_KEYS: dict[str, int] = {
    "K": _RNG.getrandbits(64),  # White kingside
    "Q": _RNG.getrandbits(64),  # White queenside
    "k": _RNG.getrandbits(64),  # Black kingside
    "q": _RNG.getrandbits(64),  # Black queenside
}

# En-passant file keys — indices 0-7 = files a-h, index 8 = no ep target
EN_PASSANT_KEYS: list[int] = [_RNG.getrandbits(64) for _ in range(9)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Ordering must match the tuple used in piece_index()
_PIECE_TYPE_ORDER = [
    PieceType.PAWN,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.ROOK,
    PieceType.QUEEN,
    PieceType.KING,
]


def piece_index(piece: Piece) -> int:
    """Return 0-11 index for a piece: color*6 + piece_type."""
    ci = 0 if piece.color == Color.WHITE else 1
    pi = _PIECE_TYPE_ORDER.index(piece.piece_type)
    return ci * 6 + pi


def square_index(row: int, col: int) -> int:
    """Encode (row, col) as a single 0-63 square index."""
    return row * 8 + col


# ---------------------------------------------------------------------------
# From-scratch hash
# ---------------------------------------------------------------------------

def compute_zobrist_hash(
    grid: list,
    current_turn: Color,
    en_passant_target: Optional[Tuple[int, int]],
    castling: int,
) -> int:
    """Compute the Zobrist hash for a board state from scratch (O(64))."""
    h = 0

    # Pieces
    for r in range(8):
        for c in range(8):
            p = grid[r][c]
            if p is not None:
                h ^= PIECE_KEYS[square_index(r, c)][piece_index(p)]

    # Side to move
    if current_turn == Color.BLACK:
        h ^= SIDE_KEY

    # Castling rights (bitmask: bit0=K, bit1=Q, bit2=k, bit3=q)
    if castling & 0b0001:
        h ^= CASTLE_KEYS["K"]
    if castling & 0b0010:
        h ^= CASTLE_KEYS["Q"]
    if castling & 0b0100:
        h ^= CASTLE_KEYS["k"]
    if castling & 0b1000:
        h ^= CASTLE_KEYS["q"]

    # En passant file
    ep_idx = en_passant_target[1] if en_passant_target is not None else 8
    h ^= EN_PASSANT_KEYS[ep_idx]

    return h


# ---------------------------------------------------------------------------
# Castle-rights bitmask helpers
# ---------------------------------------------------------------------------

def derive_castling(grid: list) -> int:
    """Derive a castling-rights bitmask from the current board grid.

    Bit layout:
        0b0001 = White kingside  (K)
        0b0010 = White queenside (Q)
        0b0100 = Black kingside  (k)
        0b1000 = Black queenside (q)
    """
    c = 0
    # White
    wk = grid[7][4]
    if wk and wk.piece_type == PieceType.KING and wk.color == Color.WHITE and not wk.has_moved:
        wr1 = grid[7][7]
        if wr1 and wr1.piece_type == PieceType.ROOK and wr1.color == Color.WHITE and not wr1.has_moved:
            c |= 0b0001
        wr2 = grid[7][0]
        if wr2 and wr2.piece_type == PieceType.ROOK and wr2.color == Color.WHITE and not wr2.has_moved:
            c |= 0b0010
    # Black
    bk = grid[0][4]
    if bk and bk.piece_type == PieceType.KING and bk.color == Color.BLACK and not bk.has_moved:
        br1 = grid[0][7]
        if br1 and br1.piece_type == PieceType.ROOK and br1.color == Color.BLACK and not br1.has_moved:
            c |= 0b0100
        br2 = grid[0][0]
        if br2 and br2.piece_type == PieceType.ROOK and br2.color == Color.BLACK and not br2.has_moved:
            c |= 0b1000
    return c


def update_castling(castling: int, piece: Piece, fr: int, fc: int,
                    captured: Optional[Piece], tr: int, tc: int) -> int:
    """Return the new castling-rights bitmask after a move.

    Only needs the move parameters — no board scan required.
    """
    c = castling
    # King moved → lose both rights for that side
    if piece.piece_type == PieceType.KING:
        if piece.color == Color.WHITE:
            c &= ~(0b0001 | 0b0010)
        else:
            c &= ~(0b0100 | 0b1000)
    # Rook moved from starting square → lose that specific right
    elif piece.piece_type == PieceType.ROOK:
        if piece.color == Color.WHITE:
            if fr == 7 and fc == 0:
                c &= ~0b0010  # queenside
            elif fr == 7 and fc == 7:
                c &= ~0b0001  # kingside
        else:
            if fr == 0 and fc == 0:
                c &= ~0b1000  # queenside
            elif fr == 0 and fc == 7:
                c &= ~0b0100  # kingside
    # Rook captured on starting square → lose that specific right
    if captured is not None and captured.piece_type == PieceType.ROOK:
        if captured.color == Color.WHITE:
            if tr == 7 and tc == 0:
                c &= ~0b0010
            elif tr == 7 and tc == 7:
                c &= ~0b0001
        else:
            if tr == 0 and tc == 0:
                c &= ~0b1000
            elif tr == 0 and tc == 7:
                c &= ~0b0100
    return c
