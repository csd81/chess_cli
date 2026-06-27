# Implementation Plan: FEN Import & Puzzle Mode

This plan outlines how to add the ability to start a game from any custom board state using Forsyth-Edwards Notation (FEN). This is incredibly useful for testing the AI on specific endgames or setting up "Mate-in-3" puzzles.

## 1. Goal
Currently, the game always starts from the standard initial chess position. We want to allow the user to pass a FEN string (e.g., `8/8/8/4k3/8/8/4K3/8 w - - 0 1` for King vs King) to jump straight into a specific scenario.

## 2. Code Changes

### A. Full FEN Parsing (`chess_cli/board.py` & `game.py`)
You likely already have a basic `Board.from_fen()` that parses the piece placements. However, a full FEN string contains 6 parts separated by spaces. We need to parse all of them to accurately set up the `Game` state.

Example FEN: `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`
1. **Piece Placement**: Keep using `Board.from_fen()`.
2. **Active Color**: `w` or `b`. This must update `self.current_turn` in `game.py`.
3. **Castling Availability**: `KQkq` (White Kingside/Queenside, Black Kingside/Queenside). Update `self.castling_rights`.
4. **En Passant Target**: e.g., `e3` or `-`. Update `self.en_passant_target`.
5. **Halfmove Clock**: Number of halfmoves since the last capture or pawn advance. Update `self.halfmove_clock`.
6. **Fullmove Number**: The current turn number. (Optional: useful for PGN export).

*Update `Game.__init__`:*
Modify the constructor to accept an optional FEN string:
```python
def __init__(self, fen: str = None):
    if fen:
        parts = fen.split(" ")
        self.board = Board.from_fen(parts[0])
        self.current_turn = Color.WHITE if parts[1] == 'w' else Color.BLACK
        # ... parse castling, en passant, and clocks ...
    else:
        self.board = Board()
        self.current_turn = Color.WHITE
        # ... standard initialization ...
```

### B. Command-Line Arguments (`main.py` / `cli.py`)
We want the user to be able to launch the app directly into a FEN state from their terminal.

Use Python's built-in `argparse` in `main.py`:
```python
import argparse
from chess_cli.cli import play

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terminal Chess CLI")
    parser.add_argument("--fen", type=str, help="Start the game from a custom FEN string")
    args = parser.parse_args()
    
    # Pass the FEN to the CLI runner
    play(fen=args.fen)
```

### C. Interactive Menu Fallback
If the user starts the game normally without arguments, add an option to the main menu:
`5. Load Custom FEN (Puzzle Mode)`
If they select this, prompt them to paste the FEN string.

### D. Web App Support (Optional but Recommended)
If you are using the FastAPI web server, add a new endpoint:
`POST /api/load_fen` which accepts `{"fen": "..."}` and resets the global game state to that FEN.

## 3. Implementation Steps
1. **Update `Game.__init__`**: Safely parse all 6 parts of the FEN string, falling back to defaults if the user provides a partial FEN.
2. **CLI Integration**: Add `argparse` to `main.py` and the interactive menu option in `cli.py`.
3. **Validation Test**: Start the app with `--fen "8/8/8/4k3/8/8/4K3/8 w - - 0 1"`. Verify that the board only shows two Kings and instantly triggers the "Insufficient Material" draw rule we implemented earlier.

## Implementation Status: COMPLETED
