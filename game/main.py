# main.py – Game entry point and main loop

import sys
import os
import pygame

# Make game_state_ref accessible to panels that need it
import game_state_ref

from .core.constants import *
from .core.game_state import GameState
from .core.units import UNIT_TYPES, Unit
from .core.factions import FACTIONS
from .core.hex_grid import hex_to_pixel, pixel_to_hex, hex_distance
from .ui.renderer import MapRenderer, HUDRenderer, Fonts
from .ui.panels import (
    Button, EventPanel, RecruitPanel, DiplomacyPanel,
    TooltipRenderer, HelpPanel, GameOverPanel
)
from .ui.faction_chooser import FactionChooser


def make_end_turn_button() -> Button:
    return Button(
        rect=pygame.Rect(SCREEN_W - 140, SCREEN_H - BOTTOM_H + 4, 130, 34),
        label="End Turn →",
        color=C_BUTTON_ACT,
        text_color=C_TEXT,
    )


def make_toolbar_buttons() -> dict:
    """Create the action toolbar buttons."""
    base_y = SCREEN_H - BOTTOM_H + 42
    buttons = {}
    defs = [
        ("recruit",   "Recruit [R]",    MAP_X + 10),
        ("diplomacy", "Diplomacy [D]",  MAP_X + 110),
        ("wait",      "Wait [W]",       MAP_X + 220),
        ("help",      "Help [H]",       MAP_X + 320),
    ]
    for key, label, x in defs:
        buttons[key] = Button(
            rect=pygame.Rect(x, base_y, 92, 28),
            label=label,
        )
    return buttons


