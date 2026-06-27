"""Tests for Texel Tuning (scripts/texel_tuner.py)."""

import math
import pytest
from chess_cli.board import Board
from chess_cli.pieces import Color, Piece, PieceType
from chess_cli.ai import PIECE_VALUES, PIECE_TABLES
from scripts.texel_tuner import (
    sigmoid,
    evaluate_white,
    parse_epd_line,
    load_dataset,
    calculate_mse,
    generate_synthetic_dataset,
    tune_piece_values,
    tune_piece_tables,
    tune,
)


class TestSigmoid:
    """Test the sigmoid function."""

    def test_sigmoid_zero(self):
        """Score of 0 should give exactly 0.5."""
        assert sigmoid(0) == 0.5

    def test_sigmoid_positive(self):
        """Positive score -> probability > 0.5."""
        assert sigmoid(100) > 0.5
        assert sigmoid(200) > sigmoid(100)

    def test_sigmoid_negative(self):
        """Negative score -> probability < 0.5."""
        assert sigmoid(-100) < 0.5
        assert sigmoid(-200) < sigmoid(-100)

    def test_sigmoid_symmetry(self):
        """Sigmoid should be symmetric around 0.5."""
        for s in [50, 100, 200, 400]:
            assert abs(sigmoid(s) + sigmoid(-s) - 1.0) < 1e-10

    def test_sigmoid_clamping(self):
        """Very large scores should be clamped."""
        assert sigmoid(5000) > 0.999
        assert sigmoid(-5000) < 0.001
        assert 0.0 < sigmoid(5000) < 1.0

    def test_sigmoid_known_value(self):
        """Test a known sigmoid value."""
        result = sigmoid(400)
        expected = 1.0 / (1.0 + math.pow(10.0, -400.0 / 400.0))
        assert abs(result - expected) < 1e-10

    def test_sigmoid_monotonic(self):
        """Sigmoid should be strictly increasing."""
        scores = list(range(-500, 501, 50))
        probs = [sigmoid(s) for s in scores]
        for i in range(len(probs) - 1):
            assert probs[i] < probs[i + 1]


class TestEvaluateWhite:
    """Test evaluate_white with custom parameters."""

    def test_starting_position_zero(self):
        """Starting position should evaluate to 0."""
        board = Board()
        score = evaluate_white(board, PIECE_VALUES, PIECE_TABLES)
        assert score == 0

    def test_white_up_pawn(self):
        """White up a pawn should give positive score."""
        board = Board()
        board.grid[1][4] = None  # Remove black e7 pawn
        score = evaluate_white(board, PIECE_VALUES, PIECE_TABLES)
        assert score > 0

    def test_black_up_knight(self):
        """Black up a knight should give negative score."""
        board = Board()
        board.grid[7][6] = None  # Remove white knight from g1
        score = evaluate_white(board, PIECE_VALUES, PIECE_TABLES)
        assert score < 0

    def test_custom_values_used(self):
        """evaluate_white should use custom values, not globals."""
        board = Board()
        board.grid[1][4] = None
        custom_values = dict(PIECE_VALUES)
        custom_values[PieceType.PAWN] = 200
        score = evaluate_white(board, custom_values, PIECE_TABLES)
        assert score > 100  # Should be higher than default

    def test_global_unchanged(self):
        """evaluate_white should not modify global PIECE_VALUES."""
        board = Board()
        original = dict(PIECE_VALUES)
        custom = dict(PIECE_VALUES)
        custom[PieceType.PAWN] = 999
        _ = evaluate_white(board, custom, PIECE_TABLES)
        assert PIECE_VALUES == original

