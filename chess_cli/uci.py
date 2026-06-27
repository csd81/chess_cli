"""UCI (Universal Chess Interface) protocol implementation.

Allows the engine to be used with UCI-compatible GUIs like Arena, CuteChess, etc.
"""

import sys
import time
from chess_cli.game import Game
from chess_cli.ai import get_best_move, clear_tt
from chess_cli.moves import algebraic_to_pos


AI_DEPTH = 6      # Default max depth for fixed-depth mode
MOVE_OVERHEAD = 0.1  # Reserve 100ms for UCI communication overhead


def handle_position(game: Game, args: list[str]) -> Game:
    """Handle the 'position' UCI command.

    Syntax:
        position startpos [moves <uci_move1> <uci_move2> ...]
        position fen <fen_string> [moves <uci_move1> <uci_move2> ...]

    Returns the resulting Game object.
    """
    if not args:
        return game

    if args[0] == "startpos":
        game = Game()
        idx = 1
    elif args[0] == "fen":
        # Collect FEN string (everything before "moves")
        fen_parts = []
        idx = 1
        while idx < len(args) and args[idx] != "moves":
            fen_parts.append(args[idx])
            idx += 1
        fen_str = " ".join(fen_parts)
        game = Game(fen=fen_str)
    else:
        return game

    # Apply moves if present
    if idx < len(args) and args[idx] == "moves":
        idx += 1
        while idx < len(args):
            game.make_move_from_uci(args[idx])
            idx += 1

    return game


def parse_time(args: list[str], game: Game) -> float:
    """Parse time control arguments from the 'go' command.

    Returns a time limit in seconds for the current move.
    """
    wtime = None
    btime = None
    winc = 0
    binc = 0
    movestogo = None
    depth = None

    i = 0
    while i < len(args):
        if args[i] == "wtime" and i + 1 < len(args):
            wtime = int(args[i + 1]) / 1000.0  # ms to seconds
            i += 2
        elif args[i] == "btime" and i + 1 < len(args):
            btime = int(args[i + 1]) / 1000.0
            i += 2
        elif args[i] == "winc" and i + 1 < len(args):
            winc = int(args[i + 1]) / 1000.0
            i += 2
        elif args[i] == "binc" and i + 1 < len(args):
            binc = int(args[i + 1]) / 1000.0
            i += 2
        elif args[i] == "movestogo" and i + 1 < len(args):
            movestogo = int(args[i + 1])
            i += 2
        elif args[i] == "depth" and i + 1 < len(args):
            depth = int(args[i + 1])
            i += 2
        else:
            i += 1

    # If explicit depth is given, use fixed-depth search (no time limit)
    if depth is not None:
        return None, depth

    # Budget for current move based on remaining time
    is_white = game.current_turn.value == "white"
    time_left = wtime if is_white else btime
    inc = winc if is_white else binc

    if time_left is None:
        return 0.5, None  # Fallback: search for 0.5s

    if movestogo and movestogo > 0:
        budget = (time_left - MOVE_OVERHEAD) / movestogo
    else:
        # Expect ~40 moves remaining
        budget = (time_left - MOVE_OVERHEAD) / 40

    # Add increment
    budget += inc * 0.8  # Use 80% of increment

    # Clamp to reasonable bounds
    budget = max(0.01, min(budget, time_left - MOVE_OVERHEAD))
    budget = max(0.01, min(budget, 30.0))  # Cap at 30s per move

    return budget, None


def handle_go(game: Game, args: list[str]) -> None:
    """Handle the 'go' UCI command.

    Calculates the best move and prints it.
    """
    time_limit, fixed_depth = parse_time(args, game)

    if fixed_depth is not None:
        best_move = get_best_move(
            game.board, game.current_turn,
            en_passant_target=game.en_passant_target,
            depth=fixed_depth,
        )
    elif time_limit is not None:
        best_move = get_best_move(
            game.board, game.current_turn,
            en_passant_target=game.en_passant_target,
            time_limit=time_limit,
        )
    else:
        best_move = get_best_move(
            game.board, game.current_turn,
            en_passant_target=game.en_passant_target,
            time_limit=0.5,
        )

    if best_move is not None:
        print(f"bestmove {best_move.uci()}")
    else:
        print("bestmove 0000")
    sys.stdout.flush()


def uci_loop() -> None:
    """Main UCI loop — reads commands from stdin, writes responses to stdout."""
    game = Game()
    debug = False

    while True:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            break

        if not line:
            break  # EOF

        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        command = tokens[0]

        if command == "uci":
            print("id name ChessCLI")
            print("id author csd81")
            print("option name Hash type spin default 64 min 1 max 256")
            print("option name Debug type check default false")
            print("uciok")
            sys.stdout.flush()

        elif command == "debug":
            if len(tokens) > 1:
                debug = tokens[1] == "on"

        elif command == "isready":
            print("readyok")
            sys.stdout.flush()

        elif command == "setoption":
            # Parse setoption commands
            if len(tokens) >= 5 and tokens[1] == "name":
                opt_name = tokens[2]
                if opt_name == "Debug" and len(tokens) >= 5:
                    debug = tokens[4] == "true"

        elif command == "ucinewgame":
            game = Game()
            clear_tt()

        elif command == "position":
            game = handle_position(game, tokens[1:])

        elif command == "go":
            handle_go(game, tokens[1:])

        elif command == "stop":
            # In a threaded engine we'd stop the search here.
            # For our synchronous engine, this is a no-op since
            # the search completes before "bestmove" is printed.
            pass

        elif command == "ponderhit":
            # Pondering not implemented — treat as "go" with current settings
            pass

        elif command == "quit":
            break

        elif debug:
            print(f"info string unknown command: {line}")
            sys.stdout.flush()


def main() -> None:
    """Entry point for UCI mode."""
    uci_loop()


if __name__ == "__main__":
    main()
