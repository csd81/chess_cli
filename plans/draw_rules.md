# Implementation Plan: Draw Detection (Fifty-Move Rule & Threefold Repetition)

This plan outlines implementing the remaining official FIDE draw rules: the Fifty-Move Rule (50 consecutive moves without a pawn move or capture) and Threefold Repetition (the exact same board position occurring three times).

## 1. Design Decisions

### Single source of truth for draw reasons
The existing code already has a `self.draw_reason: str` field on `Game` (used by insufficient material). New draw types should set this field consistently:
- `"50-move rule"` — 100 half-moves without pawn move or capture
- `"threefold repetition"` — same position appears 3 times
- `"stalemate"` — existing
- `"insufficient material"` — existing

The CLI `display()` method already reads `draw_reason` — it just needs new `elif` branches.

### Position key definition
Threefold repetition considers: piece placement + current turn + castling rights + en passant target. This is the FIDE standard (note: en passant target matters because it affects whether en passant capture is possible). The key is derived after the move is executed (i.e., the resulting position, not the pre-move position).

### Threefold repetition — any occurrence, not consecutive
FIDE rules count any 3 occurrences of the same position throughout the game (not just consecutive ones). A `dict[str, int]` counting all occurrences is correct. The position is recorded *after each move*, so the check `count >= 3` triggers on the third time a position appears.

## 2. Code Changes

### A. Track State in `Game` (`chess_cli/game.py`)

In `Game.__init__()`:
```python
self.halfmove_clock: int = 0  # Consecutive half-moves without pawn move or capture
self.position_history: dict[str, int] = {}  # position key -> occurrence count
```

### B. Generate Position Keys (`chess_cli/game.py`)

Add a helper method to uniquely fingerprint the current board state:

```python
def _get_position_key(self) -> str:
    fen = self.board.to_fen()
    turn = self.current_turn.value
    # Castling rights: encode as KQkq string
    castling = ""
    for color in [Color.WHITE, Color.BLACK]:
        rights = self.castling_rights[color]
        sym = "K" if color == Color.WHITE else "k"
        q_sym = "Q" if color == Color.WHITE else "q"
        if rights["kingside"]: castling += sym
        if rights["queenside"]: castling += q_sym
    if not castling:
        castling = "-"
    # En passant target
    ep = pos_to_algebraic(self.en_passant_target) if self.en_passant_target else "-"
    return f"{fen} {turn} {castling} {ep}"
```

### C. Update `_execute_move()` (`chess_cli/game.py`)

After the move is fully executed (board updated, castling rook moved, promotion resolved, current_turn switched):

1. **Update half-move clock**:
   ```python
   if move.piece.piece_type == PieceType.PAWN or move.captured is not None:
       self.halfmove_clock = 0
   else:
       self.halfmove_clock += 1
   ```

2. **Record position in history**:
   ```python
   key = self._get_position_key()
   self.position_history[key] = self.position_history.get(key, 0) + 1
   ```

3. **Check draw conditions** (after the existing stalemate/insufficient-material elif chain):
   ```python
   elif self.halfmove_clock >= 100:
       self.game_over = True
       self.winner = None
       self.draw_reason = "50-move rule"
   elif self.position_history.get(self._get_position_key(), 0) >= 3:
       self.game_over = True
       self.winner = None
       self.draw_reason = "threefold repetition"
   ```
   
   Note: check 50-move rule *before* threefold repetition since it takes priority. The `self._get_position_key()` is called again here because `self.current_turn` has already been switched, and the `position_history` dict was already updated — so `count >= 3` reflects the just-recorded position.

### D. Update `undo_move()` (`chess_cli/game.py`)

Undo must reverse draw-related state:

```python
# Record state before popping (for undo of halfmove clock)
move = self.move_history[-1]  # peek

# Track previous clock for restoration (simplest approach: recalculate from last move)
if move.piece.piece_type == PieceType.PAWN or move.captured is not None:
    # The undone move reset the clock — need to restore previous value
    # Walk backwards through history to find the last pawn move or capture
    prev_clock = 0
    for i in range(len(self.move_history) - 2, -1, -1):
        m = self.move_history[i]
        if m.piece.piece_type == PieceType.PAWN or m.captured is not None:
            break
        prev_clock += 1
    self.halfmove_clock = prev_clock
else:
    # The undone move incremented the clock — just decrement
    self.halfmove_clock = max(0, self.halfmove_clock - 1)

# Decrement or remove the position that's being undone (current position before undo)
current_key = self._get_position_key()
if current_key in self.position_history:
    self.position_history[current_key] -= 1
    if self.position_history[current_key] <= 0:
        del self.position_history[current_key]
```

Place this after switching `current_turn` back and before recalculating en passant.

### E. Update CLI UI (`chess_cli/cli.py`)

Extend the existing draw message chain in `display()`:

```python
if self.game.game_over:
    if self.game.winner:
        print(f"Checkmate! {self.game.winner.value.capitalize()} wins!")
    elif self.game.draw_reason == "insufficient material":
        print("Draw! Insufficient material.")
    elif self.game.draw_reason == "50-move rule":
        print("Draw by 50-move rule!")
    elif self.game.draw_reason == "threefold repetition":
        print("Draw by threefold repetition!")
    else:
        print("Stalemate! The game is a draw.")
```

---

## 3. Files Modified

| File | Change |
|------|--------|
| `chess_cli/game.py` | Add `halfmove_clock`, `position_history`, `_get_position_key()`, update `_execute_move()`, update `undo_move()` |
| `chess_cli/cli.py` | Extend draw message chain with 50-move and threefold repetition branches |

---

## 4. Tests

### `tests/test_draw_rules.py`

#### Fifty-Move Rule Tests

- **`test_halfmove_clock_resets_on_pawn_move`**: Make a pawn move, verify clock resets to 0.
- **`test_halfmove_clock_resets_on_capture`**: Make a non-pawn capture, verify clock resets.
- **`test_halfmove_clock_increments`**: Make a non-pawn, non-capture move, verify clock increments.
- **`test_fifty_move_draw_triggered`**: Set `halfmove_clock = 99` on a game (via direct field access), make a non-pawn non-capture move, verify `game_over`, `winner is None`, `draw_reason == "50-move rule"`.
- **`test_fifty_move_not_triggered_at_99`**: Set clock to 99, must not trigger before the 100th half-move.
- **`test_fifty_move_undo_restores_clock`**: Reach 50-move draw, undo, verify clock is restored and game is no longer over.

#### Threefold Repetition Tests

- **`test_threefold_repetition_triggered`**: Construct a Game, play a sequence that repeats a position 3 times (e.g. Nf3 Ng1 Nf3 Ng1 Nf3 Ng1), verify the game ends on the third repetition with `draw_reason == "threefold repetition"`.
- **`test_threefold_non_consecutive`**: Play knight shuffle, play other moves in between, then return to the original position a third time. Verify draw triggers.
- **`test_threefold_not_triggered_at_two`**: Repeat a position only twice, verify game is not over.
- **`test_threefold_undo_restores_count`**: Repeat 3 times, undo one move, verify the game is no longer over.

#### Integration Tests

- **`test_pgn_result_draw`**: Game ending in 50-move draw exports `"1/2-1/2"` in PGN.
- **`test_all_draw_types_work_together`**: Verify stalemate, insufficient material, 50-move, and threefold can all trigger independently without interfering.
