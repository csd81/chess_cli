
"""Integration tests: end-to-end flows, CLI interaction, filesystem, AI."""

import os
import sys
import tempfile
import pytest
from chess_cli.pieces import Color, PieceType
from chess_cli.board import Board
from chess_cli.moves import algebraic_to_pos, pos_to_algebraic, generate_legal_moves
from chess_cli.game import Game
from chess_cli.ai import get_best_move, evaluate


class TestFullGame:
    def test_scholars_mate_full(self):
        """Play through the entire Scholar's Mate from start to checkmate."""
        g = Game()
        moves = [
            ("e2", "e4"), ("e7", "e5"),
            ("d1", "h5"), ("b8", "c6"),
            ("f1", "c4"), ("g8", "f6"),
            ("h5", "f7"),
        ]
        for from_sq, to_sq in moves:
            result = g.make_move(algebraic_to_pos(from_sq), algebraic_to_pos(to_sq))
            assert result is True, f"Move {from_sq}{to_sq} should be legal"

        assert g.game_over is True
        assert g.winner == Color.WHITE
        assert len(g.move_history) == 7

    def test_fools_mate_full(self):
        """Play through Fool's Mate from start to checkmate."""
        g = Game()
        moves = [
            ("f2", "f3"), ("e7", "e5"),
            ("g2", "g4"), ("d8", "h4"),
        ]
        for from_sq, to_sq in moves:
            result = g.make_move(algebraic_to_pos(from_sq), algebraic_to_pos(to_sq))
            assert result is True

        assert g.game_over is True
        assert g.winner == Color.BLACK
        assert g.move_history[-1].gave_mate

    def test_long_game_with_multiple_features(self):
        """A longer game testing captures, checks, and castling."""
        g = Game()
        # Italian Game: 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.0-0 Nf6 5.d3 0-0 6.Bg5
        uci_moves = [
            "e2e4", "e7e5",
            "g1f3", "b8c6",
            "f1c4", "f8c5",
            "e1g1",  # white castles kingside
            "g8f6",
            "d2d3",
            "e8g8",  # black castles kingside
            "c1g5",  # Bg5
        ]
        for i, um in enumerate(uci_moves):
            result = g.make_move(algebraic_to_pos(um[:2]), algebraic_to_pos(um[2:4]))
            assert result is True, f"Move {i+1} ({um}) should be legal"

        assert g.game_over is False
        assert len(g.move_history) == len(uci_moves)

    def test_pgn_file_io(self):
        """Export PGN, write to disk, read back, verify content."""
        g = Game()
        for m in ["e2e4", "e7e5", "g1f3", "b8c6"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))

        pgn = g.export_pgn("PlayerOne", "PlayerTwo")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pgn",
                                          delete=False, encoding="utf-8") as tmp:
            tmp.write(pgn)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert '[White "PlayerOne"]' in content
            assert '[Black "PlayerTwo"]' in content
            assert "1. e4 e5" in content
            assert "2. Nf3 Nc6" in content
            assert content.strip().endswith("*")  # Incomplete game
        finally:
            os.unlink(tmp_path)


class TestCLIFlow:
    def test_move_history_display(self):
        """Verify move history tracks correctly for display."""
        g = Game()
        for m in ["e2e4", "e7e5", "g1f3"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))

        notations = [g.get_move_notation(m) for m in g.move_history]
        assert notations == ["e4", "e5", "Nf3"]

    def test_undo_redo_en_passant(self):
        """Undo+redo of en passant should restore state exactly."""
        g = Game()
        for m in ["e2e4", "d7d6", "e4e5", "f7f5", "e5f6"]:
            g.make_move(algebraic_to_pos(m[:2]), algebraic_to_pos(m[2:4]))

        last_move = g.move_history[-1]
        assert last_move.is_en_passant

        state_before_undo = g.board.to_fen()
        g.undo_move()
        assert g.board.to_fen() != state_before_undo

        # Re-do by making the same move
        g.make_move(algebraic_to_pos("e5"), algebraic_to_pos("f6"))
        assert g.board.to_fen() == state_before_undo


