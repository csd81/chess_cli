# Chess CLI/TUI

A feature-rich chess game with a classic CLI and a modern Textual Terminal User Interface (TUI), written in Python.

## Getting Started

```bash
# Classic CLI (default)
python main.py

# Textual TUI (modern full-screen interface)
python main.py --tui

# or
python main.py -t
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## How to Play — Classic CLI

Enter moves in UCI notation:

```
e2e4    Move pawn from e2 to e4
e7e8q   Move pawn to e8 and promote to queen
```

### In-game commands

| Command | Action |
|---------|--------|
| `help`  | Show help message |
| `moves` | Show all legal moves for the current player |
| `quit`  | Exit the game |
| `undo`  | Undo the last move |

### Game mode selection

On start, choose from three modes:

1. **Player vs Player** — Two humans take turns
2. **Player vs CPU (play White)** — You play white, AI plays black
3. **CPU vs Player (play Black)** — AI plays white, you play black

---

## How to Play — Textual TUI

The TUI provides a full-screen graphical chess board with mouse and keyboard controls.

### Mouse controls

1. **Click** a piece to select it — legal destinations highlight in green
2. **Click** a highlighted square to move the selected piece
3. **Click** the same piece again to deselect
4. **Click** another own piece to switch selection

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `u` | Undo last move |
| `q` | Quit (prompts to save PGN if moves have been played) |
| `s` | Save PGN file |
| `n` | New game (back to mode selection) |
| `h` / `?` | Show help overlay |
| `Esc` | Deselect current piece / cancel |

### Text input (fallback)

An input bar at the bottom accepts UCI notation (e.g. `e2e4`, `e7e8q`). Press Enter or click **Send** to execute.

### Promotion

When a pawn reaches the last rank, a modal dialog appears to choose the promotion piece (Queen, Rook, Bishop, or Knight).

---

## Features

### Core chess engine

- [x] Standard starting position
- [x] Full legal move generation for all pieces (king, queen, rook, bishop, knight, pawn)
- [x] Check, checkmate, and stalemate detection
- [x] Pawn promotion (with dialog in TUI)
- [x] Castling (kingside and queenside) with full legality checks
- [x] En passant capture
- [x] FIDE draw detection:
  - [x] Insufficient material (K vs K, K+B/K+N vs K, K+B vs K+B same colour)
  - [x] 50-move rule
  - [x] Threefold repetition
- [x] Move history with undo
- [x] PGN export (with save dialog in TUI)
- [x] ANSI coloured board display (CLI)

### AI opponent

- [x] Minimax engine with alpha-beta pruning
- [x] Configurable search depth (default 3)
- [x] Runs in a background thread (TUI) to keep UI responsive

### Interfaces

- [x] Classic scrolling CLI (`python main.py`)
- [x] Textual TUI (`python main.py --tui`)
  - [x] 64 individual clickable square widgets
  - [x] Visual highlights for selection, legal targets, last move, and check
  - [x] Mode selection (PvP, PvCPU, CPUvP)
  - [x] Promotion dialog
  - [x] PGN save dialog (configurable player names and filename)
  - [x] Help overlay
  - [x] Status panel (turn, check, move count)
  - [x] Move history log
  - [x] Notification system (e.g. "Illegal move!", "Move undone.")

---

## Project Structure

```
chess/
  chess_cli/
    __init__.py
    board.py          Board representation, FEN, ANSI display
    pieces.py         Piece, Color, PieceType definitions
    moves.py          Move generation, validation, draw detection
    game.py           Game state, move execution, undo, PGN export
    ai.py             AI engine (minimax + alpha-beta)
    cli.py            Classic CLI interface
    tui.py            Textual TUI application (widgets, handlers, modals)
    tui_styles/
      tui.tcss        TUI stylesheet (dark theme)
  main.py             Entry point (--tui / -t for TUI, else CLI)
  requirements.txt    Dependencies (textual)
  tests/
    conftest.py       Shared pytest fixtures
    test_unit.py      Board, coordinates, moves, game state
    test_adversarial.py  Illegal moves, king safety, edge cases
    test_integration.py  Full games, PGN I/O, CLI, AI
    test_board_ansi.py   ANSI colour display tests
    test_insufficient_material.py  Draw detection tests
    test_draw_rules.py     50-move rule, threefold repetition
    test_tui.py            TUI widget and interaction tests
  README.md
```

---

## Testing

```bash
python -m pytest tests/ -v --tb=short
```

**141 tests** across 8 test files covering:
- Board setup, FEN round-trip, coordinates
- Move generation for all piece types
- Full game scenarios (Scholar's Mate, Fool's Mate, Italian Game)
- En passant, castling (including illegal castling through/out of check)
- AI integration and CPU-vs-CPU games
- ANSI colour output and Windows terminal enablement
- Draw detection (insufficient material, 50-move, threefold)
- TUI widgets, click interactions, text input, keyboard shortcuts
- Undo, PGN export, promotion dialog, notifications

---

## Requirements

- Python 3.10+
- [textual](https://github.com/Textualize/textual) >= 1.0.0 (for TUI mode)
- Rich (installed automatically with textual)
- No other external dependencies

The classic CLI mode works with the Python standard library only.
