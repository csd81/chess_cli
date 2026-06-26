"""Tests for ANSI board colors and last move highlighting."""

import pytest
import re
from chess_cli.board import Board, BG_LIGHT, BG_DARK, BG_LAST_MOVE, FG_BLACK_PIECE, FG_WHITE_PIECE, RESET
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.game import Game
from chess_cli.moves import algebraic_to_pos


def _cell_content(cell_str: str) -> str:
    """Strip ANSI codes from a cell string, returning the visible 3-char content."""
    clean = re.sub(r'\033\[[0-9;]+m', '', cell_str)
    return clean


def _cell_bg(cell_str: str) -> str:
    """Extract the background ANSI code from a cell string."""
    if BG_LAST_MOVE in cell_str:
        return BG_LAST_MOVE
    if BG_LIGHT in cell_str:
        return BG_LIGHT
    if BG_DARK in cell_str:
        return BG_DARK
    return ""


def _cell_fg(cell_str: str) -> str:
    """Extract the foreground ANSI code from a cell string."""
    if FG_BLACK_PIECE in cell_str:
        return FG_BLACK_PIECE
    if FG_WHITE_PIECE in cell_str:
        return FG_WHITE_PIECE
    return ""


def _parse_rank_line(line: str):
    """Parse a rank line like '8 |cell|cell|...|cell|' into a list of cell strings."""
    parts = line.split("|")
    # parts[0] is rank label, parts[-1] is empty string after trailing |
    # parts[1:-1] are the 8 cell strings
    return parts[1:-1] if len(parts) >= 9 else []


class TestANSICodes:
    def test_ansi_codes_in_output(self, start_board):
        output = start_board.display()
        assert "\033[" in output, "ANSI escape codes should be present"

    def test_sixty_four_resets(self, start_board):
        output = start_board.display()
        count = output.count(RESET)
        assert count == 64, f"Expected 64 RESET codes, got {count}"

    def test_both_backgrounds_present(self, start_board):
        output = start_board.display()
        assert BG_LIGHT in output, "BG_LIGHT should appear"
        assert BG_DARK in output, "BG_DARK should appear"

    def test_both_foregrounds_present(self, start_board):
        output = start_board.display()
        assert FG_BLACK_PIECE in output, "FG_BLACK_PIECE should appear"
        assert FG_WHITE_PIECE in output, "FG_WHITE_PIECE should appear"

    def test_checkerboard_alternates(self, start_board):
        """Verify adjacent cells in the same row alternate background colors."""
        output = start_board.display()
        lines = output.split("\n")
        # The first rank line (8) is line index 1 (after the border at 0)
        rank_line = lines[1]
        cells = _parse_rank_line(rank_line)
        assert len(cells) == 8
        for i in range(7):
            bg_a = _cell_bg(cells[i])
            bg_b = _cell_bg(cells[i + 1])
            assert bg_a != bg_b, f"Cells at col {i} and {i+1} should have different backgrounds"

    def test_display_structure_preserved(self, start_board):
        """Verify the board still has correct borders and labels."""
        output = start_board.display()
        lines = output.split("\n")
        # Check header border
        assert lines[0] == "  +---+---+---+---+---+---+---+---+"
        # Check last border
        assert lines[-2] == "  +---+---+---+---+---+---+---+---+"
        # Check file labels
        assert lines[-1] == "    a   b   c   d   e   f   g   h  "
        # Check rank labels are present
        assert any(line.startswith("8 ") for line in lines)
        assert any(line.startswith("1 ") for line in lines)

    def test_pipe_separators_present(self, start_board):
        """Verify each rank line has proper pipe separators."""
        output = start_board.display()
        lines = output.split("\n")
        # Odd-indexed lines (1, 3, 5, 7, 9, 11, 13, 15) are rank lines
        for i in range(1, 16, 2):
            line = lines[i]
            # Should have rank label followed by 8 pipes (9 total including trailing)
            assert line.count("|") == 9, f"Line {i} should have 9 pipes"

    def test_cell_width_three(self, start_board):
        """Verify each visible cell is exactly 3 characters wide."""
        output = start_board.display()
        lines = output.split("\n")
        rank_line = lines[1]  # Rank 8 line
        cells = _parse_rank_line(rank_line)
        for cell in cells:
            visible = _cell_content(cell)
            assert len(visible) == 3, f"Cell content '{visible}' should be 3 chars, got {len(visible)}"

