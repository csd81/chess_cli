

## Implementation Status: COMPLETED

This feature has been fully implemented.

### Changes made to `chess_cli/ai.py`:

1. **Added `_quiescence_search` function** -- called when `depth == 0` in minimax, searches only capture moves until the position is quiet.

2. **_quiescence_search features**:
   - Stand-pat evaluation -- static score of current position as baseline
   - Beta cutoff checks -- if stand-pat already exceeds bounds, prune immediately
   - MVV-LVA ordering -- captures sorted by (victim_value * 10 - attacker_value) for optimal pruning
   - Delta pruning -- skip a capture if stand_pat + max_gain can't possibly beat alpha (margin: 200cp)
   - Depth limit -- QS_MAX_DEPTH = 8 safety cap prevents runaway recursion
   - Full Zobrist hash + castling integration -- quiescence plumbed through simulate_move()
   - TT integration -- depth == 0 TT entries are stored during normal search and reused

3. **Hook in `_minimax`** -- the `depth == 0` termination block now calls quiescence search instead of static eval.

### Constants defined:
- `QS_DELTA = 900` -- largest single-capture material swing (queen), for delta pruning
- `QS_MAX_DEPTH = 8` -- safety limit on quiescence recursion depth

### Tests:
All **180 tests pass** (181 collected, 1 pre-existing skip). Quiescence adds tactical depth that makes the test suite run longer because the AI now fully resolves capture chains.