def run_game(seed: int = 42):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    fonts = Fonts.get()

    gs = GameState(seed=seed)
    game_state_ref.GS = gs

    map_renderer = MapRenderer(screen)
    hud = HUDRenderer(screen)

    event_panel    = EventPanel()
    recruit_panel  = RecruitPanel()
    diplo_panel    = DiplomacyPanel()
    fac_chooser    = FactionChooser()
    help_panel     = HelpPanel()
    gameover_panel = GameOverPanel()
    tooltip        = TooltipRenderer()

    end_turn_btn = make_end_turn_button()
    toolbar_btns = make_toolbar_buttons()

    # State
    selected_unit: Unit = None
    log_offset = 0
    message_popup: list = []   # [text, timer]

    # Sidebar clickable faction areas (approximate y positions)
    SIDEBAR_FAC_Y0 = 232   # first faction row y coordinate
    SIDEBAR_FAC_H  = 16    # row height
    SIDEBAR_FACS   = [F_EAGLE, F_BEAR, F_CROSS, F_OIL, F_JAGUAR, F_GOV]

    def show_message(text: str, duration: int = 180):
        message_popup.append([text, duration])
        if len(message_popup) > 4:
            message_popup.pop(0)

    def select_unit(unit):
        nonlocal selected_unit
        selected_unit = unit
        map_renderer.selected_unit = unit
        map_renderer.update_reachable(gs)

    def deselect():
        nonlocal selected_unit
        selected_unit = None
        map_renderer.selected_unit = None
        map_renderer.reachable_hexes = []

    def open_diplomacy(faction_id: str):
        diplo_panel.show_for_faction(faction_id, gs)

    def open_faction_chooser():
        fac_chooser.show(gs)

    help_panel.show()

    running = True
    while running:
        clock.tick(FPS)

        # ── Event handling ────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # Game over panel
            if gameover_panel.visible:
                if gameover_panel.handle_event(event):
                    gs = GameState(seed=seed + gs.turn)
                    game_state_ref.GS = gs
                    gameover_panel.visible = False
                    deselect()
                    show_message("New game started!")
                continue

            # Help panel
            if help_panel.handle_event(event):
                continue

            # Faction chooser
            if fac_chooser.visible:
                result = fac_chooser.handle_event(event)
                if result and result != "cancel":
                    open_diplomacy(result)
                continue

            # Modal panels
            if event_panel.visible:
                result = event_panel.handle_event(event, gs)
                if result:
                    show_message(result[:90])
                continue

            if recruit_panel.visible:
                result = recruit_panel.handle_event(event, gs)
                if result and result != "closed":
                    show_message(result[:90])
                continue

            if diplo_panel.visible:
                result = diplo_panel.handle_event(event, gs)
                if result and result != "closed":
                    show_message(result[:90])
                continue

            # ── Keyboard ──────────────────────────────────────────────────
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h:
                    help_panel.show()

                elif event.key == pygame.K_ESCAPE:
                    deselect()

                elif event.key == pygame.K_r:
                    target = None
                    if selected_unit and selected_unit.owner == F_PLAYER:
                        target = (selected_unit.col, selected_unit.row)
                    elif map_renderer.hover_hex:
                        hx, hy = map_renderer.hover_hex
                        if gs.grid[(hx, hy)].owner == F_PLAYER:
                            target = (hx, hy)
                    if target:
                        recruit_panel.show_for_hex(target[0], target[1], gs)
                    else:
                        show_message("Select a player-controlled hex to recruit.")

                elif event.key == pygame.K_d:
                    open_faction_chooser()

                elif event.key == pygame.K_s and selected_unit:
                    # Subvert: key shortcut for cell units
                    if selected_unit.owner == F_PLAYER and selected_unit.utype.can_subvert:
                        result = gs.subvert_village(selected_unit)
                        show_message(result)
                        map_renderer.update_reachable(gs)

                elif event.key == pygame.K_w:
                    if selected_unit and selected_unit.owner == F_PLAYER:
                        selected_unit.has_acted = True
                        selected_unit.moves_left = 0
                        show_message(f"{selected_unit.utype.name} waits.")
                        deselect()

                elif event.key in (pygame.K_RETURN, pygame.K_END, pygame.K_SPACE):
                    _do_end_turn(gs, selected_unit, deselect, show_message,
                                 event_panel, gameover_panel)

                elif event.key == pygame.K_UP:
                    log_offset = min(log_offset + 1, max(0, len(gs.log) - 8))
                elif event.key == pygame.K_DOWN:
                    log_offset = max(log_offset - 1, 0)

            # ── Mouse motion ──────────────────────────────────────────────
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if MAP_X <= mx < SCREEN_W and MAP_Y <= my < SCREEN_H - BOTTOM_H:
                    hx, hy = pixel_to_hex(mx, my)
                    if 0 <= hx < MAP_COLS and 0 <= hy < MAP_ROWS:
                        map_renderer.hover_hex = (hx, hy)
                        tile = gs.grid[(hx, hy)]
                        if tile.visible and tile.units:
                            uid = tile.units[0]
                            u = gs.all_units.get(uid)
                            if u:
                                utype = UNIT_TYPES[u.type_id]
                                fdef = FACTIONS.get(u.owner)
                                owner_name = fdef.name if fdef else u.owner
                                tip_lines = [
                                    f"{utype.name}",
                                    f"HP {u.hp}/{u.hp_max}  Atk {u.attack}  Def {u.defense}",
                                    f"Move {u.moves_left}/{u.move}  Stealth {u.stealth}",
                                    f"Owner: {owner_name}",
                                ]
                                if u.veteran:
                                    tip_lines.append("★ Veteran")
                                tooltip.show("\n".join(tip_lines), (mx + 14, my - 10))
                            else:
                                tooltip.hide()
                        elif tile.explored:
                            # Show terrain info
                            owner_name = FACTIONS[tile.owner].name if tile.owner in FACTIONS else "Neutral"
                            tip_lines = [
                                f"{tile.name}{' – ' + tile.poi if tile.poi else ''}",
                                f"Owner: {owner_name}",
                                f"Move cost: {tile.move_cost}  Concealment: {tile.conceal_bonus}",
                            ]
                            tooltip.show("\n".join(tip_lines), (mx + 14, my - 10))
                        else:
                            tooltip.hide()
                    else:
                        map_renderer.hover_hex = None
                        tooltip.hide()
                else:
                    map_renderer.hover_hex = None
                    tooltip.hide()

            # ── Mouse click ───────────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                # Toolbar
                for key, btn in toolbar_btns.items():
                    if btn.handle_event(event):
                        _handle_toolbar(key, gs, map_renderer, selected_unit,
                                        recruit_panel, open_faction_chooser,
                                        help_panel, show_message, deselect)

                # End turn
                if end_turn_btn.handle_event(event):
                    _do_end_turn(gs, selected_unit, deselect, show_message,
                                 event_panel, gameover_panel)

                # Sidebar faction clicks
                if mx < SIDEBAR_W and event.button == 1:
                    for i, fid in enumerate(SIDEBAR_FACS):
                        row_y = SIDEBAR_FAC_Y0 + i * SIDEBAR_FAC_H
                        if row_y <= my < row_y + SIDEBAR_FAC_H:
                            open_diplomacy(fid)
                            break

                # Map area clicks
                if MAP_X <= mx < SCREEN_W and MAP_Y <= my < SCREEN_H - BOTTOM_H:
                    hx, hy = pixel_to_hex(mx, my)
                    if 0 <= hx < MAP_COLS and 0 <= hy < MAP_ROWS:
                        tile = gs.grid[(hx, hy)]

                        if event.button == 1:   # Left = select
                            found = None
                            for uid in tile.units:
                                u = gs.all_units.get(uid)
                                if u and u.owner == F_PLAYER:
                                    found = u
                                    break
                            if found:
                                select_unit(found)
                                show_message(f"Selected {found.utype.name}")
                            else:
                                deselect()

                        elif event.button == 3:  # Right = action
                            if selected_unit and selected_unit.owner == F_PLAYER:
                                enemy_here = None
                                for uid in tile.units:
                                    u = gs.all_units.get(uid)
                                    if u and u.owner != F_PLAYER:
                                        enemy_here = u
                                        break

                                if enemy_here:
                                    result = gs.attack_unit(selected_unit, enemy_here)
                                    show_message(result[:90])
                                    map_renderer.update_reachable(gs)
                                    if not selected_unit.alive:
                                        deselect()
                                elif (hx, hy) in map_renderer.reachable_hexes:
                                    result = gs.move_unit(selected_unit, hx, hy)
                                    show_message(result)
                                    map_renderer.update_reachable(gs)
                                elif (tile.terrain in ("village", "city") and
                                      selected_unit.utype.can_subvert and
                                      selected_unit.col == hx and selected_unit.row == hy):
                                    result = gs.subvert_village(selected_unit)
                                    show_message(result)
                                    map_renderer.update_reachable(gs)
                                else:
                                    show_message("Out of range or no action available.")

            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if my > SCREEN_H - BOTTOM_H:
                    log_offset = max(0, min(log_offset - event.y,
                                            max(0, len(gs.log) - 8)))

        # ── Pending event ─────────────────────────────────────────────────
        if gs.pending_event and not event_panel.visible:
            event_panel.show_event(gs.pending_event, gs)
            gs.pending_event = None

        # ── Draw ──────────────────────────────────────────────────────────
        screen.fill(C_BG)
        map_renderer.draw(gs)
        hud.draw_sidebar(gs, selected_unit, map_renderer.hover_hex)
        hud.draw_bottom_panel(gs, log_offset)

        # Toolbar buttons
        for btn in toolbar_btns.values():
            btn.draw(screen, fonts)
        end_turn_btn.draw(screen, fonts)

        # Panels (order matters – later = on top)
        fac_chooser.draw(screen, fonts)
        event_panel.draw(screen, fonts)
        recruit_panel.draw(screen, fonts)
        diplo_panel.draw(screen, fonts)
        help_panel.draw(screen, fonts)
        gameover_panel.draw(screen, fonts)

        # HUD overlays
        _draw_messages(screen, fonts, message_popup)
        tooltip.draw(screen, fonts)

        # Ceasefire banner
        if gs.peace_talks_ceasefire > 0:
            cf_txt = fonts.small.render(
                f"  ✦ CEASEFIRE ACTIVE: {gs.peace_talks_ceasefire} turns remaining  ",
                True, C_TEXT_GOOD)
            bg = pygame.Surface((cf_txt.get_width(), cf_txt.get_height()))
            bg.fill((20, 50, 30))
            screen.blit(bg, (MAP_X + MAP_W // 2 - cf_txt.get_width() // 2, 4))
            screen.blit(cf_txt, (MAP_X + MAP_W // 2 - cf_txt.get_width() // 2, 4))

        # Turn indicator in corner
        turn_indicator = fonts.small.render(
            f"Turn {gs.turn}/{MAX_TURNS}", True, C_TEXT_DIM)
        screen.blit(turn_indicator, (SCREEN_W - 120, 4))

        pygame.display.flip()

    pygame.quit()


def _handle_toolbar(key, gs, map_renderer, selected_unit,
                    recruit_panel, open_faction_chooser,
                    help_panel, show_message, deselect):
    if key == "recruit":
        target = None
        if map_renderer.hover_hex:
            hx, hy = map_renderer.hover_hex
            if gs.grid[(hx, hy)].owner == F_PLAYER:
                target = (hx, hy)
        if selected_unit and selected_unit.owner == F_PLAYER and not target:
            target = (selected_unit.col, selected_unit.row)
        if target:
            recruit_panel.show_for_hex(target[0], target[1], gs)
        else:
            show_message("Select a player-controlled hex first.")
    elif key == "diplomacy":
        open_faction_chooser()
    elif key == "wait":
        if selected_unit and selected_unit.owner == F_PLAYER:
            selected_unit.has_acted = True
            selected_unit.moves_left = 0
            show_message(f"{selected_unit.utype.name} waits.")
            deselect()
    elif key == "help":
        help_panel.show()


def _do_end_turn(gs, selected_unit, deselect_fn, show_message_fn,
                 event_panel, gameover_panel):
    deselect_fn()
    msgs = gs.end_player_turn()
    for msg in msgs[-4:]:
        show_message_fn(msg[:100])
    if gs.game_over:
        gameover_panel.show_result(gs.win_condition, gs)


def _draw_messages(screen, fonts, message_popup):
    y = MAP_Y + 40
    remaining = []
    for item in message_popup:
        text, timer = item
        if timer > 0:
            alpha = min(255, timer * 5)
            r_val = min(255, alpha)
            txt = fonts.normal.render(text, True, (r_val, r_val, r_val))
            w = txt.get_width() + 18
            h = txt.get_height() + 8
            x = MAP_X + MAP_W // 2 - w // 2
            bg = pygame.Surface((w, h), pygame.SRCALPHA)
            bg.fill((15, 20, 30, min(210, alpha)))
            screen.blit(bg, (x, y))
            screen.blit(txt, (x + 9, y + 4))
            y += h + 4
            item[1] -= 3
            remaining.append(item)
    message_popup[:] = remaining
