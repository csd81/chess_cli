/* ============================================================
   Chess Web App - Frontend Logic
   ============================================================ */

const PIECE_SYMBOLS = {};
const MODE_NAMES = {};

let state = null;
let selectedSquare = null;
let legalTargets = [];
let pendingPromoUci = null;
let isAiThinking = false;

const boardEl = document.getElementById("board");
const statusText = document.getElementById("status-text");
const moveListEl = document.getElementById("move-list");
const modeIndicator = document.getElementById("mode-indicator");
const promoDialog = document.getElementById("promo-dialog");
const modeDialog = document.getElementById("mode-dialog");

function fillSymbols() {
    const s = PIECE_SYMBOLS;
    s["K"] = "\u2654"; s["Q"] = "\u2655"; s["R"] = "\u2656";
    s["B"] = "\u2657"; s["N"] = "\u2658"; s["P"] = "\u2659";
    s["k"] = "\u265A"; s["q"] = "\u265B"; s["r"] = "\u265C";
    s["b"] = "\u265D"; s["n"] = "\u265E"; s["p"] = "\u265F";

    const m = MODE_NAMES;
    m["pvp"] = "Player vs Player";
    m["pvcpu"] = "Player vs CPU";
    m["cpuvp"] = "CPU vs Player";
    m["aivai"] = "AI vs AI";
}

async function apiGet(path) {
    const res = await fetch(path);
    if (!res.ok) {
        const err = await res.json().catch(() => ({detail: res.statusText}));
        throw new Error(err.detail || "API Error");
    }
    return res.json();
}

async function apiPost(path, body) {
    const res = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({detail: res.statusText}));
        throw new Error(err.detail || "API Error");
    }
    return res.json();
}

function parseFen(fen) {
    const board = [];
    const rows = fen.split(" ")[0].split("/");
    for (const row of rows) {
        const boardRow = [];
        for (const ch of row) {
            if (ch >= "1" && ch <= "8") {
                for (let i = 0; i < parseInt(ch); i++) {
                    boardRow.push(null);
                }
            } else {
                boardRow.push({
                    type: ch.toUpperCase(),
                    color: ch === ch.toUpperCase() ? "white" : "black",
                    symbol: PIECE_SYMBOLS[ch] || ch,
                });
            }
        }
        boardRow.reverse();
        board.push(boardRow);
    }
    board.reverse();
    return board;
}

function renderBoard() {
    if (!state) return;
    const board = parseFen(state.fen);
    boardEl.innerHTML = "";

    legalTargets = [];
    if (selectedSquare) {
        for (const uci of state.legal_moves) {
            if (uci.startsWith(selectedSquare.sq)) {
                legalTargets.push(uci.substring(2, 4));
            }
        }
    }

    let kingSquare = null;
    if (state.in_check) {
        const target = state.turn === "white" ? "K" : "k";
        const sym = PIECE_SYMBOLS[target];
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const p = board[r][c];
                if (p && p.symbol === sym) {
                    kingSquare = algebraic(7 - r, 7 - c);
                }
            }
        }
    }

    for (let dr = 0; dr < 8; dr++) {
        for (let dc = 0; dc < 8; dc++) {
            const br = 7 - dr, bc = 7 - dc;
            const shade = (dr + dc) % 2 === 0 ? "light" : "dark";
            const sq = document.createElement("div");
            sq.className = "square " + shade;
            sq.dataset.row = br;
            sq.dataset.col = bc;
            const alg = algebraic(br, bc);
            sq.dataset.square = alg;

            if (state.last_move) {
                if (alg === state.last_move.from || alg === state.last_move.to) {
                    sq.classList.add("last-move");
                }
            }
            if (alg === kingSquare) sq.classList.add("in-check");
            if (selectedSquare && alg === selectedSquare.sq) sq.classList.add("selected");
            if (legalTargets.includes(alg)) {
                const p = board[dr][dc];
                sq.classList.add(p ? "legal-target-capture" : "legal-target");
            }

            const piece = board[dr][dc];
            if (piece) {
                const span = document.createElement("span");
                span.className = "piece " + piece.color;
                span.textContent = piece.symbol;
                sq.appendChild(span);
            }

            sq.addEventListener("click", function() { onSquareClick(alg); });
            boardEl.appendChild(sq);
        }
    }
}

function algebraic(row, col) {
    return String.fromCharCode(97 + col) + (8 - row);
}

function parseAlgebraic(sq) {
    return [8 - parseInt(sq[1]), sq.charCodeAt(0) - 97];
}

function updateStatus() {
    statusText.textContent = state.status_text;
    modeIndicator.textContent = MODE_NAMES[state.game_mode] || state.game_mode;
}

function updateMoveHistory() {
    moveListEl.innerHTML = "";
    const moves = state.move_history;
    for (let i = 0; i < moves.length; i += 2) {
        const num = (i / 2) + 1;
        const row = document.createElement("div");
        row.className = "move-row";
        row.innerHTML = '<span class="move-number">' + num + '.</span>'
            + '<span class="move-white">' + (moves[i] || "") + '</span>'
            + '<span class="move-black">' + (moves[i + 1] || "") + '</span>';
        moveListEl.appendChild(row);
    }
    moveListEl.scrollTop = moveListEl.scrollHeight;
}

