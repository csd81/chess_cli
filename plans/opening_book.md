# Implementation Plan: AI Opening Book (Revised)

## Review of Original Plan
The original plan was on the right track but had several gaps:

1. **Key generation**: The plan says `" ".join(fen.split(" ")[:4])` but didn't account for how the `Board` class works. `board.to_fen()` only returns piece placement (field 1 of 6). The full key must be assembled from board state + turn + castling rights + en passant target. Castling rights aren't stored on `Board` — they must be derived from piece positions (king+rook home squares).
2. **Integration point**: The plan says to "parse the book move" but doesn't specify **how** to convert a UCI string (e.g. `"e2e4"`) back into a `Move` object. The correct approach: look up legal moves and pick one whose `.uci()` matches.
3. **Book coverage**: Only shows 1.e4 lines. Need responses for 1.d4, 1.c4, 1.Nf3, and 2nd-move lines (Sicilian, French, Caro-Kann, Ruy Lopez, Queen's Gambit, Indian).
4. **Castling in key**: Keys must reflect castling rights because rook captures on a1/h1/a8/h8 change legality. Since `Board` doesn't store `has_moved` in a way accessible from FEN alone, derive castling rights from whether king/rooks are on their home squares.
5. **Random choice**: Using `random.choice()` is fine but must ensure the chosen UCI string actually exists in the legal moves list (it should, but defense in depth).
6. **Test location**: AI tests live in `tests/test_integration.py` under `TestAIIntegration`, not `tests/test_ai.py`.

## 1. Goal
Give the AI a small opening book of ~60 positions so it plays standard responses for the first 2-3 moves instead of calculating from scratch. This makes the AI stronger and nearly instant in the opening.

## 2. Implementation

### A. Create `chess_cli/opening_book.py`

New module with:

```python
OPENING_BOOK: dict[str, list[str]] = {
    # Key format: "<board_fen> <active> <castling> <ep>"
    # Castling derived from piece positions (king+rook on home squares)
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": [
        "e2e4", "d2d4", "c2c4", "g1f3",
    ],
    # 1.e4 responses
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3": [
        "e7e5", "c7c5", "e7e6", "d7d6", "g7g6", "b8c6", "g8f6", "a7a6", "b7b6",
    ],
    # ... etc for ~60 positions
}

def _fen_key(board: Board, current_turn: Color,
              en_passant_target: Optional[Position]) -> str:
    \"\"\"Build a normalized position key for opening book lookup.\"\"\"
    ...

def get_book_move(board: Board, current_turn: Color,
                   en_passant_target: Optional[Position],
                   legal_moves: list[Move]) -> Optional[Move]:
    \"\"\"Return a random book move if position is in book, else None.\"\"\"
    key = _fen_key(board, current_turn, en_passant_target)
    if key not in OPENING_BOOK:
        return None
    book_ucis = OPENING_BOOK[key]
    candidates = [m for m in legal_moves if m.uci() in book_ucis]
    if not candidates:
        return None
    return random.choice(candidates)
```

### B. Update `chess_cli/ai.py`

In `get_best_move()`, after computing `legal = generate_legal_moves(...)`, insert a book check:

```python
book_move = get_book_move(board, current_turn, en_passant_target, legal)
if book_move is not None:
    return book_move
```

This goes before any minimax calculation, making book moves essentially free (instant response).

### C. `chess_cli/board.py` — Add a helper

Add `_get_castling_rights()` static/public method to derive castling rights from piece positions:
- White king on e1 & rook on h1 → "K"
- White king on e1 & rook on a1 → "Q"  
- Black king on e8 & rook on h8 → "k"
- Black king on e8 & rook on a8 → "q"
- Join them, default "-" if none.

## 3. Book Entries (~60 positions)

Include responses for:

| Position | Responses |
|----------|-----------|
| Starting position | e4, d4, c4, Nf3, b3, g3, f4 |
| 1.e4 responses | e5, c5, e6, d6, g6, Nc6, Nf6, a6, b6 |
| 1.e4 e5 2.Nf3 | Nc6, d6, Nf6, f5 |
| 1.e4 e5 2.Nf3 Nc6 3.Bb5 | a6, Nf6, d6, Bc5, Nge7 |
| 1.e4 c5 (Sicilian) 2.Nf3 | d6, Nc6, e6, g6, a6 |
| 1.e4 e6 (French) 2.d4 | d5 |
| 1.e4 d6 (Pirc) 2.d4 | Nf6, g6 |
| 1.e4 g6 (Modern) 2.d4 | Bg7 |
| 1.e4 Nc6 (Nimzowitsch) 2.d4 | d5 |
| 1.d4 responses | d5, Nf6, e6, f5, g6, d6, c5 |
| 1.d4 d5 2.c4 (Queen's Gambit) | e6, c6, dxc4, Nc6, e5 |
| 1.d4 Nf6 (Indian) 2.c4 | e6, g6, c5, c6, b6 |
| 1.c4 responses | e5, c5, Nf6, e6 |
| 1.Nf3 responses | d5, Nf6, c5, e6, g6 |

## 4. Files Modified
- `chess_cli/opening_book.py` — **NEW** (book dict + lookup)
- `chess_cli/ai.py` — Add book check at top of `get_best_move()`
- `chess_cli/board.py` — Add `get_castling_rights()` helper
- `tests/test_integration.py` — Add `TestOpeningBook` class

## 5. Verification
```bash
python -m pytest tests/ -v --tb=short
# 2 new tests:
#   - test_book_returns_starting_move: AI plays e4/d4/c4/Nf3 from start
#   - test_book_responds_to_e4: After 1.e4, AI responds with e5/c5/e6/etc.
```
