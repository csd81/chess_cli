"""Tests for UCI protocol implementation."""

import pytest
from chess_cli.game import Game
from chess_cli.pieces import Color, Piece, PieceType
from chess_cli.moves import algebraic_to_pos, generate_legal_moves
from chess_cli.ai import get_best_move, clear_tt
from chess_cli.uci import handle_position, handle_go, parse_time, uci_loop


class TestUCIMoveFromString:
    """Test make_move_from_uci on Game."""

    def test_standard_move(self, game):
        """Simple pawn move from UCI string."""
        assert game.make_move_from_uci("e2e4") is True
        assert game.move_history[0].uci() == "e2e4"

    def test_invalid_move(self, game):
        """Invalid UCI string returns False."""
        assert game.make_move_from_uci("e2e5") is False

    def test_promotion_move(self):
        """Promotion UCI string works."""
        g = Game()
        g.board.grid = [[None] * 8 for _ in range(8)]
        g.board.grid[0][0] = Piece(Color.BLACK, PieceType.KING)
        g.board.grid[7][4] = Piece(Color.WHITE, PieceType.KING)
        g.board.grid[1][3] = Piece(Color.WHITE, PieceType.PAWN)
        g.current_turn = Color.WHITE
        assert g.make_move_from_uci("d7d8q") is True
        assert g.board.grid[0][3].piece_type == PieceType.QUEEN

    def test_promotion_to_knight(self):
        """Promotion to knight via UCI."""
        g = Game()
        g.board.grid = [[None] * 8 for _ in range(8)]
        g.board.grid[0][0] = Piece(Color.BLACK, PieceType.KING)
        g.board.grid[7][4] = Piece(Color.WHITE, PieceType.KING)
        g.board.grid[1][3] = Piece(Color.WHITE, PieceType.PAWN)
        g.current_turn = Color.WHITE
        assert g.make_move_from_uci("d7d8n") is True
        assert g.board.grid[0][3].piece_type == PieceType.KNIGHT

    def test_empty_string(self, game):
        """Empty/too-short UCI returns False."""
        assert game.make_move_from_uci("") is False
        assert game.make_move_from_uci("e2") is False


class TestUCIPosition:
    """Test the position command handler."""

    def test_position_startpos(self):
        g = Game()
        g = handle_position(g, ["startpos"])
        assert g.board.to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        assert g.current_turn == Color.WHITE

    def test_position_startpos_moves(self):
        g = Game()
        g = handle_position(g, ["startpos", "moves", "e2e4", "e7e5"])
        assert len(g.move_history) == 2
        assert g.move_history[0].uci() == "e2e4"
        assert g.move_history[1].uci() == "e7e5"
        assert g.current_turn == Color.WHITE

    def test_position_fen(self):
        g = Game()
        g = handle_position(g, ["fen", "4k3/8/8/8/8/8/8/4K3", "w", "-", "-", "0", "1"])
        assert g.board.to_fen() == "4k3/8/8/8/8/8/8/4K3"
        assert g.current_turn == Color.WHITE

    def test_position_fen_moves(self):
        g = Game()
        g = handle_position(g, ["fen", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR", "b",
                           "KQkq", "e3", "0", "1", "moves", "e7e5"])
        assert len(g.move_history) == 1
        assert g.move_history[0].uci() == "e7e5"

    def test_position_startpos_full_game(self):
        g = Game()
        g = handle_position(g, ["startpos", "moves",
                           "e2e4", "e7e5", "g1f3", "b8c6",
                           "f1c4", "g8f6", "e1g1"])
        assert len(g.move_history) == 7
        assert g.current_turn == Color.BLACK


class TestUCIParseGo:

    def test_go_depth_returns_fixed_depth(self):
        g = Game()
        budget, depth = parse_time(["depth", "5"], g)
        assert budget is None
        assert depth == 5

    def test_go_wtime_btime(self):
        g = Game()
        budget, depth = parse_time(["wtime", "300000", "btime", "200000"], g)
        assert budget is not None
        assert budget > 0.01
        assert depth is None

    def test_go_empty_args(self):
        g = Game()
        budget, depth = parse_time([], g)
        assert budget == 0.5
        assert depth is None


class TestUCIHandleGo:

    def test_go_returns_bestmove(self, capsys):
        g = Game()
        handle_go(g, ["depth", "2"])
        captured = capsys.readouterr().out.strip()
        assert captured.startswith("bestmove ")

    def test_go_with_position(self, capsys):
        g = Game()
        g = handle_position(g, ["startpos"])
        handle_go(g, ["depth", "2"])
        captured = capsys.readouterr().out.strip()
        assert captured.startswith("bestmove ")

    def test_go_middlegame(self, capsys):
        g = Game()
        g = handle_position(g, ["startpos", "moves", "e2e4", "e7e5", "g1f3", "b8c6"])
        handle_go(g, ["depth", "2"])
        captured = capsys.readouterr().out.strip()
        assert captured.startswith("bestmove ")


class TestUCIFullLoop:

    def test_uci_handshake(self):
        import io, sys
        test_input = "uci\nisready\nquit\n"
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(test_input)
        sys.stdout = io.StringIO()
        try:
            uci_loop()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        assert "id name ChessCLI" in output
        assert "uciok" in output
        assert "readyok" in output

    def test_ucinewgame_resets(self):
        import io, sys
        test_input = "uci\nposition startpos moves e2e4\nucinewgame\nposition startpos\ngo depth 2\nquit\n"
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(test_input)
        sys.stdout = io.StringIO()
        try:
            uci_loop()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        assert "bestmove" in output

    def test_position_and_go(self):
        import io, sys
        test_input = "uci\nposition startpos moves e2e4 e7e5\ngo depth 2\nquit\n"
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(test_input)
        sys.stdout = io.StringIO()
        try:
            uci_loop()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        assert "bestmove" in output

    def test_fen_position(self):
        import io, sys
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
        test_input = f"uci\nposition fen {fen}\ngo depth 2\nquit\n"
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(test_input)
        sys.stdout = io.StringIO()
        try:
            uci_loop()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        assert "bestmove" in output

    def test_quit_handling(self):
        import io, sys
        test_input = "uci\nquit\n"
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(test_input)
        sys.stdout = io.StringIO()
        try:
            uci_loop()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        assert "uciok" in output
