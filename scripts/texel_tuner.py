
"""Texel Tuning: Automated parameter optimization for the chess engine.

Uses a dataset of positions with known results to optimize PIECE_VALUES
and PIECE_TABLES by minimizing mean squared error between the engine evaluation
(mapped through a sigmoid) and the actual game outcome.

Usage:
    python -m scripts.texel_tuner [--dataset <path>] [--passes <N>]
"""

import math
import sys
import os
from typing import List, Tuple, Optional

from chess_cli.board import Board
from chess_cli.pieces import Color, Piece, PieceType
from chess_cli.ai import PIECE_VALUES, PIECE_TABLES


K = 400.0
CLAMP = 4000


def sigmoid(score: int) -> float:
    """Convert centipawn score to win probability (0.0 to 1.0)."""
    clamped = max(-CLAMP, min(CLAMP, score))
    return 1.0 / (1.0 + math.pow(10.0, -clamped / K))


def evaluate_white(board, piece_values, piece_tables):
    """Evaluate board from White perspective using given parameters."""
    score = 0
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p is None:
                continue
            value = piece_values.get(p.piece_type, 0)
            table = piece_tables.get(p.piece_type)
            if table is not None:
                table_row = r if p.color == Color.WHITE else 7 - r
                value += table[table_row][c]
            if p.color == Color.WHITE:
                score += value
            else:
                score -= value
    return score


