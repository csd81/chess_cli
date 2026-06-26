# Implementation Plan: Interactive TUI Mode

This plan outlines the migration from a scrolling, prompt-based CLI to a rich, full-screen Terminal User Interface (TUI) using the `textual` Python framework.

## 1. Design Principles

### Keep the existing CLI untouched
The classic CLI (`cli.py`) remains fully functional. The TUI is a **separate entry point** that reuses the same `Game`, `Board`, `Move`, and `AI` modules. No changes to the core engine.

### Event-driven, not loop-driven
The current CLI uses `while True` + blocking `input()`. The TUI uses Textual's async message/event system. The `Game` object is shared state that the TUI reads after each mutation.

### Widget-per-square for click interaction
Wrapping the board in a `Static` with ANSI text would prevent per-square click detection. Instead, use a `Grid` layout with 64 individual `Button`-like widgets. This enables:
- Click a square to select a piece
- Click a target square to move
- CSS class toggling for highlights (selected, legal targets, last move)

---

## 2. New Dependencies

Add to `requirements.txt`:
```
textual>=1.0.0
```

`textual` depends on `rich` which is installed automatically. No other new dependencies.

---

## 3. Architecture

```
main.py --[--tui]--> chess_cli/tui.py :: ChessApp
main.py --[no flag]--> chess_cli/cli.py :: ChessCLI (existing)
```

Files:
| File | Change |
|------|--------|
| `chess_cli/tui.py` | **NEW** — `ChessApp(App)`, widgets, event handlers |
| `chess_cli/board.py` | Add `SQUARE_COLORS` dict mapping (r+c)%2 to CSS class names (no functional change) |
| `main.py` | Add `--tui` / `-t` argparse flag |
| `requirements.txt` | Append `textual>=1.0.0` |

---

## 4. UI Layout & Widgets

### 4.1 Layout Structure

```
+---------------------------------------------------+
|  Header: Chess TUI  |  Mode: PvP                  |
+---------------------------+-----------------------+
|                           |  Status Panel         |
|   8 x 8 Chess Board       |  - Turn: White        |
|   (Grid of 64 Square     |  - Check: No          |
|    widgets)               |  - Moves: 12          |
|                           |                       |
|                           |  Move History          |
|                           |   1. e4    e5         |
|                           |   2. Nf3   Nc6        |
|                           |                       |
+---------------------------+-----------------------+
|  Command: [e2e4]                        [Send]   |
|  [Q]uit [U]ndo [S]ave PGN [N]ew Game            |
+---------------------------------------------------+
```

### 4.2 Widget Hierarchy

```
ChessApp(App)
 +-- Header(Static)          — Title bar: "Chess TUI [PvP]"
 +-- Horizontal
      +-- BoardContainer     — CSS-styled container
      |    +-- BoardLabel    — "    a   b   c   d   e   f   g   h"
      |    +-- BoardGrid(Grid) — 8x8 grid of Square widgets
      |         +-- Square(r0c0) ... Square(r7c7)
      |    +-- BoardLabel    — "    a   b   c   d   e   f   g   h"
      +-- Sidebar(Vertical)
           +-- StatusPanel  — Turn, check, game-over messages
           +-- MoveLog(Static) — Scrollable move list
 +-- InputContainer(Horizontal)
      +-- MoveInput(Input)   — UCI text input fallback
      +-- SendButton(Button) — "Send"
 +-- Footer(Static)          — Key bindings help
 +-- ModeScreen(Screen)      — Modal for game mode selection (first launch)
 +-- PromotionDialog(Screen) — Modal for promotion piece choice
 +-- SaveDialog(Screen)      — Modal for PGN filename entry
```

### 4.3 Square Widget

Each `Square` is a custom `Button`-like widget that:
- Displays the piece character (or empty) as content
- Has CSS classes toggled for visual state:
  - `.light` / `.dark` — checkerboard background color
  - `.selected` — brighter border when piece is selected
  - `.legal-target` — dot/outline when showing legal moves
  - `.last-move` — yellow background for last move from/to squares
  - `.check` — red glow when king is in check

CSS example:
```css
Square {
    width: 5;
    height: 3;
    border: solid $surface;
    content-align: center middle;
}
Square.light { background: #f0d9b5; }
Square.dark { background: #b58863; }
Square.selected { border: solid yellow; }
Square.legal-target { background: #aaffaa 30%; }
Square.last-move { background: #ffd; }
Square.check { background: #ff4444; }
```

