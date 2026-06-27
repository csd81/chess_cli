# Implementation Plan: Web Application (FastAPI + Vanilla JS/CSS)

## Overview
Serve the chess engine via a FastAPI backend with a premium dark-mode frontend.
Unicode chess symbols for pieces, CSS Grid board, click-to-move with legal move
highlights, support for PvP, PvCPU, CPUvP, and AI vs AI modes.

## 1. Files to Create

| File | Description |
|------|-------------|
| `web/__init__.py` | Empty package marker |
| `web/server.py` | FastAPI application with 6 endpoints |
| `web/static/index.html` | HTML page structure |
| `web/static/style.css` | Premium dark theme, board grid, animations |
| `web/static/app.js` | Board rendering, click handling, API calls |

### Modified Files
| File | Change |
|------|--------|
| `requirements.txt` | Add `fastapi`, `uvicorn` |
| `main.py` | Add `--web` / `-w` flag |

## 2. API Endpoints

| Method | Path | Body | Response | Description |
|--------|------|------|----------|-------------|
| GET | `/` | — | `index.html` | Serve frontend |
| GET | `/api/state` | — | `GameState` JSON | Full current state |
| POST | `/api/move` | `{"uci":"e2e4"}` | `GameState` JSON | Execute a human move |
| POST | `/api/ai` | — | `GameState` JSON | Compute & execute one AI move |
| POST | `/api/undo` | — | `GameState` JSON | Undo last move (2 in CPU mode) |
| POST | `/api/new_game` | `{"mode":"pvp"}` | `GameState` JSON | Reset game |

### GameState JSON
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
  "turn": "white",
  "game_over": false,
  "winner": null,
  "draw_reason": "",
  "in_check": false,
  "is_checkmate": false,
  "is_stalemate": false,
  "legal_moves": ["e2e4", "d2d4", ...],
  "last_move": {"from": "e2", "to": "e4"},
  "move_history": ["e4", "e5", "Nf3"],
  "status_text": "White's turn",
  "game_mode": "pvp"
}
```

## 3. Backend Design

- `GameState` Pydantic model for typed responses
- Global `game: Game` and `game_mode: str`
- `_build_state()` helper to construct the response
- Endpoints parse UCI, call `game.make_move()` / `get_best_move()` / etc.
- Static files served from `web/static/` via `StaticFiles`

## 4. Frontend Design

### Board Rendering
- Parse FEN into 8x8 piece array
- CSS Grid with classic chess colors (`#b58863` dark, `#f0d9b5` light)
- Unicode chess symbols (♔♕♖♗♘♙♚♛♜♝♞♟) with text-shadow
- White pieces: `#fff` on dark, `#000` on light squares

### Interactivity
- Click 1: Select own piece → `.selected` class, compute targets from `legal_moves`
- Click 2: Click target → `POST /api/move` with UCI
- Click same piece → deselect; click other own piece → switch selection

### Highlights
- Selected: golden glow (`#f6f669` / `#d4d43c`)
- Legal targets: green dot (empty) / green ring (capture)
- Last move: subtle yellow overlay
- King in check: red background

### UI Layout
- Header bar with mode indicator + new game / undo buttons
- Board center-left, sidebar right with status + move history
- Promotion dialog modal

### Game Flow
1. Load → `GET /api/state` → render board
2. Click piece → highlight targets
3. Click target → `POST /api/move`
4. Re-render
5. If CPU turn → `POST /api/ai` → re-render (loop until human turn or game over)

## 5. Implementation Order
1. `web/__init__.py` + `web/server.py`
2. `web/static/index.html` + `style.css` + `app.js`
3. Update `requirements.txt`
4. Update `main.py`
5. Test: `pip install fastapi uvicorn && python main.py --web`

## 6. Files
- `web/__init__.py` — NEW
- `web/server.py` — NEW (FastAPI server)
- `web/static/index.html` — NEW
- `web/static/style.css` — NEW
- `web/static/app.js` — NEW
- `requirements.txt` — modified
- `main.py` — modified
