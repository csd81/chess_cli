# Implementation Plan: PGN Export

Portable Game Notation (PGN) is the universal format for recording chess games. Adding PGN export allows players to save their game logs and import them into chess analysis engines like Lichess or Chess.com.

## 1. Code Changes

### A. Implement PGN Generation in `Game` (`chess_cli/game.py`)
Add a method `export_pgn(self, white_name: str = "Player 1", black_name: str = "Player 2") -> str`:
1. **Metadata Headers**: Build the standard 7-tag roster (Seven Tag Roster):
   - `[Event "Casual Game"]`
   - `[Site "Chess CLI"]`
   - `[Date "YYYY.MM.DD"]` (using Python's `datetime` module)
   - `[Round "1"]`
   - `[White "{white_name}"]`
   - `[Black "{black_name}"]`
   - `[Result "{result_str}"]` (e.g., `1-0`, `0-1`, `1/2-1/2`, or `*` if incomplete)
2. **Format Moves**: Loop through `self.move_history` and group them by turn numbers:
   - For every two moves (White, then Black), format as `1. e4 e5`.
   - Use standard SAN (Standard Algebraic Notation) notation generated via the existing `get_move_notation()` helper.
   - Append the game result at the end of the move text.
3. Return the compiled PGN string.

### B. Trigger Export in CLI (`chess_cli/cli.py`)
1. In `run()` loop, check if the game has ended (`self.game.game_over`) or if the user is quitting.
2. Prompt the user: `"Would you like to save this game to a PGN file? (y/n): "`
3. If yes:
   - Prompt for player names (optional, defaulting to "White" and "Black").
   - Prompt for file name (defaulting to `game.pgn` or auto-generated timestamp like `game_20260626.pgn`).
   - Write the PGN string to the specified file.
   - Print a success message confirming the path of the saved file.

## 2. Verification Plan
- Play a short game to completion (or make a few moves and type `quit`).
- Export the game to `test_game.pgn`.
- Open the `.pgn` file with a text editor to confirm the formatting is valid.
- Copy the file contents and paste them into a PGN viewer (e.g., [Lichess Import Page](https://lichess.org/paste)) to verify it parses correctly and replay the moves.