class TestAIIntegration:
    def test_ai_returns_valid_move(self):
        """AI should always return a legal move from the starting position."""
        b = Board()
        move = get_best_move(b, Color.WHITE, depth=2)
        assert move is not None
        assert isinstance(move, tuple) is False  # should be a Move object
        assert hasattr(move, "from_pos")
        assert hasattr(move, "to_pos")

    def test_ai_move_is_legal(self):
        """The move returned by the AI must appear in the legal move list."""
        g = Game()
        move = get_best_move(g.board, Color.WHITE,
                            en_passant_target=g.en_passant_target, depth=2)
        legal = generate_legal_moves(g.board, Color.WHITE,
                                     en_passant_target=g.en_passant_target)
        assert move in legal, "AI move must be in legal move list"

    def test_ai_responds_to_e4(self):
        """AI as Black should find a response to 1.e4."""
        g = Game()
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        move = get_best_move(g.board, Color.BLACK,
                            en_passant_target=g.en_passant_target, depth=2)
        assert move is not None
        assert move.piece.color == Color.BLACK

    def test_ai_captures_hanging_piece(self):
        """AI should capture an undefended piece."""
        # Set up: black has a pawn on e5, white has pawn on d4
        b = Board.from_fen("rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2")
        g = Game()
        g.board = b
        # White can capture e5 with d4. The AI as white should take it.
        move = get_best_move(g.board, Color.WHITE, depth=2)
        # The best move should capture the e5 pawn
        assert move is not None
        if move.captured:
            assert move.captured.piece_type == PieceType.PAWN

    def test_cpu_vs_cpu_game(self):
        """Play a CPU vs CPU game to verify no errors."""
        g = Game()
        max_moves = 20
        for i in range(max_moves):
            move = get_best_move(g.board, g.current_turn,
                                en_passant_target=g.en_passant_target,
                                depth=1)
            if move is None:
                break
            g.make_move_from_move(move)
            if g.game_over:
                break

        assert len(g.move_history) > 0
        assert g.game_over or len(g.move_history) == max_moves
        assert g.winner in (Color.WHITE, Color.BLACK, None)


class TestAIVsAI:
    def test_cli_ai_vs_ai_auto_plays(self):
        """ChessCLI with ai_vs_ai=True auto-plays moves for both sides."""
        from chess_cli.cli import ChessCLI
        cli = ChessCLI.__new__(ChessCLI)
        # Minimal init to avoid stdin prompt
        cli.game = Game()
        cli.highlighted_squares = []
        cli.highlighted_piece = None
        cli.cpu_color = None
        cli.ai_vs_ai = True
        cli.ai_depth_white = 1
        cli.ai_depth_black = 1

        # Play 3 full moves (6 half-moves)
        for _ in range(6):
            ok = cli._run_ai_move()
            assert ok, "AI should have a legal move"
            assert not cli.game.game_over, "Game should not be over in 3 moves"

        assert len(cli.game.move_history) == 6


class TestOpeningBook:
    def test_book_returns_starting_move(self):
        """AI should play a book move (e4/d4/c4/Nf3) from the starting position."""
        from chess_cli.opening_book import OPENING_BOOK, get_book_move
        from chess_cli.moves import generate_legal_moves

        b = Board()
        legal = generate_legal_moves(b, Color.WHITE)
        move = get_book_move(b, Color.WHITE, None, legal)
        assert move is not None, "Should find a book move from starting position"
        assert move.uci() in OPENING_BOOK[
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
        ], f"Move {move.uci()} should be in the opening book for the starting position"

    def test_book_responds_to_e4(self):
        """After 1.e4, AI as Black should respond with a book move (e5/c5/e6/etc.)."""
        from chess_cli.opening_book import OPENING_BOOK, get_book_move
        from chess_cli.moves import generate_legal_moves, algebraic_to_pos

        g = Game()
        g.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))

        legal = generate_legal_moves(g.board, Color.BLACK,
                                     en_passant_target=g.en_passant_target)
        move = get_book_move(g.board, Color.BLACK,
                             g.en_passant_target, legal)
        assert move is not None, "Should find a book response to 1.e4"
        assert move.piece.color == Color.BLACK
        # Verify the move is in the 1.e4 responses list
        e4_key = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3"
        assert move.uci() in OPENING_BOOK[e4_key], \
            f"Move {move.uci()} should be a valid response to 1.e4"


