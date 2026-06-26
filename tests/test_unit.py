"""Unit tests."""
import pytest
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board
from chess_cli.moves import (
    Move, pos_to_algebraic, algebraic_to_pos,
    generate_legal_moves, is_in_check, is_checkmate,
    _get_pseudo_legal_moves_for_piece, _pawn_moves,
    _sliding_moves
)
from chess_cli.game import Game


class TestBoard:
    def test_starting_position_32_pieces(self, start_board):
        c = sum(1 for r in range(8) for c2 in range(8) if start_board.grid[r][c2] is not None)
        assert c == 32

    def test_kings_in_place(self, start_board):
        wk = start_board.get_piece(7, 4)
        bk = start_board.get_piece(0, 4)
        assert wk and wk.piece_type == PieceType.KING and wk.color == Color.WHITE
        assert bk and bk.piece_type == PieceType.KING and bk.color == Color.BLACK

    def test_fen_roundtrip(self, start_board):
        fen = start_board.to_fen()
        restored = Board.from_fen(fen)
        for r in range(8):
            for c in range(8):
                a = start_board.grid[r][c]
                b = restored.grid[r][c]
                assert (a is None) == (b is None)
                if a is not None:
                    assert a.color == b.color and a.piece_type == b.piece_type

    def test_fen_string(self, start_board):
        assert start_board.to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

    def test_find_king(self, start_board):
        assert start_board.find_king(Color.WHITE) == (7, 4)
        assert start_board.find_king(Color.BLACK) == (0, 4)

class TestCoordinates:
    def test_algebraic_to_pos_e4(self):
        assert algebraic_to_pos("e4") == (4, 4)

    def test_pos_to_algebraic_e4(self):
        assert pos_to_algebraic((4, 4)) == "e4"

    def test_invalid_returns_none(self):
        assert algebraic_to_pos("z1") is None
        assert algebraic_to_pos("a9") is None
        assert algebraic_to_pos("e") is None
        assert algebraic_to_pos("") is None

    def test_roundtrip(self):
        for row in range(8):
            for col in range(8):
                assert algebraic_to_pos(pos_to_algebraic((row, col))) == (row, col)


class TestMoves:
    def test_knight_center_8(self, empty_board, white_knight):
        empty_board.set_piece(4, 4, white_knight)
        moves = _get_pseudo_legal_moves_for_piece(empty_board, (4, 4), white_knight)
        assert len(moves) == 8

    def test_knight_corner_2(self, empty_board, white_knight):
        empty_board.set_piece(0, 0, white_knight)
        moves = _get_pseudo_legal_moves_for_piece(empty_board, (0, 0), white_knight)
        assert len(moves) == 2

    def test_knight_blocked(self, empty_board, white_knight):
        empty_board.set_piece(4, 4, white_knight)
        own = Piece(Color.WHITE, PieceType.PAWN)
        empty_board.set_piece(2, 3, own)
        empty_board.set_piece(6, 5, own)
        moves = _get_pseudo_legal_moves_for_piece(empty_board, (4, 4), white_knight)
        assert len(moves) == 6

    def test_bishop_13(self, empty_board):
        b = Piece(Color.WHITE, PieceType.BISHOP)
        empty_board.set_piece(4, 4, b)
        assert len(_get_pseudo_legal_moves_for_piece(empty_board, (4, 4), b)) == 13

    def test_rook_14(self, empty_board):
        r = Piece(Color.WHITE, PieceType.ROOK)
        empty_board.set_piece(4, 4, r)
        assert len(_get_pseudo_legal_moves_for_piece(empty_board, (4, 4), r)) == 14

    def test_queen_27(self, empty_board):
        q = Piece(Color.WHITE, PieceType.QUEEN)
        empty_board.set_piece(4, 4, q)
        assert len(_get_pseudo_legal_moves_for_piece(empty_board, (4, 4), q)) == 27

    def test_pawn_two_forward(self, empty_board, white_pawn):
        empty_board.set_piece(6, 4, white_pawn)
        moves = _pawn_moves(empty_board, (6, 4), white_pawn)
        assert len(moves) == 2
        targets = {m.to_pos for m in moves}
        assert (5, 4) in targets
        assert (4, 4) in targets

    def test_pawn_blocked(self, empty_board, white_pawn):
        empty_board.set_piece(4, 4, white_pawn)
        empty_board.set_piece(3, 4, Piece(Color.BLACK, PieceType.PAWN))
        assert len(_pawn_moves(empty_board, (4, 4), white_pawn)) == 0

    def test_pawn_capture(self, empty_board, white_pawn):
        empty_board.set_piece(4, 4, white_pawn)
        bp = Piece(Color.BLACK, PieceType.PAWN)
        empty_board.set_piece(3, 3, bp)
        empty_board.set_piece(3, 5, bp)
        empty_board.set_piece(3, 4, bp)  # block forward, only captures remain
        moves = _pawn_moves(empty_board, (4, 4), white_pawn)
        assert len(moves) == 2  # two diagonal captures, no forward move

    def test_sliding_captures_stops(self, empty_board):
        rook = Piece(Color.WHITE, PieceType.ROOK)
        empty_board.set_piece(4, 4, rook)
        enemy = Piece(Color.BLACK, PieceType.PAWN)
        empty_board.set_piece(4, 6, enemy)
        moves = _sliding_moves(empty_board, (4, 4), rook, [(0, 1)])
        assert len(moves) == 2
        assert moves[1].captured is enemy


class TestGame:
    def test_initial_turn_is_white(self, game):
        assert game.current_turn == Color.WHITE

    def test_turn_switches(self, game):
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        assert game.current_turn == Color.BLACK

    def test_undo_returns_to_start(self, game):
        initial_fen = game.board.to_fen()
        for m in ["e2e4", "e7e5", "g1f3"]:
            game.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        for _ in range(3):
            game.undo_move()
        assert game.board.to_fen() == initial_fen
        assert game.current_turn == Color.WHITE

    def test_undo_empty_false(self, game):
        assert game.undo_move() is False

    def test_pgn_with_moves(self, game):
        for m in ["e2e4", "e7e5"]:
            game.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        pgn = game.export_pgn("A", "B")
        assert "1. e4 e5" in pgn
        assert 'White "A"' in pgn

    def test_check_notation(self):
        g = Game()
        for m in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "c4f7"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        last = g.move_history[-1]
        assert last.gave_check
        assert "+" in g.get_move_notation(last)

    def test_scholars_mate(self):
        g = Game()
        for m in ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over
        assert g.winner == Color.WHITE
        assert is_checkmate(g.board, Color.BLACK)

    def test_fools_mate(self):
        g = Game()
        for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over
        assert g.winner == Color.BLACK
        assert is_checkmate(g.board, Color.WHITE)

    def test_simple_check(self, empty_board):
        empty_board.set_piece(7, 4, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(5, 4, Piece(Color.BLACK, PieceType.QUEEN))
        assert is_in_check(empty_board, Color.WHITE)