def parse_epd_line(line):
    """Parse EPD line into (fen, result) or None.
    
    Supports:
        1. Standard EPD:  <FEN> result 1.0
        2. Pipe format:    <FEN> | 1.0
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if " | " in line:
        parts = line.split(" | ")
        fen = parts[0].strip()
        try:
            result = float(parts[1].strip())
            if 0.0 <= result <= 1.0:
                return fen, result
        except (ValueError, IndexError):
            pass
        return None
    # Standard EPD format
    tokens = line.split()
    try:
        result_idx = tokens.index("result")
    except ValueError:
        return None
    if result_idx + 1 >= len(tokens):
        return None
    try:
        result = float(tokens[result_idx + 1])
    except ValueError:
        return None
    if not (0.0 <= result <= 1.0):
        return None
    fen = " ".join(tokens[:result_idx])
    return fen, result


def load_dataset(path):
    """Load dataset from file. Returns list of (Board, float)."""
    dataset = []
    errors = 0
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_epd_line(line)
            if parsed is None:
                continue
            fen, result = parsed
            try:
                board = Board.from_fen(fen)
                dataset.append((board, result))
            except Exception:
                errors += 1
    if errors:
        print(f"Warning: {errors} lines had invalid FEN.", file=sys.stderr)
    return dataset


def calculate_mse(dataset, piece_values, piece_tables):
    """Calculate Mean Squared Error over the dataset."""
    if not dataset:
        return 0.0
    total_error = 0.0
    for board, result in dataset:
        score = evaluate_white(board, piece_values, piece_tables)
        prob = sigmoid(score)
        error = result - prob
        total_error += error * error
    return total_error / len(dataset)


def generate_synthetic_dataset():
    """Generate synthetic dataset for testing/demo."""
    positions = [
        ("rnbqkb1r/ppppp1pp/5n2/4P3/2B5/8/PPPP1PPP/RNBQK1NR b KQkq - 0 3", 0.85),
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 0.50),
        ("rnbqkbnr/ppppp1pp/8/5p2/4P3/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 2", 0.35),
        ("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4", 1.00),
        ("4k3/8/8/8/8/8/8/4K3 w - - 0 1", 0.50),
        ("4k3/8/8/8/8/8/4p3/4K3 w - - 0 1", 0.10),
        ("4k3/8/8/8/8/8/4R3/4K3 w - - 0 1", 0.95),
        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R b KQkq - 0 4", 0.75),
        ("rn1qkb1r/ppp1pppp/5n2/3p4/3P1B2/5N2/PPP1PPPP/RN1QKB1R w KQkq - 2 4", 0.65),
        ("r3k2r/pppq1ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPPQ1PPP/R3K2R w KQkq - 4 7", 0.55),
    ]
    dataset = []
    for fen, result in positions:
        try:
            board = Board.from_fen(fen)
            dataset.append((board, result))
        except Exception:
            pass
    return dataset


def tune_piece_values(dataset, current_values, current_tables, best_mse, verbose=True):
    """Tune PIECE_VALUES using local search."""
    improved = False
    values = dict(current_values)
    for piece_type in sorted(values.keys(), key=lambda pt: pt.value):
        for delta in [1, -1]:
            values[piece_type] += delta
            if values[piece_type] < 1:
                values[piece_type] -= delta
                continue
            new_mse = calculate_mse(dataset, values, current_tables)
            if new_mse < best_mse:
                best_mse = new_mse
                improved = True
                if verbose:
                    print(f"  MSE {best_mse:.8f}  {piece_type.name} = {values[piece_type]}")
            else:
                values[piece_type] -= delta
    return values, best_mse, improved


def tune_pst_entry(dataset, values, tables, piece_type, row, col, best_mse, verbose=True):
    """Tune a single PST entry."""
    improved = False
    table = tables[piece_type]
    for delta in [1, -1]:
        table[row][col] += delta
        new_mse = calculate_mse(dataset, values, tables)
        if new_mse < best_mse:
            best_mse = new_mse
            improved = True
            if verbose:
                alg_file = chr(ord("a") + col)
                alg_rank = 8 - row
                print(f"  MSE {best_mse:.8f}  {piece_type.name}[{alg_file}{alg_rank}] = {table[row][col]}")
        else:
            table[row][col] -= delta
    return best_mse, improved


def tune_piece_tables(dataset, current_values, current_tables, best_mse, verbose=True):
    """Tune all PIECE_TABLES using local search."""
    improved = False
    tables = {}
    for pt, tbl in current_tables.items():
        tables[pt] = [row[:] for row in tbl]
    piece_types = [PieceType.PAWN, PieceType.KNIGHT, PieceType.BISHOP,
                   PieceType.ROOK, PieceType.QUEEN, PieceType.KING]
    for piece_type in piece_types:
        table = tables[piece_type]
        for r in range(8):
            for c in range(8):
                best_mse, imp = tune_pst_entry(
                    dataset, current_values, tables, piece_type, r, c, best_mse, verbose)
                if imp:
                    improved = True
    return tables, best_mse, improved


def tune(dataset, max_passes=10, verbose=True):
    """Run the full tuning optimization.
    
    Alternates between tuning PIECE_VALUES and PIECE_TABLES.
    Returns (optimized_values, optimized_tables, final_mse).
    """
    values = dict(PIECE_VALUES)
    tables = {}
    for pt, tbl in PIECE_TABLES.items():
        tables[pt] = [row[:] for row in tbl]
    best_mse = calculate_mse(dataset, values, tables)
    if verbose:
        print(f"Initial MSE: {best_mse:.8f}")
        print(f"Initial values: {values}")
    for pass_num in range(1, max_passes + 1):
        if verbose:
            print(f"\n--- Pass {pass_num} ---")
        pass_improved = False
        values, best_mse, val_imp = tune_piece_values(
            dataset, values, tables, best_mse, verbose)
        if val_imp:
            pass_improved = True
        tables, best_mse, tbl_imp = tune_piece_tables(
            dataset, values, tables, best_mse, verbose)
        if tbl_imp:
            pass_improved = True
        if not pass_improved:
            if verbose:
                print("Converged.")
            break
    if verbose:
        print(f"\nFinal MSE: {best_mse:.8f}")
    return values, tables, best_mse


def format_values(values):
    """Format PIECE_VALUES as Python code."""
    lines = ["PIECE_VALUES = {"]
    for pt in sorted(values.keys(), key=lambda x: x.value):
        lines.append(f"    PieceType.{pt.name}: {values[pt]},")
    lines.append("}")
    return "\n".join(lines)


def format_table(name, table):
    """Format a PST as Python code."""
    lines = [f"{name} = ["]
    for row in table:
        formatted = ", ".join(f"{v:4d}" for v in row)
        lines.append(f"    [{formatted}],")
    lines.append("]")
    return "\n".join(lines)


def format_tables(tables):
    """Format all PIECE_TABLES as Python code."""
    names = {
        PieceType.PAWN: "PAWN_TABLE",
        PieceType.KNIGHT: "KNIGHT_TABLE",
        PieceType.BISHOP: "BISHOP_TABLE",
        PieceType.ROOK: "ROOK_TABLE",
        PieceType.QUEEN: "QUEEN_TABLE",
        PieceType.KING: "KING_TABLE",
    }
    parts = []
    for pt, name in names.items():
        parts.append(format_table(name, tables[pt]))
    return "\n\n".join(parts)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Texel Tuning")
    parser.add_argument("--dataset", "-d", type=str, default=None)
    parser.add_argument("--passes", "-p", type=int, default=10)
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--synthetic", "-s", action="store_true")
    args = parser.parse_args()
    verbose = not args.quiet
    if args.dataset:
        if not os.path.exists(args.dataset):
            print(f"Error: file not found: {args.dataset}", file=sys.stderr)
            sys.exit(1)
        dataset = load_dataset(args.dataset)
        print(f"Loaded {len(dataset)} positions.")
    elif args.synthetic:
        dataset = generate_synthetic_dataset()
        print(f"Generated {len(dataset)} synthetic positions.")
    else:
        dataset = generate_synthetic_dataset()
        print(f"Using {len(dataset)} synthetic positions.")
    if not dataset:
        print("Error: No valid positions.", file=sys.stderr)
        sys.exit(1)
    values, tables, final_mse = tune(dataset, args.passes, verbose)
    print("\n" + "=" * 60)
    print("Optimized PIECE_VALUES (paste into ai.py):")
    print("=" * 60)
    print(format_values(values))
    print("\n" + "=" * 60)
    print("Optimized PIECE_TABLES (paste into ai.py):")
    print("=" * 60)
    print(format_tables(tables))


if __name__ == "__main__":
    main()
