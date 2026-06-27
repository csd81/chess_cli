# Implementation Plan: Universal Chess Interface (UCI)

This plan outlines how to make your chess engine speak the **UCI Protocol**. UCI is the universal text-based language that all professional chess GUIs (like Arena, CuteChess, and Chessbase) use to communicate with engines like Stockfish. By implementing this, you can plug your custom Python engine into these professional tools and run automated tournaments.

## 1. The Concept
UCI is entirely text-based. The GUI sends commands via Standard Input (`stdin`), and your engine replies via Standard Output (`stdout`).
We will create a new entry point that runs an infinite loop, constantly listening for these text commands and responding appropriately.

## 2. Core Architecture

Create a new file: `chess_cli/uci.py`.

```python
import sys
from chess_cli.game import Game
from chess_cli.ai import get_best_move

def uci_loop():
    game = Game()
    
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            continue
            
        tokens = line.split(" ")
        command = tokens[0]
        
        if command == "uci":
            print("id name ChessCLI Engine")
            print("id author You")
            print("uciok")
            sys.stdout.flush()
            
        elif command == "isready":
            print("readyok")
            sys.stdout.flush()
            
        elif command == "ucinewgame":
            game = Game()
            
        elif command == "position":
            # Handle board setup
            handle_position(game, tokens[1:])
            
        elif command == "go":
            # Handle AI thinking
            handle_go(game, tokens[1:])
            
        elif command == "quit":
            break
```

## 3. Implementing the Complex Commands

### A. The `position` Command
The GUI will send the board state in one of two ways:
1. `position startpos moves e2e4 e7e5 g1f3`
2. `position fen <fen_string> moves e2e4 e7e5`

You need to write `handle_position(game, args)` to:
1. Reset the board to `startpos` or parse the `<fen_string>` using the FEN importer you just built.
2. If the word `moves` is in the arguments, iterate through all the moves following it.
3. For each move string (e.g., `"e2e4"`), translate it into your internal `Move` object and apply it to the `Game` state so the internal board matches the GUI's board.

### B. The `go` Command
The GUI tells the engine to calculate the next move. It usually passes time controls (e.g., `go wtime 300000 btime 300000 winc 0 binc 0`).
You need to write `handle_go(game, args)` to:
1. Parse the time constraints (optional but recommended: figure out how much time the AI should spend on this move based on `wtime` / `btime`).
2. Call your existing AI: `best_move = get_best_move(game.board, game.current_turn, time_limit=...)`
3. Print the result back to the GUI in pure coordinate notation:
   `print(f"bestmove {best_move.to_uci_string()}")`
   *(Note: You'll need a helper method on your `Move` class to convert it to a UCI string like `"e2e4"` or `"e7e8q"` for promotion).*

## 4. Integration
Update `main.py` so that if it is launched with a flag (e.g., `python main.py --uci`), it bypasses the human TUI/CLI and directly launches `uci.py`'s `uci_loop()`.

## 5. Implementation Steps
1. **Move Converter**: Add a `.to_uci()` and `.from_uci()` helper to your `Move` class.
2. **The UCI Loop**: Implement `chess_cli/uci.py` with the boilerplate above.
3. **Handle Position**: Write the logic to apply a list of coordinate moves to the board.
4. **Testing**: Download a free GUI like **Arena Chess GUI** or **En Croissant**, point it to your `main.py --uci` script, and watch your engine play against itself or Stockfish on a beautiful graphical board!

---

## Implementation Status: COMPLETED

The UCI protocol implementation is complete and tested.

### What was implemented
- **`chess_cli/uci.py`** — Full UCI loop with all required commands:
  - `uci` handshake with engine identification
  - `isready` / `readyok` ping-pong
  - `ucinewgame` with transposition table clearing
  - `position startpos` and `position fen` with move application
  - `go` with time management (wtime/btime/winc/binc/movestogo/depth)
  - `stop`, `ponderhit`, `quit`, `debug`, `setoption`
  - Time management: 40-move expectation, 80% of increment, 30s per move cap, 100ms overhead reserve
- **`game.py`** — Added `make_move_from_uci()` method for applying UCI move strings
- **`main.py`** — Added `--uci` flag entry point
- **`tests/test_uci.py`** — 21 tests across 5 test classes covering all UCI functionality

### Files modified
- `chess_cli/uci.py` (new, ~225 lines)
- `tests/test_uci.py` (new, ~214 lines)
- `chess_cli/game.py` (added `make_move_from_uci`)
- `main.py` (added `--uci` argument)

### Test results
- All 21 UCI tests pass
- Full test suite: 234 tests pass in 22.79s
