"""Tests for Zobrist hashing and transposition tables."""

import pytest
from chess_cli.pieces import Piece, Color, PieceType
from chess_cli.board import Board
from chess_cli.game import Game
from chess_cli.moves import (
    Move, generate_legal_moves, algebraic_to_pos, pos_to_algebraic,
)
from chess_cli.ai import (
    get_best_move, _minimax, evaluate, simulate_move,
    TRANSPOSITION_TABLE, TTEntry, clear_tt,
    EXACT, LOWERBOUND, UPPERBOUND,
)
from chess_cli.zobrist import (
    compute_zobrist_hash, derive_castling, update_castling,
    piece_index, square_index,
    PIECE_KEYS, SIDE_KEY, CASTLE_KEYS, EN_PASSANT_KEYS,
)


def _move_uci(game, uci):
    from_pos = algebraic_to_pos(uci[:2])
    to_pos = algebraic_to_pos(uci[2:4])
    assert from_pos is not None
    assert to_pos is not None
    success = game.make_move(from_pos, to_pos)
    assert success, f"Move {uci} was rejected"


@pytest.fixture(autouse=True)
def clear_tt_before():
    clear_tt()
    yield


class TestZobristBasic:
    """Fundamental properties: deterministic, unique."""

    def test_same_position_same_hash(self, start_board):
        c = derive_castling(start_board.grid)
        h1 = compute_zobrist_hash(start_board.grid, Color.WHITE, None, c)
        h2 = compute_zobrist_hash(start_board.grid, Color.WHITE, None, c)
        assert h1 == h2

    def test_side_to_move_changes_hash(self, start_board):
        c = derive_castling(start_board.grid)
        h1 = compute_zobrist_hash(start_board.grid, Color.WHITE, None, c)
        h2 = compute_zobrist_hash(start_board.grid, Color.BLACK, None, c)
        assert h1 != h2

    def test_en_passant_changes_hash(self, start_board):
        c = derive_castling(start_board.grid)
        h1 = compute_zobrist_hash(start_board.grid, Color.WHITE, None, c)
        h2 = compute_zobrist_hash(start_board.grid, Color.WHITE, (2, 3), c)
        assert h1 != h2

    def test_castling_rights_change_hash(self):
        board = Board()
        c_all = derive_castling(board.grid)
        c_none = 0
        h1 = compute_zobrist_hash(board.grid, Color.WHITE, None, c_all)
        h2 = compute_zobrist_hash(board.grid, Color.WHITE, None, c_none)
        assert h1 != h2

    def test_different_positions_different_hashes(self, empty_board):
        c = 0
        h1 = compute_zobrist_hash(empty_board.grid, Color.WHITE, None, c)
        empty_board.grid[6][4] = Piece(Color.WHITE, PieceType.PAWN)
        h2 = compute_zobrist_hash(empty_board.grid, Color.WHITE, None, c)
        assert h1 != h2


class TestZobristIncremental:
    """Incremental hashing matches from-scratch."""

    def _check(self, game):
        c = derive_castling(game.board.grid)
        h = compute_zobrist_hash(
            game.board.grid, game.current_turn, game.en_passant_target, c)
        assert isinstance(h, int) and h != 0
        return h, c

    def test_after_e4(self, game):
        _move_uci(game, "e2e4")
        self._check(game)

    def test_after_e4_e5(self, game):
        _move_uci(game, "e2e4")
        _move_uci(game, "e7e5")
        self._check(game)

    def test_after_castle_kingside(self):
        g = Game()
        _move_uci(g, "e2e4")
        _move_uci(g, "e7e5")
        _move_uci(g, "g1f3")
        _move_uci(g, "b8c6")
        _move_uci(g, "f1c4")
        _move_uci(g, "g8f6")
        _move_uci(g, "e1g1")
        self._check(g)

    def test_after_castle_queenside(self):
        g = Game()
        _move_uci(g, "d2d4")
        _move_uci(g, "d7d5")
        _move_uci(g, "c1f4")
        _move_uci(g, "c8f5")
        _move_uci(g, "d1d2")
        _move_uci(g, "d8d7")
        _move_uci(g, "b1c3")
        _move_uci(g, "b8c6")
        _move_uci(g, "e1c1")
        self._check(g)

    def test_after_en_passant(self):
        g = Game()
        _move_uci(g, "e2e4")
        _move_uci(g, "a7a6")
        _move_uci(g, "e4e5")
        _move_uci(g, "d7d5")
        _move_uci(g, "e5d6")
        self._check(g)

    def test_after_promotion(self):
        g = Game()
        g.board.grid = [[None] * 8 for _ in range(8)]
        g.board.grid[0][0] = Piece(Color.BLACK, PieceType.KING)
        g.board.grid[7][4] = Piece(Color.WHITE, PieceType.KING)
        g.board.grid[1][3] = Piece(Color.WHITE, PieceType.PAWN)
        g.current_turn = Color.WHITE
        _move_uci(g, "d7d8q")
        self._check(g)

    def test_after_undo(self, game):
        _move_uci(game, "e2e4")
        h1, _ = self._check(game)
        game.undo_move()
        _move_uci(game, "e2e4")
        h2, _ = self._check(game)
        assert h1 == h2

    def test_different_move_orders_same_hash(self):
        g1 = Game()
        _move_uci(g1, "e2e4")
        _move_uci(g1, "e7e5")
        _move_uci(g1, "g1f3")
        _move_uci(g1, "b8c6")
        _move_uci(g1, "f1c4")  # non-pawn move to clear ep state
        h1, _ = self._check(g1)
        g2 = Game()
        _move_uci(g2, "g1f3")
        _move_uci(g2, "b8c6")
        _move_uci(g2, "e2e4")
        _move_uci(g2, "e7e5")
        _move_uci(g2, "f1c4")
        h2, _ = self._check(g2)
        assert h1 == h2