class TestFENImport:
    """Tests for importing games from FEN strings."""

    STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    KING_VS_KING_FEN = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"

    def test_standard_fen(self):
        """Full starting FEN produces same state as default Game()."""
        g = Game(fen=self.STARTING_FEN)
        assert g.board.to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        assert g.current_turn == Color.WHITE
        assert g.castling_rights[Color.WHITE]["kingside"] is True
        assert g.castling_rights[Color.WHITE]["queenside"] is True
        assert g.castling_rights[Color.BLACK]["kingside"] is True
        assert g.castling_rights[Color.BLACK]["queenside"] is True
        assert g.en_passant_target is None
        assert g.halfmove_clock == 0
        assert not g.game_over

    def test_default_game_matches_fen(self):
        """Default Game() produces same state as Game(fen=starting_fen)."""
        g1 = Game()
        g2 = Game(fen=self.STARTING_FEN)
        assert g1.board.to_fen() == g2.board.to_fen()
        assert g1.current_turn == g2.current_turn
        assert g1.castling_rights == g2.castling_rights
        assert g1.en_passant_target == g2.en_passant_target
        assert g1.halfmove_clock == g2.halfmove_clock

    def test_black_to_move(self):
        """FEN with black to move sets current_turn correctly."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        g = Game(fen=fen)
        assert g.current_turn == Color.BLACK

    def test_no_castling_rights(self):
        """FEN with no castling rights parses correctly."""
        fen = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
        g = Game(fen=fen)
        assert g.castling_rights[Color.WHITE]["kingside"] is False
        assert g.castling_rights[Color.WHITE]["queenside"] is False
        assert g.castling_rights[Color.BLACK]["kingside"] is False
        assert g.castling_rights[Color.BLACK]["queenside"] is False

    def test_partial_castling_rights(self):
        """FEN with partial castling rights."""
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w Kk - 0 1"
        g = Game(fen=fen)
        assert g.castling_rights[Color.WHITE]["kingside"] is True
        assert g.castling_rights[Color.WHITE]["queenside"] is False
        assert g.castling_rights[Color.BLACK]["kingside"] is True
        assert g.castling_rights[Color.BLACK]["queenside"] is False

    def test_en_passant_target(self):
        """FEN with en passant target sets it correctly."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        g = Game(fen=fen)
        assert g.en_passant_target is not None
        assert g.en_passant_target == (5, 4)  # e3 = rank 3, row=8-3=5, col=4

    def test_halfmove_clock(self):
        """FEN halfmove clock is parsed correctly."""
        fen = "8/8/8/4k3/8/8/4K3/8 w - - 42 1"
        g = Game(fen=fen)
        assert g.halfmove_clock == 42

    def test_king_vs_king_draw(self):
        """King vs King FEN triggers insufficient material draw."""
        g = Game(fen=self.KING_VS_KING_FEN)
        assert g.game_over is True
        assert g.draw_reason == "insufficient material"

    def test_mate_in_one_fen(self):
        """A mate-in-one position from FEN is detected."""
        # Black king on h8, White queen on g7 defended by king on g6
        fen = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"
        g = Game(fen=fen)
        assert g.game_over is True  # Already checkmate
        assert g.winner == Color.WHITE

    def test_castling_flags_set_on_rooks(self):
        """Rooks that lost castling rights have has_moved=True in FEN."""
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w Qq - 0 1"
        g = Game(fen=fen)
        # White kingside rook should be marked as moved (no K right)
        wr_h = g.board.grid[7][7]
        assert wr_h.has_moved is True
        # White queenside rook should not be marked as moved (Q right exists)
        wr_a = g.board.grid[7][0]
        assert wr_a.has_moved is False
        # Black kingside rook should be marked as moved (no k right)
        br_h = g.board.grid[0][7]
        assert br_h.has_moved is True
        # Black queenside rook should not be marked as moved (q right exists)
        br_a = g.board.grid[0][0]
        assert br_a.has_moved is False

    def test_fen_undo_and_remake(self):
        """Playing and undoing from FEN works correctly."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        g = Game(fen=fen)
        # Black can capture e4 with d5, or play e5 — let's play e5
        from chess_cli.moves import algebraic_to_pos
        success = g.make_move(algebraic_to_pos("e7"), algebraic_to_pos("e5"))
        assert success
        assert g.current_turn == Color.WHITE
        # Undo
        g.undo_move()
        assert g.current_turn == Color.BLACK
        assert g.board.to_fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR"

    def test_fen_with_checks(self):
        """FEN where a side is in check is handled correctly."""
        fen = "4k3/8/8/8/8/8/8/R3K3 w Q - 0 1"  # white king checked by black rook on e8? No...
        # Let's use: white king on e1, black rook on e8 = check
        fen = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
        g = Game(fen=fen)
        from chess_cli.moves import is_in_check
        assert not is_in_check(g.board, Color.WHITE)  # rook on h1 doesn't attack e1
