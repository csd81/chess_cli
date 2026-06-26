"""Tests for 50-move rule and threefold repetition draw detection."""

import pytest
from chess_cli.board import Board
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.moves import algebraic_to_pos
from chess_cli.game import Game


class TestHalfmoveClock:
    def test_clock_starts_at_zero(self, game):
        assert game.halfmove_clock == 0

    def test_clock_resets_on_pawn_move(self, game):
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        assert game.halfmove_clock == 0

    def test_clock_resets_on_capture(self, game):
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        game.make_move(algebraic_to_pos("d7"), algebraic_to_pos("d5"))
        game.make_move(algebraic_to_pos("e4"), algebraic_to_pos("d5"))
        assert game.halfmove_clock == 0

    def test_clock_increments(self, game):
        game.make_move(algebraic_to_pos("g1"), algebraic_to_pos("f3"))
        assert game.halfmove_clock == 1

    def test_clock_multiple_increments(self, game):
        for m in ["g1f3", "g8f6", "b1c3", "b8c6"]:
            game.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert game.halfmove_clock == 4

    def test_pawn_move_resets_accumulated_clock(self, game):
        for m in ["g1f3", "g8f6", "b1c3", "b8c6"]:
            game.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert game.halfmove_clock == 4
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        assert game.halfmove_clock == 0

class TestFiftyMoveRule:
    def _make_quiet_knight_game(self):
        b = Board.from_fen("n3k3/8/8/8/8/8/8/N3K3 w - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.WHITE
        return g

    def test_triggered_at_100(self):
        g = self._make_quiet_knight_game()
        g.halfmove_clock = 99
        success = g.make_move(algebraic_to_pos("a1"), algebraic_to_pos("c2"))
        assert success is True
        assert g.game_over is True
        assert g.winner is None
        assert g.draw_reason == "50-move rule"

    def test_not_triggered_at_98(self):
        g = self._make_quiet_knight_game()
        g.halfmove_clock = 98
        success = g.make_move(algebraic_to_pos("a1"), algebraic_to_pos("c2"))
        assert success is True
        assert g.game_over is False

    def test_undo_restores_clock(self):
        g = self._make_quiet_knight_game()
        g.halfmove_clock = 99
        g.make_move(algebraic_to_pos("a1"), algebraic_to_pos("c2"))
        assert g.game_over is True
        result = g.undo_move()
        assert result is True
        assert g.game_over is False
        assert g.halfmove_clock == 99

    def test_pawn_move_resets_and_prevents_draw(self):
        b = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.WHITE
        g.halfmove_clock = 98
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        assert g.game_over is False
        assert g.halfmove_clock == 0


class TestThreefoldRepetition:
    def _knight_shuffle_til_3rd_repeat(self):
        g = Game()
        moves = ["g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8"]
        for m in moves:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        return g

    def test_threefold_triggered_on_third_repeat(self):
        g = self._knight_shuffle_til_3rd_repeat()
        assert g.game_over is True
        assert g.winner is None
        assert g.draw_reason == "threefold repetition"

    def test_threefold_not_triggered_at_two(self):
        g = Game()
        moves = ["g1f3", "g8f6", "f3g1", "f6g8"]
        for m in moves:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over is False

    def test_threefold_undo_restores(self):
        g = Game()
        moves = ["g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8"]
        for m in moves:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over is True
        # Undo the last 4 moves (2 full turns) to get below the 3-repeat threshold
        for _ in range(4):
            g.undo_move()
        assert g.game_over is False
        # All position keys should now have count < 3
        for count in g.position_history.values():
            assert count < 3, f"Position count {count} should be < 3 after undoing 4 moves"

    def test_threefold_six_moves_no_draw(self):
        """Only 6 moves means at most 2 repeats, no draw yet."""
        g = Game()
        moves = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6"]
        for m in moves:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over is False


class TestPositionKey:
    def test_key_includes_turn(self, game):
        key1 = game._get_position_key()
        assert "white" in key1
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        key2 = game._get_position_key()
        assert "black" in key2

    def test_key_includes_castling(self, game):
        key = game._get_position_key()
        assert "KQkq" in key

    def test_key_includes_en_passant(self):
        g = Game()
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        key = g._get_position_key()
        assert "e3" in key


class TestPGNDraws:
    def test_fifty_move_pgn(self):
        b = Board.from_fen("n3k3/8/8/8/8/8/8/N3K3 w - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.WHITE
        g.halfmove_clock = 99
        g.make_move(algebraic_to_pos("a1"), algebraic_to_pos("c2"))
        pgn = g.export_pgn("White", "Black")
        assert '[Result "1/2-1/2"]' in pgn

    def test_threefold_pgn(self):
        g = Game()
        moves = ["g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8",
                 "g1f3", "g8f6", "f3g1", "f6g8"]
        for m in moves:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))
        assert g.game_over is True
        pgn = g.export_pgn("White", "Black")
        assert '[Result "1/2-1/2"]' in pgn


class TestAllDrawTypesCoexist:
    def test_stalemate_still_works(self):
        from chess_cli.moves import is_stalemate
        b = Board.from_fen("8/8/8/8/8/2k5/1r6/K7 w - - 0 1")
        assert is_stalemate(b, Color.WHITE) is True

    def test_insufficient_material_still_works(self, empty_board):
        from chess_cli.moves import is_insufficient_material
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is True

    def test_position_history_tracks_multiple(self, game):
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        game.make_move(algebraic_to_pos("e7"), algebraic_to_pos("e5"))
        assert len(game.position_history) == 2
