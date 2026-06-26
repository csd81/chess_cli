# Chess CLI

A command-line chess game written in Python.

## Getting Started

    python main.py


## How to Play

Enter moves in UCI notation:
  e2e4  - Move pawn from e2 to e4
  e7e8q - Move pawn to e8 and promote to queen

### Commands
  help  - Show help
  moves - Show all legal moves
  quit  - Exit the game

## Project Structure

chess/
  chess_cli/
    __init__.py
    board.py    - Board representation and display
    pieces.py   - Piece definitions
    moves.py    - Move generation and validation
    game.py     - Game state management
    cli.py      - CLI interface
  main.py         - Entry point
  requirements.txt

## Features

[x] Board display with Unicode chess pieces
[x] Standard starting position
[x] Legal move generation for all pieces
[x] Check, checkmate, and stalemate detection
[x] Pawn promotion
[x] Castling
[ ] En passant
[ ] Move history display
[ ] Undo move
[ ] PGN export