function onSquareClick(sq) {
    if (state.game_over || isAiThinking) return;
    if (!promoDialog.classList.contains("hidden")) return;

    const [row, col] = parseAlgebraic(sq);
    const board = parseFen(state.fen);
    const piece = board[7 - row][7 - col];

    if (!selectedSquare) {
        if (piece && piece.color === state.turn) {
            selectedSquare = {sq: sq};
            renderBoard();
        }
    } else {
        const fromSq = selectedSquare.sq;
        if (sq === fromSq) {
            selectedSquare = null;
            renderBoard();
            return;
        }

        const isPromo = !piece && (
            (state.turn === "white" && sq[1] === "8") ||
            (state.turn === "black" && sq[1] === "1")
        );

        if (isPromo) {
            pendingPromoUci = fromSq + sq;
            showPromotionDialog();
            return;
        }

        const legalUci = state.legal_moves.find(function(m) { return m === fromSq + sq; });
        if (legalUci) {
            selectedSquare = null;
            sendMove(legalUci);
        } else if (piece && piece.color === state.turn) {
            selectedSquare = {sq: sq};
            renderBoard();
        } else {
            selectedSquare = null;
            renderBoard();
        }
    }
}

async function sendMove(uci) {
    try {
        state = await apiPost("/api/move", {uci: uci});
        renderBoard();
        updateStatus();
        updateMoveHistory();
        await triggerAiIfNeeded();
    } catch (err) {
        console.error("Move error:", err);
        statusText.textContent = "Error: " + err.message;
    }
}

async function triggerAiIfNeeded() {
    const mode = state.game_mode;
    const turn = state.turn;
    let shouldMove = false;
    if (mode === "aivai") shouldMove = true;
    else if (mode === "pvcpu" && turn === "black") shouldMove = true;
    else if (mode === "cpuvp" && turn === "white") shouldMove = true;

    if (shouldMove && !state.game_over) {
        isAiThinking = true;
        statusText.textContent = "Thinking...";
        try {
            state = await apiPost("/api/ai");
            renderBoard();
            updateStatus();
            updateMoveHistory();
            await triggerAiIfNeeded();
        } catch (err) {
            console.error("AI error:", err);
            statusText.textContent = "AI Error: " + err.message;
        } finally {
            isAiThinking = false;
        }
    }
}

function showPromotionDialog() { promoDialog.classList.remove("hidden"); }
function hidePromotionDialog() { promoDialog.classList.add("hidden"); pendingPromoUci = null; }

function selectPromotion(pieceLetter) {
    const uci = pendingPromoUci + pieceLetter;
    hidePromotionDialog();
    pendingPromoUci = null;
    if (state.legal_moves.includes(uci)) {
        selectedSquare = null;
        sendMove(uci);
    } else {
        const prefix = uci.substring(0, 4);
        for (const m of state.legal_moves) {
            if (m.startsWith(prefix)) {
                selectedSquare = null;
                sendMove(m);
                return;
            }
        }
        statusText.textContent = "Invalid promotion";
    }
}

async function startNewGame(mode) {
    selectedSquare = null;
    try {
        state = await apiPost("/api/new_game", {mode: mode});
        renderBoard();
        updateStatus();
        updateMoveHistory();
        hideModeDialog();
        await triggerAiIfNeeded();
    } catch (err) {
        console.error("New game error:", err);
        statusText.textContent = "Error: " + err.message;
    }
}

function showModeDialog() { modeDialog.classList.remove("hidden"); }
function hideModeDialog() { modeDialog.classList.add("hidden"); }

async function handleUndo() {
    if (isAiThinking || !state || state.game_over) return;
    try {
        state = await apiPost("/api/undo");
        selectedSquare = null;
        renderBoard();
        updateStatus();
        updateMoveHistory();
    } catch (err) {
        console.error("Undo error:", err);
    }
}

async function loadState() {
    try {
        state = await apiGet("/api/state");
        renderBoard();
        updateStatus();
        updateMoveHistory();
        showModeDialog();
    } catch (err) {
        console.error("Load error:", err);
        statusText.textContent = "Failed to load game";
    }
}

document.addEventListener("DOMContentLoaded", function() {
    fillSymbols();
    loadState();

    document.getElementById("btn-new").addEventListener("click", showModeDialog);
    document.getElementById("btn-undo").addEventListener("click", handleUndo);

    document.querySelectorAll(".promo-btn").forEach(function(btn) {
        btn.addEventListener("click", function() { selectPromotion(btn.dataset.piece); });
    });

    document.querySelectorAll(".mode-btn").forEach(function(btn) {
        btn.addEventListener("click", function() { startNewGame(btn.dataset.mode); });
    });

    promoDialog.addEventListener("click", function(e) {
        if (e.target === promoDialog) hidePromotionDialog();
    });

    modeDialog.addEventListener("click", function(e) {
        if (e.target === modeDialog) hideModeDialog();
    });

    document.addEventListener("keydown", function(e) {
        if (e.key === "u" || e.key === "U") handleUndo();
        if (e.key === "n" || e.key === "N") showModeDialog();
        if (e.key === "Escape") {
            if (!promoDialog.classList.contains("hidden")) hidePromotionDialog();
            else if (!modeDialog.classList.contains("hidden")) hideModeDialog();
            else if (selectedSquare) { selectedSquare = null; renderBoard(); }
        }
    });
});
