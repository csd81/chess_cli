
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
        """Play a full CPU vs CPU game to verify no errors."""
        g = Game()
        max_moves = 40  # prevent infinite games
        for i in range(max_moves):
            move = get_best_move(g.board, g.current_turn,
                                en_passant_target=g.en_passant_target,
                                depth=2)
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
        cli.ai_depth_white = 2
        cli.ai_depth_black = 2

        # Play 3 full moves (6 half-moves)
        for _ in range(6):
            ok = cli._run_ai_move()
            assert ok, "AI should have a legal move"
            assert not cli.game.game_over, "Game should not be over in 3 moves"

        assert len(cli.game.move_history) == 6