class TestLastMoveHighlight:
    def test_last_move_squares_have_yellow(self, empty_board):
        """Verify last_move from/to squares get BG_LAST_MOVE."""
        output = empty_board.display(last_move=((6, 4), (4, 4)))
        lines = output.split("\n")

        # In reversed view: row 6 = rank 2, row 4 = rank 4
        for line in lines:
            if line.startswith("2 "):
                cells = _parse_rank_line(line)
                # e2 is at col 4 (e-file)
                assert BG_LAST_MOVE in cells[4], "e2 (row 6, col 4) should have yellow background"
            if line.startswith("4 "):
                cells = _parse_rank_line(line)
                # e4 is at col 4 (e-file)
                assert BG_LAST_MOVE in cells[4], "e4 (row 4, col 4) should have yellow background"

    def test_other_squares_no_yellow(self, empty_board):
        """Verify squares not in last_move don't get BG_LAST_MOVE."""
        output = empty_board.display(last_move=((6, 4), (4, 4)))
        lines = output.split("\n")
        # Check rank 1 (row 7) - none of its squares should be yellow
        for line in lines:
            if line.startswith("1 "):
                cells = _parse_rank_line(line)
                for i, cell in enumerate(cells):
                    assert BG_LAST_MOVE not in cell, f"Rank 1 col {i} should not be yellow"

    def test_last_move_clear_after_undo(self, game):
        """After undo, the last_move changes to the previous move's squares."""
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        game.make_move(algebraic_to_pos("e7"), algebraic_to_pos("e5"))
        game.undo_move()
        # Last move should now be e2e4
        assert len(game.move_history) == 1
        last = game.move_history[0]
        assert last.from_pos == (6, 4)
        assert last.to_pos == (4, 4)

    def test_integration_via_game(self, game):
        """Verify that after a game move, the display includes yellow highlights."""
        game.make_move(algebraic_to_pos("e2"), algebraic_to_pos("e4"))
        output = game.board.display(
            last_move=(game.move_history[-1].from_pos, game.move_history[-1].to_pos)
        )
        assert BG_LAST_MOVE in output

class TestPieceColors:
    def test_white_piece_black_text(self, empty_board):
        """White pieces should have FG_BLACK_PIECE."""
        wp = Piece(Color.WHITE, PieceType.KING)
        empty_board.set_piece(7, 4, wp)
        output = empty_board.display()
        lines = output.split("\n")
        for line in lines:
            if line.startswith("1 "):  # Rank 1 (row 7 in internal coords)
                cells = _parse_rank_line(line)
                assert FG_BLACK_PIECE in cells[4], "White king should have black foreground text"

    def test_black_piece_white_text(self, empty_board):
        """Black pieces should have FG_WHITE_PIECE."""
        bp = Piece(Color.BLACK, PieceType.KING)
        empty_board.set_piece(0, 4, bp)
        output = empty_board.display()
        lines = output.split("\n")
        for line in lines:
            if line.startswith("8 "):  # Rank 8 (row 0 in internal coords)
                cells = _parse_rank_line(line)
                assert FG_WHITE_PIECE in cells[4], "Black king should have white foreground text"

    def test_same_square_fg_and_bg(self, empty_board):
        """A piece cell should have both background and foreground codes."""
        wp = Piece(Color.WHITE, PieceType.PAWN)
        empty_board.set_piece(3, 3, wp)
        output = empty_board.display()
        assert FG_BLACK_PIECE in output
        assert BG_LIGHT in output or BG_DARK in output or BG_LAST_MOVE in output


class TestHighlightSquaresCoexist:
    def test_brackets_with_ansi(self, empty_board):
        """highlight_squares bracket notation should work alongside ANSI colors."""
        wp = Piece(Color.WHITE, PieceType.KNIGHT)
        empty_board.set_piece(4, 4, wp)
        output = empty_board.display(highlight_squares=[(4, 4)])
        assert BG_LIGHT in output or BG_DARK in output, "Background codes still present"
        assert "[N]" in output, "highlighted knight should show [N]"

    def test_brackets_no_ansi_interference(self, empty_board):
        """Bracket notation should not be corrupted by ANSI codes."""
        output = empty_board.display(highlight_squares=[(0, 0)])
        assert "[ ]" in output, "Empty highlighted square should show [ ]"

    def test_last_move_and_highlight_together(self, empty_board):
        """Both last_move and highlight_squares work together."""
        wp = Piece(Color.WHITE, PieceType.PAWN)
        empty_board.set_piece(6, 4, wp)
        output = empty_board.display(
            highlight_squares=[(4, 4)],
            last_move=((6, 4), (4, 4))
        )
        assert BG_LAST_MOVE in output
        lines = output.split("\n")
        for line in lines:
            if line.startswith("4 "):
                cells = _parse_rank_line(line)
                target_cell = cells[4]
                assert BG_LAST_MOVE in target_cell
                content = _cell_content(target_cell)
                assert "[ ]" in content or "[P]" in content


class TestReversedView:
    def test_reversed_false_has_ansi(self, start_board):
        """reversed_view=False should still have ANSI colors."""
        output = start_board.display(reversed_view=False)
        assert "\033[" in output
        assert BG_LIGHT in output
        assert BG_DARK in output

    def test_reversed_view_rank_order(self, start_board):
        """reversed_view=False shows rank 1 at top."""
        output = start_board.display(reversed_view=False)
        lines = output.split("\n")
        assert lines[1].startswith("1 "), "First rank should be 1 in reversed_view=False"

    def test_reversed_view_highlight_works(self, empty_board):
        """highlight_squares works in reversed_view=False."""
        output = empty_board.display(reversed_view=False, highlight_squares=[(0, 0)])
        assert "\033[" in output
        assert RESET in output