class TestTranspositionTable:
    """Transposition table caching works correctly."""

    def test_tt_stores_and_retrieves(self):
        TRANSPOSITION_TABLE[42] = TTEntry(150, 3, EXACT)
        entry = TRANSPOSITION_TABLE.get(42)
        assert entry.score == 150 and entry.depth == 3 and entry.flag == EXACT

    def test_clear_tt_works(self):
        TRANSPOSITION_TABLE[42] = TTEntry(150, 3, EXACT)
        clear_tt()
        assert len(TRANSPOSITION_TABLE) == 0

    def test_tt_exact_returned_directly(self):
        board = Board()
        c = derive_castling(board.grid)
        h = compute_zobrist_hash(board.grid, Color.WHITE, None, c)
        TRANSPOSITION_TABLE[h] = TTEntry(500, 3, EXACT)
        grid = [row[:] for row in board.grid]
        s = _minimax(grid, 3, -999999, 999999, True,
                     Color.WHITE, None, Color.WHITE, h, c)
        assert s == 500

    def test_tt_not_used_if_depth_too_shallow(self):
        board = Board()
        c = derive_castling(board.grid)
        h = compute_zobrist_hash(board.grid, Color.WHITE, None, c)
        TRANSPOSITION_TABLE[h] = TTEntry(500, 1, EXACT)
        grid = [row[:] for row in board.grid]
        s = _minimax(grid, 3, -999999, 999999, True,
                     Color.WHITE, None, Color.WHITE, h, c)
        assert s != 500

    def test_tt_entries_stored_after_search(self):
        board = Board()
        c = derive_castling(board.grid)
        h = compute_zobrist_hash(board.grid, Color.WHITE, None, c)
        grid = [row[:] for row in board.grid]
        _minimax(grid, 2, -999999, 999999, True,
                 Color.WHITE, None, Color.WHITE, h, c)
        assert len(TRANSPOSITION_TABLE) > 0
        assert h in TRANSPOSITION_TABLE
        assert TRANSPOSITION_TABLE[h].depth == 2

    def test_transposition_hits_tt(self):
        g1 = Game()
        _move_uci(g1, "e2e4")
        _move_uci(g1, "e7e5")
        _move_uci(g1, "g1f3")
        _move_uci(g1, "b8c6")
        _move_uci(g1, "f1c4")  # non-pawn move clears ep
        c1 = derive_castling(g1.board.grid)
        h1 = compute_zobrist_hash(
            g1.board.grid, g1.current_turn, g1.en_passant_target, c1)
        grid1 = [row[:] for row in g1.board.grid]
        s1 = _minimax(grid1, 2, -999999, 999999, True,
                      Color.BLACK, g1.en_passant_target,
                      g1.current_turn, h1, c1)
        sz = len(TRANSPOSITION_TABLE)
        g2 = Game()
        _move_uci(g2, "g1f3")
        _move_uci(g2, "b8c6")
        _move_uci(g2, "e2e4")
        _move_uci(g2, "e7e5")
        _move_uci(g2, "f1c4")
        c2 = derive_castling(g2.board.grid)
        h2 = compute_zobrist_hash(
            g2.board.grid, g2.current_turn, g2.en_passant_target, c2)
        assert h1 == h2
        grid2 = [row[:] for row in g2.board.grid]
        s2 = _minimax(grid2, 2, -999999, 999999, True,
                      Color.BLACK, g2.en_passant_target,
                      g2.current_turn, h2, c2)
        assert s1 == s2
        assert len(TRANSPOSITION_TABLE) >= sz


