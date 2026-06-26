"""Opening book for AI - provides standard responses for early moves."""

import random
from typing import Optional
from chess_cli.pieces import Color, Piece, PieceType
from chess_cli.board import Board, Position
from chess_cli.moves import Move


def _get_castling_rights(board: Board) -> str:
    """Derive castling rights from piece positions on the board."""
    rights = ""
    wk = board.get_piece(7, 4)
    wh_r = board.get_piece(7, 7)
    wq_r = board.get_piece(7, 0)
    if wk and wk.piece_type == PieceType.KING and wk.color == Color.WHITE:
        if wh_r and wh_r.piece_type == PieceType.ROOK and wh_r.color == Color.WHITE:
            rights += "K"
        if wq_r and wq_r.piece_type == PieceType.ROOK and wq_r.color == Color.WHITE:
            rights += "Q"
    bk = board.get_piece(0, 4)
    bh_r = board.get_piece(0, 7)
    bq_r = board.get_piece(0, 0)
    if bk and bk.piece_type == PieceType.KING and bk.color == Color.BLACK:
        if bh_r and bh_r.piece_type == PieceType.ROOK and bh_r.color == Color.BLACK:
            rights += "k"
        if bq_r and bq_r.piece_type == PieceType.ROOK and bq_r.color == Color.BLACK:
            rights += "q"
    return rights if rights else "-"

def _fen_key(board, current_turn, en_passant_target):
    fen = board.to_fen()
    active = current_turn.value[0]
    castling = _get_castling_rights(board)
    if en_passant_target:
        from chess_cli.moves import pos_to_algebraic
        ep = pos_to_algebraic(en_passant_target)
    else:
        ep = "-"
    return f"{fen} {active} {castling} {ep}"


# ---------------------------------------------------------------------------
# Opening book dictionary
# Key format: "<piece_placement> <active> <castling> <en_passant>"
# Castling rights derived from piece positions (king+rook on home squares).
# ---------------------------------------------------------------------------