Square dimensions: width 5, height 3. This gives enough room for the piece character (centered) and visual borders. At this size the full board is about 40 chars wide + padding, fitting most terminals.

---

## 5. Interaction Model

### 5.1 Mouse Click (Primary)

Two-click sequence:
1. **Click square** → if it has a piece belonging to current player → select it, show legal targets
2. **Click target square** → if it's a legal destination → make the move
3. **Click same piece again** → deselect
4. **Click another own piece** → switch selection

Implementation:
```python
def on_square_clicked(self, event: Square.Clicked) -> None:
    pos = event.square.pos
    piece = self.game.board.get_piece(*pos)
    
    if self.selected_pos is None:
        # Select piece
        if piece and piece.color == self.game.current_turn:
            self.selected_pos = pos
            self.legal_targets = [m.to_pos for m in self.game.get_legal_moves()
                                  if m.from_pos == pos]
            self.refresh_board()
    else:
        # Try to move
        if pos in self.legal_targets:
            # Handle promotion
            target_piece = self.game.board.get_piece(*pos)
            if (piece and piece.piece_type == PieceType.PAWN and
                    pos[0] in (0, 7)):
                self._pending_promotion = (self.selected_pos, pos)
                self.push_screen(PromotionDialog(self.game.current_turn))
                return
            success = self.game.make_move(self.selected_pos, pos)
        elif pos == self.selected_pos:
            # Deselect
            self.selected_pos = None
            self.legal_targets = []
        else:
            # Try selecting a different piece
            if piece and piece.color == self.game.current_turn:
                self.selected_pos = pos
                self.legal_targets = [m.to_pos for m in self.game.get_legal_moves()
                                      if m.from_pos == pos]
            else:
                self.selected_pos = None
                self.legal_targets = []
        self.refresh_board()
        self._check_game_over()
```

### 5.2 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `u` / `U` | Undo last move |
| `q` / `Q` | Quit (with PGN save prompt if moves exist) |
| `s` / `S` | Save PGN (with filename dialog) |
| `n` / `N` | New game (back to mode selection) |
| `h` / `H` / `?` | Show help overlay |
| Escape | Deselect current piece / cancel dialog |
| Tab | Focus move input |

Key bindings in Textual:
```python
BINDINGS = [
    Binding("u", "undo", "Undo"),
    Binding("q", "quit", "Quit"),
    Binding("s", "save_pgn", "Save PGN"),
    Binding("n", "new_game", "New Game"),
    Binding("h,?", "show_help", "Help"),
]
```

### 5.3 Text Input (Fallback)

An `Input` widget at the bottom allows UCI text entry (e.g., `e2e4`, `e7e8q`). User types and presses Enter. Validation reuses the existing `Game.make_move()` path. Error feedback shown as a temporary notification.

### 5.4 Promotion Dialog

When a pawn reaches the promotion rank, show a modal `Screen` with 4 buttons: Queen, Rook, Bishop, Knight. On click, complete the move with the chosen promotion type.

```python
class PromotionDialog(Screen):
    """Modal dialog to choose promotion piece."""
    
    def compose(self) -> ComposeResult:
        yield Grid(
            Button("Queen", variant="primary", id="queen"),
            Button("Rook", id="rook"),
            Button("Bishop", id="bishop"),
            Button("Knight", id="knight"),
            id="promo-grid",
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)
```

### 5.5 Game Mode Selection

On first launch (or "New Game"), show a `Screen` with three choices (same as classic CLI):
- Player vs Player
- Player vs CPU (play White)
- CPU vs Player (play Black)

Selection stored in `self.cpu_color` (same field as `ChessCLI`).

### 5.6 PGN Save Dialog

When triggered (via `s` key or quit prompt), show a `Screen` with:
- White name input
- Black name input
- Filename input
- Save / Cancel buttons

---

## 6. CPU / AI Integration

The AI `get_best_move()` is synchronous and can take 0.5–3 seconds at depth 3. Use Textual's `@work(exclusive=True)` to run it in a worker thread so the UI stays responsive:

```python
@work(exclusive=True, thread=True)
async def _run_cpu_move(self) -> None:
    self._cpu_thinking = True
    self.refresh_status("CPU is thinking...")
    move = await work_thread(get_best_move, ...)
    self._cpu_thinking = False
    if move:
        self.game.make_move_from_move(move)
        self.refresh_board()
        self._check_game_over()
    if not self.game.game_over:
        self._reset_selection()
```

