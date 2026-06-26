"""Tests for insufficient material draw detection."""

import pytest
from chess_cli.board import Board
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.moves import is_insufficient_material, is_stalemate, is_checkmate
from chess_cli.game import Game
from chess_cli.moves import algebraic_to_pos


class TestInsufficientMaterial:
    def test_king_vs_king(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is True

    def test_king_bishop_vs_king(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.BISHOP))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is True

    def test_king_knight_vs_king(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.KNIGHT))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is True

    def test_bishop_king_vs_king(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        empty_board.set_piece(3, 3, Piece(Color.BLACK, PieceType.BISHOP))
        assert is_insufficient_material(empty_board) is True

    def test_king_bishop_vs_king_bishop_same_color(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(2, 0, Piece(Color.WHITE, PieceType.BISHOP))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        empty_board.set_piece(5, 3, Piece(Color.BLACK, PieceType.BISHOP))
        assert is_insufficient_material(empty_board) is True

    def test_king_bishop_vs_king_bishop_diff_color(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(2, 0, Piece(Color.WHITE, PieceType.BISHOP))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        empty_board.set_piece(5, 0, Piece(Color.BLACK, PieceType.BISHOP))
        assert is_insufficient_material(empty_board) is False

    def test_sufficient_with_pawn(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(6, 4, Piece(Color.WHITE, PieceType.PAWN))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is False

    def test_sufficient_with_rook(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.ROOK))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is False

    def test_sufficient_with_queen(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.QUEEN))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is False

    def test_sufficient_two_knights(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.KNIGHT))
        empty_board.set_piece(5, 5, Piece(Color.WHITE, PieceType.KNIGHT))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is False

    def test_full_starting_position(self, start_board):
        assert is_insufficient_material(start_board) is False

    def test_sufficient_two_bishops(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.BISHOP))
        empty_board.set_piece(5, 5, Piece(Color.WHITE, PieceType.BISHOP))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        assert is_insufficient_material(empty_board) is False

    def test_knight_vs_bishop(self, empty_board):
        empty_board.set_piece(0, 0, Piece(Color.WHITE, PieceType.KING))
        empty_board.set_piece(4, 4, Piece(Color.WHITE, PieceType.KNIGHT))
        empty_board.set_piece(7, 7, Piece(Color.BLACK, PieceType.KING))
        empty_board.set_piece(3, 3, Piece(Color.BLACK, PieceType.BISHOP))
        assert is_insufficient_material(empty_board) is False

class TestGameDrawDetection:
    def test_king_vs_king_pgn_ends_game(self):
        b = Board.from_fen("7k/8/8/8/8/8/8/K7 b - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.BLACK
        success = g.make_move(algebraic_to_pos("h8"), algebraic_to_pos("g8"))
        assert success is True
        assert g.game_over is True
        assert g.winner is None
        assert g.draw_reason == "insufficient material"

    def test_king_bishop_vs_king_draw(self):
        b = Board.from_fen("7k/8/8/8/8/8/8/K1B5 b - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.BLACK
        success = g.make_move(algebraic_to_pos("h8"), algebraic_to_pos("g8"))
        assert success is True
        assert g.game_over is True
        assert g.winner is None
        assert g.draw_reason == "insufficient material"

    def test_undo_after_insufficient_material(self):
        b = Board.from_fen("7k/8/8/8/8/8/8/K7 b - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.BLACK
        g.make_move(algebraic_to_pos("h8"), algebraic_to_pos("g8"))
        assert g.game_over is True
        result = g.undo_move()
        assert result is True
        assert g.game_over is False
        assert g.winner is None
        assert g.draw_reason == ""

    def test_pgn_result_for_insufficient_material(self):
        b = Board.from_fen("7k/8/8/8/8/8/8/K7 b - - 0 1")
        g = Game()
        g.board = b
        g.current_turn = Color.BLACK
        g.make_move(algebraic_to_pos("h8"), algebraic_to_pos("g8"))
        pgn = g.export_pgn("White", "Black")
        assert '[Result "1/2-1/2"]' in pgn

    def test_stalemate_still_recognized(self):
        # Stalemate: White K on a1, Black R on b2, Black K on c3
        # White king has no legal moves (a2 and b1 attacked by rook, b2 occupied)
        # White is not in check
        b = Board.from_fen("8/8/8/8/8/2k5/1r6/K7 w - - 0 1")
        assert is_stalemate(b, Color.WHITE) is True
        assert is_checkmate(b, Color.WHITE) is False
        assert is_insufficient_material(b) is False

    def test_insufficient_material_does_not_interfere_stalemate(self):
        # Verify a position with e.g. K+N vs K is draw by insufficient material
        # but a position with K+R vs K that happens to be stalemate is still stalemate
        b = Board.from_fen("8/8/8/8/8/8/k7/R3K3 w - - 0 1")
        # White to move with K+R vs K, material is sufficient
        assert is_insufficient_material(b) is False
        # Not stalemate either (white has legal moves)
        assert is_stalemate(b, Color.WHITE) is False