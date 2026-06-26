# Implementation Plan: Insufficient Material Draw Detection

Adding insufficient material detection ensures the game correctly recognizes draw positions where checkmate is impossible (K vs K, K+B vs K, K+N vs K, K+B vs K+B same color). This is a standard FIDE rule.

## 1. Code Changes

### A. Add is_insufficient_material() to chess_cli/moves.py

New function that checks the board for positions with insufficient material:
- King vs King: No other pieces on the board.
- King + Bishop vs King or King + Knight vs King: One side has only a king, the other has a king plus a single bishop or knight.
- King + Bishop vs King + Bishop (same color): Both sides have only a bishop, and both bishops occupy the same square color.
- All other cases (pawns, rooks, queens, multiple pieces, two knights, opposite-color bishops) are considered sufficient material.

Logic:
1. Iterate through all pieces on the board via board.get_all_pieces().
2. Collect non-king piece types for each color.
3. If either side has a pawn, rook, queen, or >=2 minor pieces -> return False.
4. Apply the specific insufficient material patterns above.

### B. Update chess_cli/game.py

- Import is_insufficient_material from moves.
- Add self.draw_reason: str = "" field to Game.__init__().
- In _execute_move(), after stalemate check, add check for insufficient material.
- In undo_move(), reset self.draw_reason to empty.
- PGN export already handles winner is None as 1/2-1/2.

### C. Update chess_cli/cli.py

In display(), update the draw message to show the reason.

## 2. Files Modified

- chess_cli/moves.py: Add is_insufficient_material(board) function
- chess_cli/game.py: Import, draw_reason field, check in _execute_move(), reset in undo_move()
- chess_cli/cli.py: Draw message distinguishes insufficient material from stalemate

## 3. Tests (tests/test_insufficient_material.py)

Test cases:
- King vs King
- King + Bishop vs King
- King + Knight vs King
- King + Bishop vs King + Bishop (same color)
- King + Bishop vs King + Bishop (diff color) -> sufficient
- Sufficient with pawn, rook, queen
- Sufficient with two knights
- Full starting position -> sufficient
- Game detects draw via K vs K endgame
- Undo after insufficient material
- PGN result is 1/2-1/2 for insufficient material draw