class TestEPDParsing:
    """Test EPD line parsing."""

    def test_standard_epd(self):
        """Standard EPD with result tag."""
        line = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 result 0.5"
        result = parse_epd_line(line)
        assert result is not None
        fen, score = result
        assert "rnbqkbnr" in fen
        assert score == 0.5

    def test_pipe_format(self):
        """Pipe-separated format."""
        line = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR | 0.5"
        result = parse_epd_line(line)
        assert result is not None
        assert result[1] == 0.5

    def test_white_win(self):
        """Result of 1.0 for white win."""
        line = "4k3/8/8/8/8/8/8/4K3 | 1.0"
        result = parse_epd_line(line)
        assert result is not None
        assert result[1] == 1.0

    def test_black_win(self):
        """Result of 0.0 for black win."""
        line = "4k3/8/8/8/8/8/8/4K3 | 0.0"
        result = parse_epd_line(line)
        assert result is not None
        assert result[1] == 0.0

    def test_comment_line(self):
        """Comment lines should be skipped."""
        line = "# this is a comment"
        assert parse_epd_line(line) is None

    def test_empty_line(self):
        """Empty lines should be skipped."""
        assert parse_epd_line("") is None
        assert parse_epd_line("   ") is None

    def test_malformed_no_result(self):
        """Line without result should return None."""
        line = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        assert parse_epd_line(line) is None

    def test_result_out_of_range(self):
        """Result > 1.0 or < 0.0 should be rejected."""
        line = "4k3/8/8/8/8/8/8/4K3 | 2.5"
        assert parse_epd_line(line) is None
    

class TestMSECalculation:
    """Test MSE calculation."""

    def test_perfect_prediction(self):
        """If sigmoid(score) == result, MSE should be 0."""
        board = Board()
        dataset = [(board, 0.5)]
        mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        assert mse == 0.0

    def test_worst_prediction(self):
        """If prediction is wrong, MSE should be positive."""
        board = Board()
        dataset = [(board, 0.0)]
        mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        assert abs(mse - 0.25) < 1e-10

    def test_multiple_positions(self):
        """MSE should average over multiple positions."""
        board = Board()
        dataset = [(board, 0.5), (board, 0.0), (board, 1.0)]
        mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        expected = (0.0 + 0.25 + 0.25) / 3.0
        assert abs(mse - expected) < 1e-10

    def test_empty_dataset(self):
        """Empty dataset should return 0 MSE."""
        assert calculate_mse([], PIECE_VALUES, PIECE_TABLES) == 0.0


class TestSyntheticDataset:
    """Test synthetic dataset generation."""

    def test_generates_positions(self):
        """Synthetic dataset should have positions."""
        dataset = generate_synthetic_dataset()
        assert len(dataset) > 0

    def test_all_boards_valid(self):
        """All boards should be valid Board instances."""
        dataset = generate_synthetic_dataset()
        for board, result in dataset:
            assert isinstance(board, Board)
            assert 0.0 <= result <= 1.0

    def test_starting_position_included(self):
        """Starting position should be in the dataset."""
        dataset = generate_synthetic_dataset()
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        found = any(board.to_fen() == start_fen for board, _ in dataset)
        assert found

    def test_varied_results(self):
        """Dataset should have varied results."""
        dataset = generate_synthetic_dataset()
        results = [r for _, r in dataset]
        assert any(r > 0.8 for r in results)
        assert any(r < 0.2 for r in results)
        assert any(0.4 < r < 0.6 for r in results)

class TestTuningConvergence:
    """Test that tuning actually improves MSE."""

    def test_tuning_reduces_mse(self):
        """Tuning should not increase MSE on synthetic dataset."""
        dataset = generate_synthetic_dataset()
        initial_mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        values, tables, final_mse = tune(dataset, max_passes=1, verbose=False)
        assert final_mse <= initial_mse + 1e-12

    def test_tune_piece_values_improves(self):
        """Tuning piece values should not increase MSE."""
        dataset = generate_synthetic_dataset()
        initial_mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        values = dict(PIECE_VALUES)
        tables = {}
        for pt, tbl in PIECE_TABLES.items():
            tables[pt] = [row[:] for row in tbl]
        values, mse, improved = tune_piece_values(
            dataset, values, tables, initial_mse, verbose=False)
        assert mse <= initial_mse + 1e-12

    def test_tune_piece_tables_valid(self):
        """Tuning piece tables should produce valid 8x8 tables."""
        dataset = generate_synthetic_dataset()
        initial_mse = calculate_mse(dataset, PIECE_VALUES, PIECE_TABLES)
        values = dict(PIECE_VALUES)
        tables = {}
        for pt, tbl in PIECE_TABLES.items():
            tables[pt] = [row[:] for row in tbl]
        tables, mse, improved = tune_piece_tables(
            dataset, values, tables, initial_mse, verbose=False)
        for pt in tables:
            assert len(tables[pt]) == 8
            for row in tables[pt]:
                assert len(row) == 8