OPENING_BOOK: dict[str, list[str]] = {
    # Starting position
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": [
        "e2e4", "d2d4", "c2c4", "g1f3",
    ],

    # 1.e4 responses
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3": [
        "e7e5", "c7c5", "e7e6", "d7d6", "g7g6", "b8c6", "g8f6", "a7a6", "b7b6",
    ],

    # 1.e4 e5 2.Nf3
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": [
        "b8c6", "d7d6", "g8f6", "f7f5",
    ],

    # 1.e4 e5 2.Nf3 Nc6 3.Bb5 (Ruy Lopez)
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": [
        "a7a6", "g8f6", "d7d6", "f8c5", "g8e7",
    ],

    # 1.e4 c5 2.Nf3 d6
    "rnbqkbnr/pp2pppp/3p4/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "d2d4",
    ],

    # 1.e4 c5 2.Nf3 Nc6
    "r1bqkbnr/pp1ppppp/2n5/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "d2d4",
    ],

    # 1.e4 c5 2.Nf3 e6
    "rnbqkbnr/pp1p1ppp/4p3/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "d2d4",
    ],

    # 1.e4 c5 2.Nf3 g6
    "rnbqkbnr/pp1ppp1p/6p1/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "d2d4",
    ],

    # 1.e4 c5 2.Nf3 a6
    "rnbqkbnr/1p1ppppp/p7/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "d2d4",
    ],

    # 1.e4 e6 (French) 2.d4
    "rnbqkbnr/pppp1ppp/4p3/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": [
        "d7d5",
    ],

    # 1.e4 d6 (Pirc) 2.d4
    "rnbqkbnr/ppp1pppp/3p4/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": [
        "g8f6", "g7g6",
    ],

    # 1.e4 g6 (Modern) 2.d4
    "rnbqkbnr/pppppp1p/6p1/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": [
        "f8g7",
    ],

    # 1.e4 Nc6 (Nimzowitsch) 2.d4
    "r1bqkbnr/pppppppp/2n5/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": [
        "d7d5",
    ],

    # 1.d4 responses
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3": [
        "d7d5", "g8f6", "e7e6", "f7f5", "g7g6", "d7d6", "c7c5",
    ],

    # 1.d4 d5 2.c4 (Queen's Gambit)
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3": [
        "e7e6", "c7c6", "d5c4", "b8c6", "e7e5",
    ],

    # 1.d4 Nf6 2.c4 (Indian)
    "rnbqkb1r/pppppppp/5n2/8/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3": [
        "e7e6", "g7g6", "c7c5", "c7c6", "b7b6",
    ],

    # 1.c4 responses
    "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq c3": [
        "e7e5", "c7c5", "g8f6", "e7e6",
    ],

    # 1.Nf3 responses
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq -": [
        "d7d5", "g8f6", "c7c5", "e7e6", "g7g6",
    ],

    # 1.c4 e5
    "rnbqkbnr/pppp1ppp/8/4p3/2P5/8/PP1PPPPP/RNBQKBNR w KQkq e6": [
        "g1f3", "b1c3", "e2e3",
    ],

    # 1.c4 c5
    "rnbqkbnr/pp1ppppp/8/2p5/2P5/8/PP1PPPPP/RNBQKBNR w KQkq c6": [
        "g1f3", "b1c3", "e2e3",
    ],

    # 1.d4 d5 (Queen's Gambit responses)
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6": [
        "c2c4", "b1c3", "g1f3", "c1f4",
    ],

    # 1.d4 Nf6 2.c4 e6 (Nimzo-Indian)
    "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": [
        "b1c3", "g1f3",
    ],

    # 1.d4 Nf6 2.c4 g6 (King's Indian)
    "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": [
        "b1c3", "g1f3", "e2e4",
    ],

    # 1.d4 Nf6 2.c4 c5 (Benoni)
    "rnbqkb1r/pp1ppppp/5n2/2p5/2PP4/8/PP2PPPP/RNBQKBNR w KQkq c6": [
        "d4d5", "g1f3",
    ],

    # 1.e4 e5 2.Nf3 Nc6
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": [
        "f1b5", "d2d4", "f1c4", "b1c3",
    ],

    # 1.e4 c5 2.Nf3 d6 3.d4 (Open Sicilian)
    "rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq -": [
        "c5d4",
    ],

    # 1.e4 e6 2.d4 d5 (French main line)
    "rnbqkbnr/ppp2ppp/4p3/3p4/3PP3/8/PPP2PPP/RNBQKBNR w KQkq d6": [
        "b1c3", "e4e5", "c1g5",
    ],

    # 1.d4 d5 2.c4 e6 (QGD)
    "rnbqkbnr/ppp2ppp/4p3/3p4/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": [
        "b1c3", "g1f3", "c1g5",
    ],

    # 1.d4 d5 2.c4 c6 (Slav)
    "rnbqkbnr/pp2pppp/2p5/3p4/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": [
        "b1c3", "g1f3", "c4d5",
    ],

    # 1.d4 d5 2.c4 dxc4 (QGA)
    "rnbqkbnr/ppp1pppp/8/8/2pP4/8/PP2PPPP/RNBQKBNR w KQkq -": [
        "e2e3", "g1f3", "e2e4",
    ],
}


def get_book_move(board: Board, current_turn: Color,
                   en_passant_target: Optional[Position],
                   legal_moves: list[Move]) -> Optional[Move]:
    """Return a random book move if the position is in the opening book.

    Looks up the current position in OPENING_BOOK by building a normalized
    4-field FEN key. If found, filters legal moves by matching UCI strings
    and returns a random candidate. Returns None if no match.
    """
    key = _fen_key(board, current_turn, en_passant_target)
    if key not in OPENING_BOOK:
        return None
    book_ucis = OPENING_BOOK[key]
    candidates = [m for m in legal_moves if m.uci() in book_ucis]
    if not candidates:
        return None
    return random.choice(candidates)