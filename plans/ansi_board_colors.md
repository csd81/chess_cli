# Implementation Plan: ANSI Board Colors & Last Move Highlight

Adding ANSI board shading, colored piece letters, and last-move highlights dramatically improves board readability and terminal aesthetics. This allows players to track diagonal movements and locate the opponent's last move instantly.

## 1. Design Decisions

### Coexistence with existing `highlight_squares`
The `display()` method already has a `highlight_squares` parameter used by the `moves <sq>` command (shows `[ ]` / `[P]` brackets on target squares). The new `last_move` parameter is **independent** and additive:

- **`last_move`** → applies a **yellow background** (`BG_LAST_MOVE`) to the from/to squares. This is a background color, applied beneath whatever content is in the cell.
- **`highlight_squares`** → applies `[ ]`/`[P]` **bracket notation** around the content. This is a content change, not a background change.

When both are active (e.g. player types `moves e2` after a move was already made):
- Last-move squares get yellow background + normal content (or `[ ]` brackets if also in `highlight_squares`)
- The yellow background takes visual precedence for tracking the last move, while brackets show legal move destinations

This avoids conflict because one affects the background color and the other affects the text content.

### Dark square color
`\033[42m` (bright green) is too intense. Use a muted 256-color shade instead:

| Square | ANSI Code | Description |
|--------|-----------|-------------|
| Light  | `\033[48;5;255m` | Near-white (255) |
| Dark   | `\033[48;5;95m`  | Warm brown (95) — traditional wooden board feel |
| Last move | `\033[48;5;228m` | Soft yellow (228) — visible but not garish |
| White pieces | `\033[38;5;0m` | Black text (0) — contrasts well on light squares |
| Black pieces | `\033[38;5;255m` | White text (255) — contrasts well on dark squares |

Using 256-color codes provides a more refined look than basic 16-color ANSI while still being widely supported in modern terminals (CMD, Windows Terminal, Git Bash, VS Code terminal).

### Borders and labels
- Board borders (`+---+---+...`) and rank/file labels remain **uncolored** — plain ASCII as-is.
- This avoids complexity and keeps the focus on the board squares themselves.

---

## 2. Code Changes

### A. Define ANSI Codes in `Board` (`chess_cli/board.py`)
Add ANSI color formatting constants above the `Board` class:
```python
# ANSI 256-color codes for board display
BG_LIGHT = "\033[48;5;255m"    # Near-white
BG_DARK = "\033[48;5;95m"      # Warm brown (wooden board feel)
BG_LAST_MOVE = "\033[48;5;228m" # Soft yellow
FG_BLACK_PIECE = "\033[38;5;0m"   # Black text (for white pieces on light)
FG_WHITE_PIECE = "\033[38;5;255m" # White text (for black pieces on dark)
RESET = "\033[0m"
```

### B. Update `Board.display()` (`chess_cli/board.py`)
Modify signature to:
```python
def display(self, reversed_view: bool = True,
            highlight_squares: Optional[List[Position]] = None,
            last_move: Optional[Move] = None) -> str:
```

Logic per square `(r, c)`:
1. **Determine background color**:
   - If `last_move` is set and `(r, c)` matches `last_move.from_pos` or `last_move.to_pos` → use `BG_LAST_MOVE`
   - Else if `(r + c) % 2 == 0` (light square) → use `BG_LIGHT`
   - Else (dark square) → use `BG_DARK`
2. **Determine piece text color**:
   - If the square has a white piece → `FG_BLACK_PIECE` (black text, readable on light/yellow)
   - If the square has a black piece → `FG_WHITE_PIECE` (white text, readable on dark/yellow)
3. **Build cell content** (same logic as before):
   - If `(r, c)` is in `highlight_squares`: `[ ]` for empty, `[P]` for piece
   - Otherwise: `   ` for empty, ` P ` for piece
4. **Assemble**: `background + text_color + cell_content + RESET`
   - Each cell is width 3 (same as before), so `|...|...|...|` alignment is preserved.
5. **Preserve borders**: Borders and labels are plain ASCII, no ANSI codes applied.

### C. Windows ANSI Enablement (`chess_cli/board.py`)
Add a module-level initialization block to enable virtual terminal processing on Windows:
```python
import os
import sys

# Enable ANSI escape sequences on Windows
if os.name == "nt":
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
```

This goes at the top of `board.py` (or `cli.py`) to ensure ANSI codes work in legacy Windows terminals like CMD.

### D. Update CLI Display trigger (`chess_cli/cli.py`)
In `ChessCLI.display()`, pass the last move alongside existing highlight squares:
```python
last_move = self.game.move_history[-1] if self.game.move_history else None
print(self.game.board.display(
    highlight_squares=self.highlighted_squares,
    last_move=last_move
))
```

The existing `self.highlighted_squares` / `self.highlighted_piece` state and reset logic remains unchanged.

---

## 3. Files Modified

| File | Change |
|------|--------|
| `chess_cli/board.py` | Add ANSI constants, Windows enablement, update `display()` signature and cell rendering |
| `chess_cli/cli.py` | Update `display()` call to pass `last_move` from `game.move_history` |

---

## 4. Verification Plan

- **Windows Compatibility**:
  - Run in **CMD**, **Windows Terminal**, and **Git Bash**. Verify colors display properly without raw escape sequences.
  - The `ctypes` enablement handles legacy CMD; modern terminals (Windows Terminal, VS Code) work natively.
- **Color Aesthetics Verification**:
  - Verify light and dark squares alternate in a checkerboard pattern (light = near-white, dark = warm brown).
  - Verify white pieces are readable as dark text on light/yellow backgrounds.
  - Verify black pieces are readable as light text on dark/yellow backgrounds.
- **Move Tracking Verification**:
  - Play `e2e4`. Verify `e2` and `e4` squares turn soft yellow (different from the light/dark pattern).
  - Make a move for Black. Verify yellow highlights shift to Black's move, previous highlights cleared.
- **Coexistence Test**:
  - After making a move, type `moves g1`. Verify last-move squares are still yellow, and `g1` knight's target squares show `[ ]`/`[N]` brackets.
  - Verify the yellow background still shows through behind the bracket notation.
