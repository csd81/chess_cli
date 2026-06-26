# Chess CLI Testing Framework Plan

To ensure the game engine remains robust, correct, and free from regression bugs, we establish a three-tiered testing framework. Every new feature must implement and pass all three types of tests: **Unit Tests**, **Adversarial Tests**, and **Integration Tests**.

---

## 📂 Directory Structure

Tests will live in a new `tests` folder in the project root:

```text
chess/
  chess_cli/
  plans/
  tests/
    __init__.py
    conftest.py             # Shared pytest fixtures
    test_unit.py            # Unit tests (logic isolation)
    test_adversarial.py     # Adversarial tests (boundary/illegal states)
    test_integration.py     # End-to-end execution flow tests
```

We will use the standard **`pytest`** framework for execution.

---

## 🧪 1. Unit Tests

Unit tests focus on verifying individual classes, methods, and functions in isolation.

### Scope
- **Move Generation**: Test that each piece type generates correct pseudo-legal coordinates on an empty board, blocked board, and starting position.
- **Board Setup & FEN**: Validate FEN import/export and board parsing.
- **Game Flags**: Test specific functions like turn switching, history updates, and en passant target registration.
- **Special Moves (Undo/PGN)**:
  - Reverting simple moves must return the board state to the exact previous grid.
  - Converting a move list to a PGN tag roster must produce syntactically valid strings.

### Sample Test Case
```python
def test_knight_moves_on_empty_board():
    board = Board()
    board.grid = [[None] * 8 for _ in range(8)]
    knight = Piece(Color.WHITE, PieceType.KNIGHT)
    board.set_piece(4, 4, knight)  # Center square e4
    
    moves = _get_pseudo_legal_moves_for_piece(board, (4, 4), knight)
    assert len(moves) == 8  # A knight in the center should have 8 moves
```

---

## 😈 2. Adversarial Tests

Adversarial tests focus on input validation, illegal operations, extreme boundary states, and security checks.

### Scope
- **Illegal Moves**:
  - Test moving pieces through occupied paths (for non-knights).
  - Attempting to capture own pieces.
  - Making moves that violate standard movement shapes.
- **King Safety Violations**:
  - Attempting to make a move that leaves your own king in check (must return `False` and not alter the board state).
  - Attempting to castle while in check, through check, or into check.
- **Mangled/Malicious CLI Inputs**:
  - Feeding short inputs (`e2`), out-of-bound coordinates (`e2e9`, `z1z2`), invalid promotion strings (`e7e8k` promoting to king), empty lines, or special characters.
- **State Violations**:
  - Attempting to move pieces during the opponent's turn.
  - Trying to execute en passant when the target pawn did not move on the *immediate preceding* turn.

### Sample Test Case
```python
def test_cannot_make_move_leaving_king_in_check():
    board = Board.from_fen("k7/8/8/8/8/8/r7/4K3 w - - 0 1")  # King on e1, Rook on a2 pinning king
    game = Game()
    game.board = board
    # Trying to move white king to f1 (illegal because rook attacks f1/f2/f3/f4/f5/f6/f7/f8)
    success = game.make_move(algebraic_to_pos("e1"), algebraic_to_pos("f1"))
    assert success is False
```

---

## 🔄 3. Integration Tests

Integration tests focus on end-to-end execution, CLI interactive session loops, and filesystem persistence.

### Scope
- **Full Game Simulation**: Programmatically simulate a full game (Scholar's Mate) from start to checkmate to verify turn switching, checkmate flags, and history logs work together.
- **CLI loop mock**: Mock stdout/stdin in `cli.py` to simulate command-line interactions (like typing `moves`, then `undo`, then making a move) and ensure the screen redraws without raising errors.
- **Filesystem Persistence**: Ensure PGN exporting writes a valid `.pgn` file to disk, closes file handles correctly, and reads/writes from valid paths.
- **AI Integration**: Run automated CPU vs CPU games (10 full trials) to verify the AI searches and executes moves without deadlocking, generating illegal moves, or entering loops.

### Sample Test Case
```python
def test_scholars_mate_full_flow():
    game = Game()
    # Scholar's mate moves: 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7#
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("d1", "h5"), ("b8", "c6"),
        ("f1", "c4"), ("g8", "f6"),
        ("h5", "f7")
    ]
    for from_sq, to_sq in moves:
        assert game.make_move(algebraic_to_pos(from_sq), algebraic_to_pos(to_sq)) is True
    
    assert game.game_over is True
    assert game.winner == Color.WHITE
```

---

## 📈 Quality Gates

For any new feature pull request (PR) or code addition:
1. **Gate 1**: Unit tests must cover all newly introduced methods (100% coverage on new methods).
2. **Gate 2**: Adversarial checks must verify validation logic rejects bad arguments or states.
3. **Gate 3**: Integration runs must verify end-to-end command line behavior and persistence.
