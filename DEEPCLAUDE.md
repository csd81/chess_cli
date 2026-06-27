# DEEPCLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (classic CLI)
python main.py

# Run the TUI
python main.py --tui

# Run the web server (needs fastapi + uvicorn)
python main.py --web

# Install dependencies
pip install -r requirements.txt

# Run full test suite
python -m pytest tests/ -v --tb=short

# Run a single test file
python -m pytest tests/test_transposition.py -v --tb=short

# Run a single test
python -m pytest tests/test_transposition.py::TestIterativeDeepening::test_time_limit_returns_valid_move -v

# Run tests with timing breakdown
python -m pytest tests/ --tb=short --durations=10
```

## Architecture (Big Picture)

The project is a chess engine with three user interfaces (CLI, TUI, Web) sharing a common core.

```
main.py                    Entry point (--tui, --web, or default CLI)
chess_cli/                 Core engine + CLIs
  pieces.py                Piece, Color, PieceType enums/dataclass
  board.py                 Board grid, FEN serialization, ANSI display
  moves.py                 Move generation, validation, check/checkmate detection
  game.py                  Game state, move execution, undo, PGN export, draw rules
  ai.py                    AI engine (minimax + alpha-beta + TT + quiescence + iterative deepening)
  zobrist.py               Zobrist hashing for transposition table keys
  opening_book.py          Opening book (dictionary of FEN -> list of UCI moves)
  cli.py                   Classic scrolling CLI interface
  tui.py                   Textual TUI application (widget-based full-screen UI)
  tui_styles/tui.tcss      TUI stylesheet (dark theme)
  __init__.py              Package marker (version 0.1.0)
web/                       FastAPI web server + static frontend
  server.py                REST API endpoints
  static/                  Frontend HTML/CSS/JS
tests/                     Pytest test suite
plans/                     Implementation plans (documentation of features)
```

### Core Engine Data Flow

1. **Board** (`board.py`): 8x8 grid of `Optional[Piece]`. Row 0 = rank 8 (top), row 7 = rank 1 (bottom). Supports FEN import/export and ANSI-colored display string generation.

2. **Pieces** (`pieces.py`): `Color` enum (WHITE/BLACK with `.opponent()` helper). `PieceType` enum (PAWN through KING). `Piece` dataclass (color, piece_type, has_moved flag). `letter()` returns algebraic notation (empty string for pawns).

3. **Moves** (`moves.py`): `Move` dataclass with from_pos, to_pos, piece, captured, promotion, is_castle, is_en_passant. `uci()` returns standard notation. `generate_legal_moves(board, turn, en_passant_target)` generates pseudo-legal moves per piece type then filters by king safety. `pos_to_algebraic` / `algebraic_to_pos` convert between (row, col) and strings.

4. **Game** (`game.py`): Orchestrates everything. Tracks board, current_turn, move_history, game_over, winner, en_passant_target, halfmove_clock, position_history. `_execute_move(move)` handles all side effects: en passant, castling rook movement, promotion, check/checkmate, draw detection. `undo_move()` reverses all of these. `export_pgn()` produces standard PGN with 7-tag roster.

### AI Engine (ai.py)

The engine uses **minimax with alpha-beta pruning** on raw grids (not Board objects) for performance:

- **Piece-square tables**: Positional bonuses/penalties for each piece type on each square.
- **Transposition table**: Global `dict[int, TTEntry]` keyed by Zobrist hash. Stores score, depth, and EXACT/LOWERBOUND/UPPERBOUND flags. Cleared between games via `clear_tt()`.
- **Quiescence search**: At depth=0, continues searching only captures using MVV-LVA ordering, stand-pat evaluation, and delta pruning.
- **Iterative deepening**: When `time_limit` is passed to `get_best_move()`, searches depth=1,2,3... until time runs out. Best move from previous depth is promoted to front of root list. Uses `_check_timeout(end_time)` every 1024 nodes.
- **Zobrist hashing**: `simulate_move()` returns (new_grid, new_en_passant, new_hash, new_castling). Hash is updated incrementally via XOR.
- **Opening book**: Checked at root of `get_best_move()` -- returns instantly if position is in the book.

### Key Design Decisions

- **simulate_move() is NOT in Board or Game**: It lives in ai.py and takes a raw grid + hash + castling mask to avoid Board object creation overhead during search (millions of nodes).
- **Minimax operates on raw grids**: Creates temporary Board objects only when evaluate(), generate_legal_moves(), or checkmate/stalemate checks are needed.
- **Castling rights bitmask**: 0b0001=K, 0b0010=Q, 0b0100=k, 0b1000=q. Updated incrementally by update_castling() without board scans.
- **Three interfaces, same engine**: CLI, TUI, and Web all call Game and get_best_move() the same way.
- **No external chess libraries**: Everything is hand-built -- move generation, evaluation, search, FEN, PGN. Only textual (TUI) and fastapi/uvicorn (web) are external deps.
- **get_best_move() two modes**: depth=N for fixed-depth (backward compat), time_limit=N for iterative deepening.

### Test Patterns

Tests use pytest with shared fixtures in conftest.py (empty_board, start_board, game). The transposition test file has an auto-use fixture clear_tt_before that clears the global TT before each test. AI tests use a helper _move_uci(game, uci).

**Critical rules:**
- **Every feature must have tests.** No feature is considered complete without a test file or test class covering it.
- **Tests must run fast.** The full suite must complete in under 30 seconds. This means:
  - Use small time budgets (0.01-0.05s) in time-limited AI tests, never >0.1s.
  - Keep AI search depths at 1-2 when the goal is testing game completion or integration, not search strength.
  - Keep AI-vs-AI move counts low (6-20 moves per test, not hundreds).
  - Avoid real wall-clock sleeps or delays.

### Important Conventions

- **Coordinates**: (row, col) tuples. Row 0 = rank 8 (top), row 7 = rank 1 (bottom). Col 0 = file a, col 7 = file h.
- **FEN**: Row 0 (rank 8) is first in the FEN string.
- **UCI strings**: Files a-h, ranks 1-8 (e.g. "e2e4").
- **Minimax/quiescence accept end_time=0**: Default 0 means no timeout, preserving backward compat.
- **Global state**: TRANSPOSITION_TABLE and _node_count are module-level globals in ai.py. Always call clear_tt() between games.
