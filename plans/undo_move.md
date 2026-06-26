# Implementation Plan: Undo Move

Adding an `undo` command allows players to take back their last move. Since the game maintains a move history, we can reverse the state changes step-by-step.

## 1. Code Changes

### A. Update `Move` Dataclass (`chess_cli/moves.py`)
To properly revert `has_moved` flags on pieces, we need to record if the piece had already moved prior to this turn.
- Add `piece_had_moved: bool = False` to the `Move` dataclass.
- Update move generation to capture this state when creating `Move` instances.

### B. Add Reversion Logic in `Game` (`chess_cli/game.py`)
Implement the `undo_move(self) -> bool` method on the `Game` class:
1. **Check History**: If `self.move_history` is empty, return `False`.
2. **Pop Move**: Pop the last `move` from `self.move_history`.
3. **Revert Piece Position**: Move the piece from `move.to_pos` back to `move.from_pos`.
4. **Revert `has_moved` Flag**: Set `move.piece.has_moved = move.piece_had_moved`.
5. **Restore Captures**:
   - For standard captures: Put `move.captured` back on `move.to_pos`.
   - For en passant: Place `move.captured` (the pawn) back on its original square `(move.from_pos[0], move.to_pos[1])`.
6. **Revert Castling**:
   - If `move.is_castle` is True, locate the corresponding rook that was moved and move it back to its corner file (`0` or `7`), resetting its `has_moved` status to `False`.
7. **Switch Turn**: Set `self.current_turn = self.current_turn.opponent()`.
8. **Reset Game Over States**: Set `self.game_over = False` and `self.winner = None`.
9. **Update En Passant Target**: Re-calculate or restore the previous en passant target if the preceding move in history was a pawn double-step.
10. Return `True`.

### C. Update CLI Command Processing (`chess_cli/cli.py`)
- In `parse_move()`, recognize `"undo"` or `"u"` as valid commands.
- In `run()`, when `undo` is entered:
  ```python
  if result == "undo":
      if self.game.undo_move():
          print("Move undone.")
      else:
          print("No moves to undo!")
      continue
  ```

## 2. Verification Plan
- Start a game and make a few moves.
- Enter `undo` and verify the board returns to the previous state.
- Test capturing a piece, undoing, and verifying the captured piece is restored to the correct square.
- Test castling, undoing, and verifying both the king and rook return to their starting positions.
- Test pawn promotion, undoing, and verifying it turns back into a pawn.
