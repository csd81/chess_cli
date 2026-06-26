"""Piece definitions and movement rules for chess."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    def opponent(self) -> "Color":
        return Color.BLACK if self == Color.WHITE else Color.WHITE


class PieceType(Enum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


@dataclass
class Piece:
    """Represents a single chess piece."""
    color: Color
    piece_type: PieceType
    has_moved: bool = False

    def __str__(self) -> str:
        symbols = {
            (Color.WHITE, PieceType.KING): "K",
            (Color.WHITE, PieceType.QUEEN): "Q",
            (Color.WHITE, PieceType.ROOK): "R",
            (Color.WHITE, PieceType.BISHOP): "B",
            (Color.WHITE, PieceType.KNIGHT): "N",
            (Color.WHITE, PieceType.PAWN): "P",
            (Color.BLACK, PieceType.KING): "k",
            (Color.BLACK, PieceType.QUEEN): "q",
            (Color.BLACK, PieceType.ROOK): "r",
            (Color.BLACK, PieceType.BISHOP): "b",
            (Color.BLACK, PieceType.KNIGHT): "n",
            (Color.BLACK, PieceType.PAWN): "p",
        }
        return symbols.get((self.color, self.piece_type), "?")

    def __repr__(self) -> str:
        return f"Piece({self.color.value}, {self.piece_type.value}, moved={self.has_moved})"

    def letter(self) -> str:
        """Return the algebraic notation letter for this piece."""
        mapping = {
            PieceType.KING: "K",
            PieceType.QUEEN: "Q",
            PieceType.ROOK: "R",
            PieceType.BISHOP: "B",
            PieceType.KNIGHT: "N",
            PieceType.PAWN: "",
        }
        return mapping.get(self.piece_type, "")

    def fen_letter(self) -> str:
        """Return the FEN character for this piece (e.g. 'P' for white pawn, 'p' for black)."""
        mapping = {
            PieceType.KING: "K",
            PieceType.QUEEN: "Q",
            PieceType.ROOK: "R",
            PieceType.BISHOP: "B",
            PieceType.KNIGHT: "N",
            PieceType.PAWN: "P",
        }
        letter = mapping.get(self.piece_type, "?")
        return letter if self.color == Color.WHITE else letter.lower()

    @staticmethod
    def from_letter(letter: str, color: Color) -> Optional["Piece"]:
        """Create a piece from a FEN-style letter (e.g. 'P' for white pawn)."""
        mapping = {
            "K": PieceType.KING,
            "Q": PieceType.QUEEN,
            "R": PieceType.ROOK,
            "B": PieceType.BISHOP,
            "N": PieceType.KNIGHT,
            "P": PieceType.PAWN,
        }
        pt = mapping.get(letter.upper())
        if pt is None:
            return None
        return Piece(color=color, piece_type=pt)
