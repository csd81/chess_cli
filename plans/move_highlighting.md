# Implementation Plan: Move Highlighting

Adding move highlighting lets players query a piece (e.g. `moves e2`) and visually see all its valid destination squares marked directly on the ASCII board display.

## 1. Code Changes

### A. Update `Board.display()` (`chess_cli/board.py`)
Add an optional parameter `highlight_squares: List[Position] = None` to the `display` method:
- While rendering each square at `(row, col)`:
  - Check if `(row, col)` is in `highlight_squares`.
  - If it is, and the square is empty, render it as ` * ` or ` • ` instead of `"   "`.
  - If it contains a piece, render it with brackets like `[P]` or `[p]` instead of `" P "` or `" p "`, or use ANSI escape color codes (e.g., green text background) if the terminal supports it.

### B. Track Highlights in CLI (`chess_cli/cli.py`)
1. Add `self.highlighted_squares = []` to `ChessCLI.__init__()`.
2. Update `display()` to pass `self.highlighted_squares` to `self.game.board.display()`.
3. Clear `self.highlighted_squares` after any successful move is made so highlights don't persist on the next turn.

### C. Handle Highlight Commands (`chess_cli/cli.py`)
Modify how `moves` commands are parsed and processed:
- Allow commands like `moves <square>` (e.g. `moves e2`).
- In `show_legal_moves()`:
  - If a square is specified, look up the piece on that square.
  - Get all legal moves from `self.game.get_legal_moves()`.
  - Filter the moves to only those starting from the specified square.
  - Store the target positions of those filtered moves in `self.highlighted_squares`.
  - Do NOT pause with `input()` if highlighting; instead, immediately redraw the board showing the highlighted targets, allowing the user to type their next move.

## 2. Verification Plan
- Type `moves e2` at the start of the game.
- Verify the board immediately redraws, highlighting `e3` and `e4` with `*` or brackets.
- Verify you can type a move (e.g. `e2e4`) immediately while the highlights are shown.
- Verify that after the move completes, the highlights disappear on the opponent's turn.
