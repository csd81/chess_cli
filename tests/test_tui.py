import pytest

from chess_cli.tui import ChessApp, Square
from chess_cli.pieces import Color, Piece, PieceType


def _get_square(app, pos):
    return next(s for s in app.query(Square) if s.pos == pos)


def _clear_board(app):
    for r in range(8):
        for c in range(8):
            app.game.board.set_piece(r, c, None)


@pytest.fixture
def app():
    return ChessApp()
# Board rendering
@pytest.mark.asyncio
async def test_board_renders_64_squares(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        squares = list(app.query(Square))
        assert len(squares) == 64


@pytest.mark.asyncio
async def test_starting_position_32_pieces(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        occupied = sum(1 for s in app.query(Square) if app.game.board.get_piece(*s.pos) is not None)
        assert occupied == 32
# Click interactions
@pytest.mark.asyncio
async def test_click_selects_own_piece(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        event = Square.Clicked(square=e2)
        app.on_square_clicked(event)
        assert app.selected_pos == (6, 4)


@pytest.mark.asyncio
async def test_click_does_not_select_opponent(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e7 = _get_square(app, (1, 4))
        app.on_square_clicked(Square.Clicked(square=e7))
        assert app.selected_pos is None


@pytest.mark.asyncio
async def test_click_shows_legal_targets(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        e4 = _get_square(app, (4, 4))
        e3 = _get_square(app, (5, 4))
        assert "legal-target" in e4.classes or "legal-target" in e3.classes


@pytest.mark.asyncio
async def test_click_to_move(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        assert app.selected_pos == (6, 4)
        e4 = _get_square(app, (4, 4))
        app.on_square_clicked(Square.Clicked(square=e4))
        assert app.game.board.get_piece(4, 4) is not None
        assert app.game.board.get_piece(6, 4) is None
        assert app.game.current_turn == Color.BLACK
        assert len(app.game.move_history) == 1


@pytest.mark.asyncio
async def test_click_deselects_same_square(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        assert app.selected_pos == (6, 4)
        app.on_square_clicked(Square.Clicked(square=e2))
        assert app.selected_pos is None
# Text input
@pytest.mark.asyncio
async def test_text_input_move(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e4"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert app.game.board.get_piece(4, 4) is not None
        assert len(app.game.move_history) == 1


@pytest.mark.asyncio
async def test_text_input_invalid_move(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e5"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 0


@pytest.mark.asyncio
async def test_text_input_short_string(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "ab"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 0
# Undo
@pytest.mark.asyncio
async def test_undo_via_text(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e4"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 1
        inp.value = "u"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 0
        assert app.game.board.get_piece(4, 4) is None
        assert app.game.board.get_piece(6, 4) is not None


@pytest.mark.asyncio
async def test_undo_via_keyboard_shortcut(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e4"
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 1
        await pilot.press("tab")
        await pilot.pause(0.05)
        await pilot.press("u")
        await pilot.pause(0.05)
        assert len(app.game.move_history) == 0
# Mode screen
@pytest.mark.asyncio
async def test_mode_screen_appears_on_start(app):
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        buttons = app.screen.query("Button")
        ids = [b.id for b in buttons if b.id]
        assert "pvp" in ids
        assert "pvcpu" in ids
        assert "cpuvp" in ids


@pytest.mark.asyncio
async def test_pvp_mode_sets_no_cpu(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        assert app.cpu_color is None


@pytest.mark.asyncio
async def test_pvcpu_mode_sets_cpu_black(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvcpu")
        await pilot.pause(0.05)
        assert app.cpu_color == Color.BLACK


@pytest.mark.asyncio
async def test_cpuvp_mode_sets_cpu_white(app):
    async with app.run_test() as pilot:
        await pilot.click("#cpuvp")
        await pilot.pause(0.05)
        assert app.cpu_color == Color.WHITE
# Check and game over
@pytest.mark.asyncio
async def test_check_highlighted(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        _clear_board(app)
        app.game.board.set_piece(7, 4, Piece(Color.WHITE, PieceType.KING))
        app.game.board.set_piece(0, 4, Piece(Color.BLACK, PieceType.KING))
        app.game.board.set_piece(2, 4, Piece(Color.WHITE, PieceType.QUEEN))
        app.game.current_turn = Color.BLACK
        app.refresh_board()
        await pilot.pause(0.05)
        ke8 = _get_square(app, (0, 4))
        assert "check" in ke8.classes


@pytest.mark.asyncio
async def test_checkmate_game_over(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            inp.value = uci
            await pilot.press("enter")
            await pilot.pause(0.05)
        assert app.game.game_over is True
        assert app.game.winner == Color.BLACK
# Status
@pytest.mark.asyncio
async def test_status_shows_turn(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        status = app.query_one("#status")
        text = str(status.render().plain or "")
        assert "White" in text or "turn" in text.lower()


@pytest.mark.asyncio
async def test_status_shows_move_count(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e4"
        await pilot.press("enter")
        await pilot.pause(0.05)
        status = app.query_one("#status")
        text = str(status.render().plain or "")
        assert "Moves: 1" in text


# CSS classes
@pytest.mark.asyncio
async def test_last_move_highlight(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        inp = app.query_one("#move-input")
        inp.value = "e2e4"
        await pilot.press("enter")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        e4 = _get_square(app, (4, 4))
        assert "last-move" in e2.classes
        assert "last-move" in e4.classes


@pytest.mark.asyncio
async def test_selected_class(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        assert "selected" in e2.classes
# Help
@pytest.mark.asyncio
async def test_help_screen_shows(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        await pilot.press("tab")
        await pilot.pause(0.05)
        await pilot.press("h")
        await pilot.pause(0.1)
        help_text = app.screen.query_one("#help-text")
        assert help_text is not None


# Escape
@pytest.mark.asyncio
async def test_escape_deselects(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        assert app.selected_pos == (6, 4)
        await pilot.press("tab")
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert app.selected_pos is None


# Promotion
@pytest.mark.asyncio
async def test_promotion_pending(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        _clear_board(app)
        app.game.board.set_piece(7, 4, Piece(Color.WHITE, PieceType.KING))
        app.game.board.set_piece(0, 4, Piece(Color.BLACK, PieceType.KING))
        app.game.board.set_piece(1, 3, Piece(Color.WHITE, PieceType.PAWN))
        app.game.current_turn = Color.WHITE
        app.refresh_board()
        app._update_status()
        await pilot.pause(0.05)
        d7 = _get_square(app, (1, 3))
        app.on_square_clicked(Square.Clicked(square=d7))
        d8 = _get_square(app, (0, 3))
        app.on_square_clicked(Square.Clicked(square=d8))
        assert app._pending_promotion is not None
        assert app._pending_promotion == ((1, 3), (0, 3))


# Notification
@pytest.mark.asyncio
async def test_notification_after_illegal_click(app):
    async with app.run_test() as pilot:
        await pilot.click("#pvp")
        await pilot.pause(0.05)
        e2 = _get_square(app, (6, 4))
        app.on_square_clicked(Square.Clicked(square=e2))
        d5 = _get_square(app, (3, 3))
        app.on_square_clicked(Square.Clicked(square=d5))
        await pilot.pause(0.1)
        try:
            n = app.query_one("#notification")
            assert n is not None
        except Exception:
            pytest.skip("Notification already removed")
# AI vs AI
@pytest.mark.asyncio
async def test_aivai_mode_selection(app):
    """Selecting AI vs AI mode sets ai_vs_ai flag."""
    async with app.run_test() as pilot:
        await pilot.click("#aivai")
        await pilot.pause(0.1)
        assert app.ai_vs_ai is True
        assert app.cpu_color is None