"""Shared pytest fixtures for chess tests."""

import pytest
from chess_cli.board import Board
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.game import Game
from chess_cli.moves import Move, pos_to_algebraic, algebraic_to_pos, generate_legal_moves, _get_pseudo_legal_moves_for_piece


@pytest.fixture
def empty_board():
    """An 8x8 board with no pieces."""
    b = Board.__new__(Board)
    b.grid = [[None] * 8 for _ in range(8)]
    return b


@pytest.fixture
def start_board():
    """Standard starting position."""
    return Board()


@pytest.fixture
def game():
    """A fresh Game instance."""
    return Game()


@pytest.fixture
def white_knight():
    return Piece(Color.WHITE, PieceType.KNIGHT)


@pytest.fixture
def white_pawn():
    return Piece(Color.WHITE, PieceType.PAWN)