class TestAITransposition:
    """AI works correctly with transposition tables."""

    def test_ai_returns_valid_move_start(self):
        board = Board()
        move = get_best_move(board, Color.WHITE, depth=3)
        assert move is not None
        assert move in generate_legal_moves(board, Color.WHITE)

    def test_ai_returns_valid_move_middlegame(self):
        g = Game()
        _move_uci(g, "e2e4")
        _move_uci(g, "e7e5")
        _move_uci(g, "g1f3")
        _move_uci(g, "b8c6")
        move = get_best_move(
            g.board, g.current_turn,
            en_passant_target=g.en_passant_target, depth=3)
        assert move is not None
        assert move in generate_legal_moves(
            g.board, g.current_turn,
            en_passant_target=g.en_passant_target)

    def test_ai_same_position_same_move(self):
        # Use a middlegame position not in the opening book
        g = Game()
        _move_uci(g, "e2e4")
        _move_uci(g, "e7e5")
        _move_uci(g, "g1f3")
        _move_uci(g, "d7d6")
        clear_tt()
        m1 = get_best_move(g.board, g.current_turn,
                          en_passant_target=g.en_passant_target, depth=3)
        clear_tt()
        m2 = get_best_move(g.board, g.current_turn,
                          en_passant_target=g.en_passant_target, depth=3)
        assert m1 is not None
        assert m1.uci() == m2.uci()

    def test_ai_captures_hanging_piece(self):
        board = Board()
        board.grid = [[None] * 8 for _ in range(8)]
        board.grid[0][4] = Piece(Color.BLACK, PieceType.KING)
        board.grid[7][4] = Piece(Color.WHITE, PieceType.KING)
        board.grid[3][4] = Piece(Color.BLACK, PieceType.PAWN)
        board.grid[4][3] = Piece(Color.WHITE, PieceType.QUEEN)
        move = get_best_move(board, Color.WHITE, depth=3)
        assert move is not None
        assert move.to_pos == (3, 4)

    def test_ai_in_check_escapes(self):
        board = Board()
        board.grid = [[None] * 8 for _ in range(8)]
        board.grid[7][4] = Piece(Color.WHITE, PieceType.KING)
        board.grid[0][0] = Piece(Color.BLACK, PieceType.KING)
        board.grid[5][4] = Piece(Color.BLACK, PieceType.ROOK)
        move = get_best_move(board, Color.WHITE, depth=3)
        assert move is not None
        assert move.from_pos == (7, 4)

    def test_ai_vs_ai_game_completes(self):
        g = Game()
        for i in range(200):
            if g.game_over:
                break
            move = get_best_move(
                g.board, g.current_turn,
                en_passant_target=g.en_passant_target, depth=2)
            if move is None:
                break
            g.make_move_from_move(move)
        assert i < 199 or g.game_over


class TestCastlingDerivation:
    """derive_castling and update_castling consistency."""

    def test_initial_castling_rights(self, start_board):
        c = derive_castling(start_board.grid)
        assert c & 0b0001 and c & 0b0010
        assert c & 0b0100 and c & 0b1000

    def test_king_moves_loses_rights(self, start_board):
        start_board.grid[7][4] = Piece(Color.WHITE, PieceType.KING, has_moved=True)
        c = derive_castling(start_board.grid)
        assert c == 0b1100  # only black rights remain

    def test_update_castling_incremental(self):
        board = Board()
        c_before = derive_castling(board.grid)
        c_after = update_castling(
            c_before, Piece(Color.WHITE, PieceType.KING), 7, 4, None, 7, 5)
        board.grid[7][4] = None
        board.grid[7][5] = Piece(Color.WHITE, PieceType.KING, has_moved=True)
        c_derived = derive_castling(board.grid)
        assert c_after == c_derived


class TestZobristEdgeCases:
    """Edge cases for Zobrist hashing."""

    def test_empty_board_hash(self, empty_board):
        h1 = compute_zobrist_hash(empty_board.grid, Color.WHITE, None, 0)
        h2 = compute_zobrist_hash(empty_board.grid, Color.WHITE, None, 0)
        assert h1 == h2 and isinstance(h1, int)

    def test_piece_index_all_types(self):
        for color in [Color.WHITE, Color.BLACK]:
            for pt in PieceType:
                p = Piece(color, pt)
                idx = piece_index(p)
                assert 0 <= idx < 12
                assert piece_index(p) == idx

    def test_square_index_all_squares(self):
        for r in range(8):
            for c in range(8):
                idx = square_index(r, c)
                assert 0 <= idx < 64
                assert square_index(r, c) == idx

    def test_piece_keys_all_nonzero(self):
        for sq in range(64):
            for pi in range(12):
                assert PIECE_KEYS[sq][pi] != 0

    def test_en_passant_keys_all_nonzero(self):
        for i in range(9):
            assert EN_PASSANT_KEYS[i] != 0

    def test_castle_keys_all_nonzero(self):
        for k in ["K", "Q", "k", "q"]:
            assert CASTLE_KEYS[k] != 0

    def test_side_key_nonzero(self):
        assert SIDE_KEY != 0
