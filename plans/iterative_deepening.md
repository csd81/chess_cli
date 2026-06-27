# Implementation Plan: Iterative Deepening & Time Limits

This plan outlines how to shift the AI from a fixed-depth search (e.g., "always search exactly 4 moves deep") to a time-based search (e.g., "think for exactly 2 seconds"). This maximizes the AI's strength by utilizing the Transposition Tables to perfectly order moves.

## 1. Goal
Iterative Deepening works by repeatedly running the Minimax algorithm at increasing depths: first Depth 1, then Depth 2, then Depth 3, and so on, until a time limit is reached. If the time limit is hit during Depth 4, the AI throws away the incomplete Depth 4 calculations and simply plays the best move it found at Depth 3.

## 2. Code Changes (`chess_cli/ai.py`)

### A. Time Management
Add a custom exception to break out of the deep recursive search when time runs out.

```python
import time

class TimeOutException(Exception):
    """Raised when the AI exceeds its allotted thinking time."""
    pass
```

### B. Modify `_minimax` to Check Time
Pass an `end_time` parameter down the recursive tree. Every few nodes (or every node), check if the current time exceeds `end_time`.

```python
def _minimax(grid, depth, alpha, beta, is_maximizing, ai_color, en_passant_target, current_turn, end_time):
    # Check for timeout
    if time.time() > end_time:
        raise TimeOutException()
        
    # ... rest of minimax / transposition table logic ...
```

### C. The Iterative Deepening Loop (`get_best_move`)
Rewrite `get_best_move` to use a `while` or `for` loop that increments depth.

```python
def get_best_move(board: Board, current_turn: Color, en_passant_target=None, time_limit: float = 2.0):
    legal = generate_legal_moves(board, current_turn, en_passant_target=en_passant_target)
    if not legal: return None
    
    # Check opening book first...
    
    end_time = time.time() + time_limit
    best_move_overall = legal[0] # Fallback
    
    # Iterative Deepening Loop
    for depth in range(1, 20):  # 20 is an arbitrary max depth
        try:
            # We want to order our root moves too! 
            # If we found a best move at depth D-1, search it FIRST at depth D.
            if best_move_overall in legal:
                legal.remove(best_move_overall)
                legal.insert(0, best_move_overall)
                
            best_score = -999999
            current_best_move = legal[0]
            
            for move in legal:
                # Check timeout before starting a root branch
                if time.time() > end_time:
                    raise TimeOutException()
                    
                ng, nep = _simulate_move(board, move, en_passant_target)
                nt = current_turn.opponent()
                score = _minimax(ng, depth - 1, -999999, 999999, False, current_turn, nep, nt, end_time)
                
                if score > best_score:
                    best_score = score
                    current_best_move = move
            
            # If we successfully completed this depth without a TimeOutException,
            # save the best move found.
            best_move_overall = current_best_move
            
            # Optional: If we found a forced checkmate, we can break early!
            if best_score > 90000:
                break
                
        except TimeOutException:
            # Time ran out in the middle of a depth search.
            # Discard the incomplete results and break the loop.
            break
            
    return best_move_overall
```

## 3. Synergy with Transposition Tables
Iterative Deepening might *sound* slow because it recalculates Depth 1, then Depth 1+2, then Depth 1+2+3. But because you have **Transposition Tables**, it is actually *faster*. 
When it searches Depth 3, all the nodes from Depth 2 are already in the hash table! The table provides the exact scores and best moves instantly, ensuring the Alpha-Beta pruning cuts off 90% of the bad branches immediately.

## 4. Implementation Steps
1. **Define Exception**: Add `TimeOutException`.
2. **Update `_minimax` Signature**: Add the `end_time` parameter and the time check. (Note: To avoid the overhead of `time.time()` on literally every single node, you can optionally keep a node counter and only check the time every 1000 nodes).
3. **Implement Loop**: Replace the fixed `depth=3` logic in `get_best_move` with the `for depth in range(1, 20):` loop.
4. **Test**: Run the CLI. Set the time limit to 2 seconds. Verify that the AI returns a move exactly at the 2-second mark, regardless of how complex the board state is.

## Implementation Status: COMPLETED

This feature has been fully implemented.

### Changes made to chess_cli/ai.py:

1. **TimeOutException** -- custom exception raised when the AI exceeds its thinking time.

2. **Node counter (NODE_CHECK_INTERVAL=1024)** -- periodic timeout checks
   using a power-of-2 counter to avoid calling time.time() on every single node.
   Only checks every 1024 nodes.

3. **end_time parameter added** to _minimax and _quiescence_search -- both functions
   call _check_timeout(end_time) periodically. Default value 0 means no timeout
   (backward compatible with tests).

4. **Iterative deepening loop in get_best_move** -- two modes:
   - **Mode A (fixed depth)**: When time_limit=None, uses the original depth-based
     search (backward compatible, all tests unchanged).
   - **Mode B (time-limited)**: When time_limit is set (in seconds), runs iterative
     deepening:
     - Loops depth = 1, 2, 3, ... 100
     - Promotes the best move from the previous depth to the front of the root list
     - Sorts root moves by capture value (MVV-LVA style)
     - Catches TimeOutException to discard an incomplete depth and return the best
       move from the last completed depth
     - Early-exits if a forced checkmate is found (score > 90000)

### Key design decisions:
- **Node counter, not per-node time checks** -- checking time.time() every 1024 nodes
  avoids the cost of a syscall on every position (can be 10-20% overhead).
- **Power-of-2 modulus** -- _node_count & 1023 == 0 is faster than modulo.
- **Backward compatible signature** -- existing callers using depth=N work identically;
  new callers can pass time_limit=2.0 to use iterative deepening.

### Tests:
All **133 non-TUI tests pass** (including all 35 transposition tests).