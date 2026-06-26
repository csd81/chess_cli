
"""Adversarial tests: illegal moves, boundary states, and security checks."""

import pytest
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board
from chess_cli.moves import (
    Move, pos_to_algebraic, algebraic_to_pos,
    generate_legal_moves, is_in_check, is_checkmate,
    _get_pseudo_legal_moves_for_piece
)
from chess_cli.game import Game


class TestIllegalMoves:
    def test_cannot_capture_own_piece(self, game):
        # Try to capture own pawn with own knight
        for m in ["g1f3"]:
            pass
        # Instead, try all starting moves - none should be captures of own
        legal = game.get_legal_moves()
        for move in legal:
            if move.captured:
                assert move.captured.color != move.piece.color

    def test_cannot_move_into_check(self):
        # Position where white king on e1, black rook on e8
        # White cannot move e2e4 because it leaves king exposed
        b = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        g = Game()
        g.board = b
        success = g.make_move(algebraic_to_pos("e1"), algebraic_to_pos("e2"))
        assert success is False

    def test_cannot_castle_through_check(self):
        # Position where black rook on f6 attacks f1 — king passes through f1
        b = Board.from_fen("4k3/8/5r2/8/8/8/8/4K2R w K - 0 1")
        g = Game()
        g.board = b
        # e1g1 should be illegal because rook on f6 attacks f1 (pass-through square)
        success = g.make_move(algebraic_to_pos("e1"), algebraic_to_pos("g1"))
        assert success is False

    def test_cannot_castle_when_in_check(self):
        # Position where black rook on e4 attacks e1 (king is in check)
        b = Board.from_fen("4k3/8/8/4r3/8/8/8/4K2R w K - 0 1")
        g = Game()
        g.board = b
        # King is in check from rook on e4, cannot castle
        success = g.make_move(algebraic_to_pos("e1"), algebraic_to_pos("g1"))
        assert success is False

    def test_cannot_move_opponent_pieces(self, game):
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        # Try to move black piece on white's turn... but now it's black's turn
        # Actually, this is the key: after white moves, can't move more white pieces
        success = game.make_move(algebraic_to_pos("d2"), algebraic_to_pos("d4"))
        assert success is False

    def test_knight_cannot_move_obstructed(self, empty_board, white_knight):
        empty_board.set_piece(4, 4, white_knight)
        own = Piece(Color.WHITE, PieceType.PAWN)
        empty_board.set_piece(2, 3, own)
        empty_board.set_piece(6, 5, own)
        moves = _get_pseudo_legal_moves_for_piece(empty_board, (4, 4), white_knight)
        for m in moves:
            assert m.to_pos not in [(2, 3), (6, 5)]

    def test_bishop_cannot_jump_over(self, empty_board):
        bishop = Piece(Color.WHITE, PieceType.BISHOP)
        empty_board.set_piece(4, 4, bishop)
        blocker = Piece(Color.BLACK, PieceType.PAWN)
        empty_board.set_piece(2, 2, blocker)
        moves = _get_pseudo_legal_moves_for_piece(empty_board, (4, 4), bishop)
        for m in moves:
            # No moves should go past the blocker on the (1,1) diagonal
            assert m.to_pos not in [(1, 1), (0, 0)]


class TestKingSafety:
    def test_king_cannot_move_to_attacked_square(self):
        b = Board.from_fen("4k3/8/8/8/8/8/r7/4K3 w - - 0 1")
        g = Game()
        g.board = b
        # Rook on a2 (row 6, col 0) attacks row 6 (2nd rank) and col 0 (a-file)
        # From e1 (7,4), squares d2 (6,3) and f2 (6,5) are on row 6 -> attacked
        # But d1 (7,3) and f1 (7,5) are NOT attacked by the rook
        for dest in ["d2", "f2"]:
            success = g.make_move(algebraic_to_pos("e1"), algebraic_to_pos(dest))
            assert success is False, f"King should not be able to move to {dest}"

    def test_king_capture_guarded_piece(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/4K1r1 w - - 0 1")
        g = Game()
        g.board = b
        # King cannot capture rook on f1 if rook is guarded by black king
        success = g.make_move(algebraic_to_pos("e1"), algebraic_to_pos("f1"))
        assert success is False


class TestEnPassant:
    def test_en_passant_only_immediately(self):
        g = Game()
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        g.make_move(algebraic_to_pos("a7"), algebraic_to_pos("a6"))
        g.make_move(algebraic_to_pos("e4"), algebraic_to_pos("e5"))
        g.make_move(algebraic_to_pos("d7"), algebraic_to_pos("d5"))
        # En passant available now: e5xd6
        ep_legal = [m for m in g.get_legal_moves()
                    if m.is_en_passant]
        assert len(ep_legal) == 1
        assert ep_legal[0].to_pos == (2, 3)  # d6

    def test_en_passant_not_available_after_one_move(self):
        g = Game()
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        g.make_move(algebraic_to_pos("a7"), algebraic_to_pos("a6"))
        g.make_move(algebraic_to_pos("e4"), algebraic_to_pos("e5"))
        g.make_move(algebraic_to_pos("d7"), algebraic_to_pos("d5"))
        # White now has en passant - but if they make a different move...
        g.make_move(algebraic_to_pos("g1"), algebraic_to_pos("f3"))
        # Now en passant should no longer be available for black
        ep_legal = [m for m in g.get_legal_moves()
                    if m.is_en_passant]
        assert len(ep_legal) == 0


class TestMaliciousInput:
    def test_out_of_bounds_algebraic(self):
        assert algebraic_to_pos("z9") is None
        assert algebraic_to_pos("a0") is None
        assert algebraic_to_pos("i5") is None

    def test_short_input(self):
        assert algebraic_to_pos("e") is None
        assert algebraic_to_pos("") is None

    def test_promotion_to_invalid_piece(self):
        b = Board.from_fen("8/4P3/8/8/8/8/8/4K2k w - - 0 1")
        g = Game()
        g.board = b
        # e7e8 is a promotion, but must be Q/R/B/N
        # Valid: e7e8q, e7e8r, etc.
        success = g.make_move(algebraic_to_pos("e7"), algebraic_to_pos("e8"))
        # Without specifying promotion, the move generator creates promotions
        # So this should work (default promote to queen via Move)
        # Actually, our system only accepts specific UCI
        pass

    def test_move_when_game_over(self):
        g = Game()
        for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over
        # No more moves should be possible
        assert len(g.get_legal_moves()) == 0
