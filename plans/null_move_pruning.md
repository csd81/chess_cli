# Implementation Plan: Null Move Pruning

This plan outlines how to add **Null Move Pruning** to the Alpha-Beta search. This advanced technique dramatically reduces the number of positions the AI has to calculate by assuming that any valid chess move is better than skipping a turn.

## 1. The Concept
In most chess positions, doing *something* is better than doing *nothing* (except in "Zugzwang" endgames). 
Therefore, if we allow the AI to temporarily "skip" its turn (a Null Move) in the simulation, and the resulting board state *still* looks overwhelmingly winning for us (causing a Beta cutoff), then we can safely assume that making a *real* move would be just as good or better. We can prune the entire branch immediately without calculating any actual moves!

## 2. When NOT to use it
We cannot skip a turn if:
1. **We are in check**: We must respond to checks.
2. **We are in Zugzwang**: In pawn endgames, skipping a turn is sometimes an advantage. If we only have pawns and our King left on the board, we skip Null Move Pruning to avoid blundering endgames.
3. **Depth is too low**: Null moves reduce the search depth by a factor of `R` (usually `R = 2`). If `depth < 3`, we don't have enough depth to do a Null Move Search.

## 3. Code Changes (`chess_cli/ai.py`)

### A. Add Zugzwang Risk Detection
Create a helper function to check if the current player only has Pawns and a King left.
```python
def _has_non_pawn_material(board: Board, color: Color) -> bool:
    """Returns True if the player has pieces other than Pawns and Kings."""
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p and p.color == color and p.piece_type not in (PieceType.PAWN, PieceType.KING):
                return True
    return False
```

### B. Add the Null Move Logic
At the very top of `_minimax` (after checking for checkmate/stalemate and transposition tables, but *before* generating legal moves), insert the Null Move Search.

```python
    # Ensure depth is sufficient and R factor is defined
    R = 2
    if depth >= 3 and not is_in_check(temp_board, current_turn) and _has_non_pawn_material(temp_board, current_turn):
        # Create a "Null Move" grid (identical, but clears en_passant)
        null_grid = [row[:] for row in temp_board.grid]
        next_turn = current_turn.opponent()
        
        # Do a reduced depth search with the turn skipped
        if is_maximizing:
            null_score = _minimax(null_grid, depth - 1 - R, alpha, beta, False, ai_color, None, next_turn, end_time)
            if null_score >= beta:
                return beta  # Prune!
        else:
            null_score = _minimax(null_grid, depth - 1 - R, alpha, beta, True, ai_color, None, next_turn, end_time)
            if null_score <= alpha:
                return alpha # Prune!
```

## 4. Synergy with Iterative Deepening
Since you are currently working on Iterative Deepening, Null Move Pruning is the perfect companion. Iterative Deepening heavily relies on reaching deeper search depths quickly, and Null Move Pruning cuts the "branching factor" of the search tree down significantly, allowing Iterative Deepening to reach `Depth 6` or `Depth 7` in the same time it used to take to reach `Depth 4`.

## 5. Implementation Steps
1. **Helper Function**: Add `_has_non_pawn_material`.
2. **Minimax Hook**: Insert the Null Move block in `_minimax` right after the base cases/TT lookup, before calculating legal moves.
3. **Validation**: Run your test suite. The AI should play identical or better moves, but you should notice it "thinks" noticeably faster in complex mid-game positions because it's aggressively pruning dead-end branches.
