"""FastAPI web server for chess."""

import os
import sys
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chess_cli.game import Game
from chess_cli.pieces import Color
from chess_cli.moves import (
    algebraic_to_pos, pos_to_algebraic, generate_legal_moves,
    is_in_check, is_checkmate, is_stalemate, Move
)
from chess_cli.ai import get_best_move

app = FastAPI(title="Chess Web")

game = Game()
game_mode: str = "pvp"  # pvp, pvcpu (human=white), cpuvp (human=black), aivai
ai_depth: int = 3


class MoveRequest(BaseModel):
    uci: str


class NewGameRequest(BaseModel):
    mode: str = "pvp"


class GameState(BaseModel):
    fen: str
    turn: str
    game_over: bool
    winner: Optional[str]
    draw_reason: str
    in_check: bool
    is_checkmate: bool
    is_stalemate: bool
    legal_moves: List[str]
    last_move: Optional[dict]
    move_history: List[str]
    status_text: str
    game_mode: str


def _build_state() -> GameState:
    """Build the current game state response."""
    board = game.board
    turn = game.current_turn
    turn_str = turn.value  # "white" or "black"

    # Legal moves as UCI strings
    legal = game.get_legal_moves()
    legal_ucis = [m.uci() for m in legal]

    # Check status
    check = is_in_check(board, turn)
    checkmate = is_checkmate(board, turn)
    stale = is_stalemate(board, turn)

    # Last move
    last_move_data = None
    if game.move_history:
        last = game.move_history[-1]
        last_move_data = {
            "from": pos_to_algebraic(last.from_pos),
            "to": pos_to_algebraic(last.to_pos),
        }

    # Move history in algebraic notation
    history = []
    for m in game.move_history:
        notation = game.get_move_notation(m)
        # Clean up: remove check/mate symbols for cleaner display
        history.append(notation)

    # Status text
    if game.game_over:
        if game.winner:
            status = f"{game.winner.value.capitalize()} wins!"
        elif game.draw_reason:
            status = f"Draw: {game.draw_reason}"
        else:
            status = "Draw"
    elif checkmate:
        status = "Checkmate!"
    elif stale:
        status = "Stalemate!"
    elif check:
        status = f"{turn_str.capitalize()} is in check!"
    else:
        status = f"{turn_str.capitalize()}'s turn"

    return GameState(
        fen=board.to_fen(),
        turn=turn_str,
        game_over=game.game_over,
        winner=game.winner.value if game.winner else None,
        draw_reason=game.draw_reason,
        in_check=check,
        is_checkmate=checkmate,
        is_stalemate=stale,
        legal_moves=legal_ucis,
        last_move=last_move_data,
        move_history=history,
        status_text=status,
        game_mode=game_mode,
    )


@app.get("/api/state", response_model=GameState)
def get_state():
    """Return the current game state."""
    return _build_state()


@app.post("/api/move", response_model=GameState)
def make_move(req: MoveRequest):
    """Execute a human move given in UCI notation (e.g. 'e2e4', 'e7e8q')."""
    global game
    uci = req.uci.strip().lower()
    if len(uci) < 4:
        raise HTTPException(status_code=400, detail="Invalid UCI: too short")

    from_sq = uci[:2]
    to_sq = uci[2:4]
    promo_letter = uci[4] if len(uci) >= 5 else None

    from_pos = algebraic_to_pos(from_sq)
    to_pos = algebraic_to_pos(to_sq)
    if from_pos is None or to_pos is None:
        raise HTTPException(status_code=400, detail="Invalid square coordinates")

    # If promotion, find the matching legal move
    if promo_letter:
        promo_map = {"q": 4, "r": 3, "b": 2, "n": 1}  # PieceType enum order
        from chess_cli.pieces import PieceType
        promo_types = {4: PieceType.QUEEN, 3: PieceType.ROOK,
                       2: PieceType.BISHOP, 1: PieceType.KNIGHT}
        promo_pt = promo_types.get(promo_map.get(promo_letter, 4))
        legal = game.get_legal_moves()
        for move in legal:
            if (move.from_pos == from_pos and move.to_pos == to_pos
                    and move.promotion == promo_pt):
                game.make_move_from_move(move)
                return _build_state()
        raise HTTPException(status_code=400, detail="Illegal promotion move")

    success = game.make_move(from_pos, to_pos)
    if not success:
        raise HTTPException(status_code=400, detail="Illegal move")

    return _build_state()


@app.post("/api/ai", response_model=GameState)
def ai_move():
    """Compute and execute one AI move for the current turn."""
    global game
    if game.game_over:
        raise HTTPException(status_code=400, detail="Game is over")

    move = get_best_move(
        game.board, game.current_turn,
        en_passant_target=game.en_passant_target,
        depth=ai_depth,
    )
    if move is None:
        raise HTTPException(status_code=400, detail="AI has no legal moves")

    game.make_move_from_move(move)
    return _build_state()


@app.post("/api/undo", response_model=GameState)
def undo_move():
    """Undo last move. In CPU modes, undo 2 moves (human + AI)."""
    global game
    if not game.move_history:
        raise HTTPException(status_code=400, detail="No moves to undo")

    game.undo_move()
    # In CPU modes, undo the AI move too
    if game_mode in ("pvcpu", "cpuvp", "aivai"):
        if game.move_history:
            game.undo_move()

    return _build_state()


@app.post("/api/new_game", response_model=GameState)
def new_game(req: NewGameRequest):
    """Start a new game with the given mode."""
    global game, game_mode
    valid_modes = ("pvp", "pvcpu", "cpuvp", "aivai")
    if req.mode not in valid_modes:
        raise HTTPException(status_code=400,
                            detail=f"Invalid mode. Choose from {valid_modes}")
    game = Game()
    game_mode = req.mode
    return _build_state()


# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the FastAPI server with uvicorn."""
    import uvicorn
    print(f"Chess Web App running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
