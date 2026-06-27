# Implementation Plan: Texel Tuning (Automated Parameter Optimization)

This plan outlines how to use **Texel Tuning**, a machine-learning-style approach to automatically optimize your AI's Piece Values and Piece-Square Tables (PSTs). Instead of guessing that a Knight is worth 320 points, the tuner will mathematically prove the best possible value by analyzing thousands of real grandmaster games.

## 1. The Concept
1. **Dataset**: We take a dataset of ~100,000 "quiet" chess positions (FEN strings) where we know the final outcome of the game (1.0 = White Wins, 0.5 = Draw, 0.0 = Black Wins).
2. **Sigmoid Mapping**: We use our `evaluate()` function on each position. We map the score (e.g., `+150` centipawns) to a win probability `P` using a sigmoid function: `P = 1 / (1 + 10^(-score / 400))`.
3. **Loss Function**: We calculate the Mean Squared Error (MSE) between our prediction `P` and the actual result `R`.
4. **Optimization**: We systematically tweak every single value in our PSTs by +1 or -1. If a tweak lowers the total MSE across all 100,000 positions, we keep it!

## 2. Code Changes

### A. Create the Tuner Script (`scripts/texel_tuner.py`)
Create a standalone script separate from the main game loop, since this is a heavy offline optimization task.

```python
import math
from chess_cli.board import Board
from chess_cli.ai import evaluate, PIECE_VALUES, PIECE_TABLES

# Standard scaling constant for the sigmoid
K = 400.0

def sigmoid(score: int) -> float:
    """Converts a centipawn score to a win probability (0.0 to 1.0)."""
    # clamp to avoid overflow
    score = max(-4000, min(4000, score))
    return 1.0 / (1.0 + math.pow(10.0, -score / K))

def calculate_mse(dataset: list) -> float:
    """Calculates Mean Squared Error across the whole dataset.
    dataset format: [ (Board, result_float), ... ]
    """
    total_error = 0.0
    for board, result in dataset:
        # evaluate() is always from the perspective of the side to move,
        # but for tuning, we usually want absolute White's perspective.
        # Ensure your evaluate() is adaptable or wrap it here.
        score = evaluate_white(board) 
        prob = sigmoid(score)
        error = result - prob
        total_error += error * error
    return total_error / len(dataset)
```

### B. The Optimization Loop (Local Search / Hill Climbing)
We will use a simple Local Search algorithm. It takes a parameter, increments it by 1, and checks if MSE improves.

```python
def tune():
    dataset = load_epd_dataset("dataset.epd") # You will need to download an EPD dataset
    best_mse = calculate_mse(dataset)
    print(f"Initial MSE: {best_mse}")

    improved = True
    while improved:
        improved = False
        
        # Loop through all Piece Values and Piece-Square Table elements
        for piece_type in PIECE_VALUES:
            for delta in [1, -1]:
                # 1. Apply tweak
                PIECE_VALUES[piece_type] += delta
                
                # 2. Test
                new_mse = calculate_mse(dataset)
                
                if new_mse < best_mse:
                    best_mse = new_mse
                    improved = True
                    print(f"Improved MSE to {best_mse}. {piece_type} value is now {PIECE_VALUES[piece_type]}")
                else:
                    # 3. Revert if it didn't help
                    PIECE_VALUES[piece_type] -= delta
                    
        # (Repeat the same loop structure for the 64 squares in the PST arrays)
```

## 3. The Dataset
You will need a dataset in EPD (Extended Position Description) format, which is basically FEN + the game result.
You can find thousands of these for free (e.g., the Zurichess dataset or Quiet Position datasets on computer chess forums).

## 4. Implementation Steps
1. **Prepare the Data**: Create `scripts/texel_tuner.py` and write a quick parser to load FENs and results into `Board` objects.
2. **Setup Evaluation Wrapper**: Make sure you have a function that evaluates the board *specifically* from White's perspective (since a win is 1.0 for White).
3. **Run the Tuner**: Start the script. It will likely take several hours or overnight to run through thousands of permutations.
4. **Update the Engine**: Once it finishes, copy the optimized arrays and values it prints out and paste them over the hardcoded ones in `chess_cli/ai.py`. You'll immediately notice the AI playing more human-like, positional chess!