On CPU turn start:
1. Disable input (prevent double-move)
2. Show "CPU thinking..." in status
3. Fire worker
4. Worker callback re-enables input and refreshes

---

## 7. Implementation Steps (Ordered)

### Step 1: Install textual and create boilerplate
- `pip install textual`
- Create `chess_cli/tui.py` with empty `ChessApp(App)` class
- Wire `main.py --tui` flag

### Step 2: Build Square widget and BoardGrid
- Define `Square(Button)` with CSS classes for light/dark
- Define `BoardGrid` composing 64 squares in an 8×8 `Grid`
- Render pieces from `Game.board.grid`

### Step 3: Click-to-move interaction
- Implement `on_square_clicked` message handler
- Selection tracking (`selected_pos`, `legal_targets`)
- Visual highlighting via CSS class toggling
- Move execution and board refresh

### Step 4: Sidebar (Status + Move History)
- `StatusPanel(Static)` showing turn, check status, game-over message
- `MoveLog(Static)` showing scrollable move list
- Both update on `refresh_board()`

### Step 5: Keyboard shortcuts
- Bind `u` (undo), `q` (quit), `s` (save PGN), `n` (new game)
- Wire to game actions with refresh

### Step 6: Promotion dialog
- `PromotionDialog(Screen)` modal
- Complete the pending pawn move with chosen promotion

### Step 7: Game mode selection screen
- `ModeScreen(Screen)` with 3 buttons
- Set `self.cpu_color` based on choice

### Step 8: CPU async worker
- `@work` decorator for AI computation
- Disable input during CPU turn
- Auto-trigger on CPU turn after human move

### Step 9: PGN save dialog
- `SaveDialog(Screen)` with name/filename inputs
- Write PGN file on confirmation

### Step 10: Footer and polish
- Footer showing key bindings
- Help overlay screen
- Error messages (invalid move) as temporary notifications
- Last-move highlighting on board
- Check square highlighting (red glow on king)

---

## 8. CSS File

Create `chess_cli/tui.tcss` with all styles. Keeping CSS separate from Python follows Textual best practices.

Key sections:
- Screen background and layout containers
- Square widget (.light, .dark, .selected, .legal-target, .last-move, .check)
- Sidebar and status styles
- Input and button styles
- Modal dialog styling
- Footer text

---

## 9. Testing

### `tests/test_tui.py` (new)

Core widget tests (using `textual`'s `pilot` testing API):

- **`test_board_renders_32_pieces`**: Verify 64 Square widgets exist, 32 have piece content.
- **`test_click_selects_piece`**: Click e2, verify that square has `.selected` class.
- **`test_click_shows_legal_targets`**: Click e2, verify e4 has `.legal-target` class.
- **`test_click_to_move`**: Click e2 then e4, verify pawn moved.
- **`test_undo`**: Make a move, press `u`, verify board reverts.
- **`test_cpu_mode_triggers_ai`**: Start in CPU mode, make a move, verify AI responds.
- **`test_game_over_message`**: Play Scholar's Mate, verify checkmate message shown.
- **`test_threefold_draw_detected`**: Play knight shuffle three times, verify draw message.
- **`test_promotion_dialog_appears`**: Set up pawn on 7th rank, push it, verify dialog.
- **`test_promotion_queen`**: Push pawn, select queen in dialog, verify promotion.
- **`test_mode_screen_shows`**: On new game, verify mode selection screen appears.
- **`test_text_input_move`**: Type `e2e4` in Input widget, press Enter, verify move executed.

---

## 10. Verification Plan

- **Windows Terminal**: Run `python main.py --tui`, verify colors and layout render correctly.
- **Resize**: Shrink terminal to 80×24 minimum. Verify board still fits (scroll or scale).
- **Click flow**: Click a piece, verify highlighting, click target, verify move.
- **Keyboard**: Press `u` to undo, `s` to save, `q` to quit.
- **Promotion**: Set up a promotion scenario, verify dialog appears.
- **CPU**: Play vs CPU, verify AI thinks and responds without UI freeze.
- **Full game**: Play a complete game to checkmate, verify end message.
- **Draw**: Force a stalemate, insufficient material, 50-move, and threefold draw — verify each message.
- **Mixed input**: Use both mouse clicks and text input interchangeably.
- **Regression**: Run `python -m pytest tests/ -v` to confirm all 116 existing tests still pass.
