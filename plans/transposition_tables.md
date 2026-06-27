# Implementation Plan: Transposition Tables (Zobrist Hashing)

This plan outlines how to dramatically speed up the AI's Minimax algorithm by caching evaluated board states. This prevents the AI from recalculating the exact same position if it was reached through a different sequence of moves (a "transposition").

## 1. Goal
Implement Zobrist Hashing to uniquely and efficiently identify board states. Use these hashes as keys in a Transposition Table (a Python dictionary) to store and retrieve evaluation scores, allowing the AI to search deeper in the same amount of time.

## 2. Core Concepts
- **Zobrist Hashing**: Instead of converting the board to a slow FEN string every time, we assign a random 64-bit integer to every possible piece on every possible square, plus random numbers for castling rights, en passant, and whose turn it is. The hash of the board is just all these numbers XORed (`^`) together.
- **Incremental Updates**: When a move is made, we don't recalculate the hash from scratch. We just XOR out the piece from the starting square, and XOR it in at the target square. This is insanely fast.
- **Transposition Table (TT)**: A dictionary caching `hash -> {depth, score, flag, best_move}`.

## 3. Code Changes

### A. Create `chess_cli/zobrist.py`
Create a new file to manage the Zobrist keys:
1. Pre-compute and store random 64-bit integers for:
   - Pieces (64 squares × 12 piece types)
   - Black to move (1 number)
   - Castling rights (16 combinations)
   - En Passant file (8 files)
2. Add a `compute_initial_hash(board, current_turn)` function that calculates the full hash from scratch.
3. Add an `update_hash(current_hash, move, ...)` function that quickly XORs the necessary bits to reflect a move.

### B. Update `chess_cli/ai.py`
1. **Initialize the TT**: Create a global dictionary `TRANSPOSITION_TABLE = {}` (and a mechanism to clear it or limit its size if memory becomes an issue).
2. **TT Entry Flags**: Define constants for the bounds (since Alpha-Beta pruning means we don't always get an exact score):
   - `EXACT`: The score is the true evaluation.
   - `LOWERBOUND`: The score was produced by a beta cutoff (it's at least this good).
   - `UPPERBOUND`: The score couldn't beat alpha (it's at most this good).
3. **Modify `_minimax`**:
   - Pass the `zobrist_hash` as an argument into `_minimax`.
   - **Lookup**: At the very start of the function, check if `zobrist_hash` is in the TT.
     - If `tt_entry.depth >= current_depth`:
       - If `EXACT`: return `tt_entry.score`.
       - If `LOWERBOUND`: `alpha = max(alpha, tt_entry.score)`.
       - If `UPPERBOUND`: `beta = min(beta, tt_entry.score)`.
       - If `alpha >= beta`: return `tt_entry.score`.
   - **Execution**: Run the normal minimax loop. Ensure that `_simulate_move` also calculates the *new* Zobrist hash incrementally to pass to the next node.
   - **Store**: Before returning `best_score`, determine the flag:
     - If `best_score <= original_alpha`: flag = `UPPERBOUND`
     - If `best_score >= beta`: flag = `LOWERBOUND`
     - Else: flag = `EXACT`
     - Save to TT: `TRANSPOSITION_TABLE[zobrist_hash] = {score: best_score, depth: current_depth, flag: flag}`

### C. Update `chess_cli/game.py` (Optional but Recommended)
You can optionally replace the string-based `_get_position_key()` used for the Threefold Repetition draw rule with this new Zobrist hash, which will make draw detection faster too!

## 4. Implementation Steps
1. **Zobrist Module**: Write `zobrist.py` and test that `initial_hash` matches `update_hash` after a move.
2. **TT Integration**: Plumb the hash through `_minimax` in `ai.py` and add the table lookup/store logic.
3. **Validation Test**: Write a test where the AI evaluates `1. e4 e5 2. Nf3 Nc6` and `1. Nf3 Nc6 2. e4 e5`. Verify that the second sequence hits the Transposition Table and skips calculation.
