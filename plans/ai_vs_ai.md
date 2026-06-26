# Implementation Plan: AI vs AI Mode (Revised)

## Review of Original Plan
The original plan was conceptually correct but had several gaps:

1. **Integration with existing CPU loop**: The CLI already handles CPU moves via `self.cpu_color` (single-side check:
   `if self.cpu_color is not None and self.game.current_turn == self.cpu_color`). For AI vs AI,
   both sides need auto-play. Simplest approach: add `self.ai_vs_ai` flag and check it alongside
   the existing CPU check.
2. **Per-side AI depth**: Different depths for White vs Black prevent deterministic mirror matches.
   Add `self.ai_depth_white = 3` and `self.ai_depth_black = 3` fields.
3. **Display label**: Add to MODES dict and show on status line.
4. **Auto PGN at end**: Unlike human modes where we prompt, AI vs AI should auto-save with
   descriptive filenames and player names "AI_White" / "AI_Black".
5. **TUI support**: The TUI should also support AI vs AI mode (add to ModeScreen).
6. **Plan missed**: No mention of the `"Press Enter..."` pauses that exist in the CPU loop —
   those must be skipped in AI vs AI mode.

## 1. Goal
Create a spectator mode where two AI instances play a complete game of chess against each other.
The game auto-executes moves with a short delay so the user can watch, ending with auto-PGN export.
Available in both CLI and TUI.

## 2. CLI Updates (`chess_cli/cli.py`)

### 2.1 MODES dict
```python
MODES = {1: "PvP", 2: "PvCPU", 3: "CPUvP", 4: "AI vs AI"}
```
The display line `f"=== CHESS CLI [{mode_name}] ==="` already uses this dict.

### 2.2 State tracking
```python
self.ai_vs_ai = False
self.ai_depth_white = 3
self.ai_depth_black = 3
```

### 2.3 Mode selection
Add option 4 to the startup prompt. When selected, set `self.ai_vs_ai = True`.
No need to set `self.cpu_color` (it stays None, but the AI-vs-AI flag takes precedence).

### 2.4 Run loop logic
The loop currently has:
```python
if self.cpu_color is not None and self.game.current_turn == self.cpu_color:
    # CPU turn: auto-compute
```
Change to:
```python
is_ai_turn = self.ai_vs_ai or (self.cpu_color is not None and self.game.current_turn == self.cpu_color)
if is_ai_turn:
    # auto-compute (determine depth based on who plays)
```
- In AI vs AI: `self.ai_vs_ai` is True, so every turn is an AI turn.
- Remove the `"Press Enter to continue..."` and `input()` calls for AI moves in AI vs AI mode.
- Use `time.sleep(1.0)` between AI moves in AI vs AI so the user can watch.

### 2.5 End-of-game auto-save
When `self.ai_vs_ai` is True and the game ends:
- Auto-save PGN with player names "AI White" / "AI Black" and timestamped filename.
- Display the final board with the result message.
- Show "Press Enter to exit..." (final pause before returning).

## 3. TUI Updates (`chess_cli/tui.py`)

### 3.1 ModeScreen
Add a 4th button: `Button("AI vs AI (Spectator)", id="aivai")` and update the mapping:
```python
mapping = {"pvp": 1, "pvcpu": 2, "cpuvp": 3, "aivai": 4}
```
In `_on_mode_selected`, handle choice 4 by setting `self.cpu_color` to None but adding an
`self.ai_vs_ai = True` flag. The existing CPU worker `_maybe_run_cpu` only triggers when
`current_turn == cpu_color`. For AI vs AI, both turns need CPU — so add a separate method
`_maybe_run_ai_vs_ai` that runs after every move.

### 3.2 AI vs AI flow in TUI
When `self.ai_vs_ai` is True:
- After each move (both by white and black), call `_run_ai_vs_ai_turn()` which:
  - Adds a small delay (0.5s)
  - Gets the best move for the current turn
  - Executes it
  - Refreshes board
  - Recurses unless game is over

## 4. Implementation Steps
1. Update `chess_cli/cli.py`:
   - Add option 4 to `_select_mode()`
   - Add `self.ai_vs_ai`, `self.ai_depth_white`, `self.ai_depth_black` fields
   - Update `__init__` and `run()` loop
   - Auto-save PGN at end
2. Update `chess_cli/tui.py`:
   - Add `self.ai_vs_ai` flag and 4th button to ModeScreen
   - Add `_maybe_run_ai_vs_ai()` method triggered after every move
3. Update `tests/test_integration.py`:
   - Add a test that starts AI vs AI and verifies it produces a complete game
   - Add a test for the CLI mode selection parsing

## 5. Files Modified
- `chess_cli/cli.py` — Mode selection, loop logic, auto-save
- `chess_cli/tui.py` — ModeScreen button, ai_vs_ai flow
- `tests/test_integration.py` — AI vs AI integration test
