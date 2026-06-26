# Implementation Plan: AI Opponent

Add a basic CPU player so the game can be played in single-player mode. The AI will use a minimax search algorithm with alpha-beta pruning and simple piece evaluation.

## 1. Code Changes

### A. Create AI Module (`chess_cli/ai.py`)
Create a new file containing the search algorithm:
1. **Evaluation Function**:
   - Assign static values to pieces: Pawn=100, Knight=320, Bishop=330, Rook=500, Queen=900, King=20000.
   - Sum values for current player and subtract opponent values.
   - (Optional) Add basic position tables (e.g., incentivize knights/bishops in the center, pawns advancing).
2. **Minimax Search with Alpha-Beta Pruning**:
   - `minimax(board, depth, alpha, beta, maximizing_player)`:
     - Base case: `depth == 0` or game over. Return evaluation.
     - Generate legal moves.
     - Recursively call `minimax` on simulated boards.
     - Keep track of the best move.
3. **Best Move Lookup**:
   - `get_best_move(game: Game, depth: int = 2) -> Optional[Move]`:
     - Run minimax to find the best scoring legal move and return it.

### B. Integrate Game Selection in CLI (`chess_cli/cli.py`)
1. In `main()`, ask the player if they want to play:
   - `(1) Player vs Player`
   - `(2) Player vs CPU (Play as White)`
   - `(3) Player vs CPU (Play as Black)`
2. Store the choice in `self.play_mode` and `self.cpu_color`.
3. In `run()` loop:
   - Check if `self.game.current_turn == self.cpu_color` and `not self.game.game_over`.
   - If it is the CPU's turn:
     - Print: `"CPU is thinking..."`
     - Call `get_best_move(self.game)` to obtain the AI's selection.
     - Play the move using `self.game.make_move()`.
     - Continue the game loop without waiting for user input.

## 2. Verification Plan
- Launch the game, select Option 2 (Player vs CPU as White).
- Play White's first move (e.g. `e2e4`).
- Verify that the CPU automatically calculates, prints its choice, makes its move, and shifts the turn back to you.
- Play a full game to check for stability and verify the CPU makes sensible captures when pieces are left undefended.
