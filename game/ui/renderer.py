# renderer.py – Map and HUD rendering

import math
import pygame
from typing import Dict, Optional, Tuple, List
from ..core.constants import *
from ..core.hex_grid import hex_to_pixel, hexagon_points, hex_neighbors, hex_distance, hex_reachable
from ..core.units import UNIT_TYPES, Unit
from ..core.factions import FACTIONS
from ..core.game_state import GameState


class Fonts:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        pygame.font.init()
        self.tiny   = pygame.font.SysFont("monospace", 11)
        self.small  = pygame.font.SysFont("monospace", 13)
        self.normal = pygame.font.SysFont("monospace", 15)
        self.medium = pygame.font.SysFont("monospace", 17)
        self.large  = pygame.font.SysFont("monospace", 22, bold=True)
        self.title  = pygame.font.SysFont("monospace", 28, bold=True)
        self.symbol = pygame.font.SysFont("monospace", 18, bold=True)


class MapRenderer:
    """Renders the hex map, units, overlays."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.fonts = Fonts.get()
        # Camera offset
        self.cam_x = 0
        self.cam_y = 0
        # Selection state
        self.selected_unit: Optional[Unit] = None
        self.reachable_hexes: List[Tuple[int,int]] = []
        self.hover_hex: Optional[Tuple[int,int]] = None

    def update_reachable(self, gs: GameState):
        """Recalculate reachable hexes for selected unit."""
        if self.selected_unit and self.selected_unit.alive:
            u = self.selected_unit
            self.reachable_hexes = hex_reachable(
                u.col, u.row, u.moves_left, gs.grid)
        else:
            self.reachable_hexes = []

    def draw(self, gs: GameState):
        # Map viewport surface
        map_surf = self.screen.subsurface(
            (MAP_X, MAP_Y, MAP_W, MAP_H))
        map_surf.fill(C_BG)

        # Draw all hexes
        for (c, r), tile in gs.grid.items():
            self._draw_hex(map_surf, c, r, tile, gs)

        # Draw movement overlay
        if self.selected_unit:
            for (c, r) in self.reachable_hexes:
                px, py = hex_to_pixel(c, r)
                px -= MAP_X
                py -= MAP_Y
                pts = hexagon_points(px, py, HEX_SIZE - 2)
                surf = pygame.Surface((HEX_SIZE*2, HEX_SIZE*2), pygame.SRCALPHA)
                pygame.draw.polygon(surf, (80, 200, 255, 60), [
                    (p[0] - px + HEX_SIZE, p[1] - py + HEX_SIZE) for p in pts])
                map_surf.blit(surf, (px - HEX_SIZE, py - HEX_SIZE))

        # Oil pipeline marker
        if gs.oil_pipeline_hex:
            pc, pr = gs.oil_pipeline_hex
            px, py = hex_to_pixel(pc, pr)
            px -= MAP_X; py -= MAP_Y
            if gs.grid[(pc, pr)].visible:
                pygame.draw.circle(map_surf, (220, 180, 40), (px, py), 8, 2)
                txt = self.fonts.tiny.render("PIPE", True, (220, 180, 40))
                map_surf.blit(txt, (px - 14, py - 24))

        # Draw units
        for unit in gs.all_units.values():
            tile = gs.grid.get((unit.col, unit.row))
            if tile and (tile.visible or unit.owner != F_PLAYER):
                # Only show non-player units if visible
                if unit.owner != F_PLAYER and not tile.visible:
                    continue
                self._draw_unit(map_surf, unit, gs)

        # Hover highlight
        if self.hover_hex:
            c, r = self.hover_hex
            px, py = hex_to_pixel(c, r)
            px -= MAP_X; py -= MAP_Y
            pts = hexagon_points(px, py, HEX_SIZE - 1)
            pygame.draw.polygon(map_surf, C_HIGHLIGHT, pts, 2)

        # Selected unit highlight
        if self.selected_unit and self.selected_unit.alive:
            u = self.selected_unit
            px, py = hex_to_pixel(u.col, u.row)
            px -= MAP_X; py -= MAP_Y
            pts = hexagon_points(px, py, HEX_SIZE - 1)
            pygame.draw.polygon(map_surf, C_SELECT, pts, 3)

    def _draw_hex(self, surf, c, r, tile, gs):
        px, py = hex_to_pixel(c, r)
        px -= MAP_X; py -= MAP_Y
        pts = hexagon_points(px, py, HEX_SIZE)

        # Base terrain color
        color = tile.color
        if not tile.explored:
            color = (15, 18, 22)  # Unexplored = dark
        elif not tile.visible:
            # Darken explored but not visible tiles
            color = tuple(max(0, v // 3) for v in color)

        pygame.draw.polygon(surf, color, pts)

        # Owner tint (thin border)
        if tile.owner and tile.visible:
            owner_color = FACTIONS.get(tile.owner, None)
            if owner_color:
                oc = FACTIONS[tile.owner].color
                pygame.draw.polygon(surf, oc, pts, 2)

        # Hex outline
        pygame.draw.polygon(surf, (40, 45, 55), pts, 1)

        if not tile.visible:
            return

        # POI label
        if tile.poi:
            fnt = self.fonts.tiny
            txt = fnt.render(tile.poi[:8], True, (240, 240, 200))
            surf.blit(txt, (px - txt.get_width() // 2, py + HEX_SIZE // 2 - 4))

        # Terrain symbol
        sym_map = {
            "jungle": "J", "mountain": "^", "river": "~",
            "coast": "≈", "city": "⌂", "village": "▲"
        }
        sym = sym_map.get(tile.terrain, "")
        if sym:
            fnt = self.fonts.tiny
            txt = fnt.render(sym, True, (200, 200, 180))
            surf.blit(txt, (px - txt.get_width() // 2, py - 8))

    def _draw_unit(self, surf, unit: Unit, gs: GameState):
        px, py = hex_to_pixel(unit.col, unit.row)
        px -= MAP_X; py -= MAP_Y

        # Stack offset: if multiple units in same hex
        tile = gs.grid.get((unit.col, unit.row))
        if tile:
            idx = tile.units.index(unit.id) if unit.id in tile.units else 0
            px += (idx % 3) * 8 - 8
            py += (idx // 3) * 8 - 4

        utype = UNIT_TYPES[unit.type_id]
        fdef = FACTIONS.get(unit.owner)
        color = fdef.color if fdef else (180, 180, 180)

        # Unit circle
        radius = 12
        pygame.draw.circle(surf, color, (px, py), radius)
        pygame.draw.circle(surf, (255, 255, 255), (px, py), radius, 1)

        # Symbol
        sym = self.fonts.symbol.render(utype.symbol.upper(), True, (255, 255, 255))
        surf.blit(sym, (px - sym.get_width() // 2, py - sym.get_height() // 2))

        # HP bar
        bar_w = 20
        bar_h = 3
        hp_frac = unit.hp / unit.hp_max
        bar_color = (100, 220, 100) if hp_frac > 0.5 else \
                    (220, 200, 60) if hp_frac > 0.25 else (220, 80, 60)
        pygame.draw.rect(surf, (60, 60, 60), (px - bar_w//2, py + radius + 1, bar_w, bar_h))
        pygame.draw.rect(surf, bar_color, (px - bar_w//2, py + radius + 1,
                                           int(bar_w * hp_frac), bar_h))

        # Veteran star
        if unit.veteran:
            star = self.fonts.tiny.render("★", True, (255, 220, 0))
            surf.blit(star, (px + radius - 4, py - radius - 4))

        # Acted indicator
        if unit.has_acted and unit.owner == F_PLAYER:
            acted = self.fonts.tiny.render("•", True, (150, 150, 150))
            surf.blit(acted, (px - 4, py - radius - 4))


class HUDRenderer:
    """Renders sidebar and bottom panel."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.fonts = Fonts.get()

    def draw_sidebar(self, gs: GameState, selected_unit: Optional[Unit],
                     hover_hex: Optional[Tuple[int, int]]):
        # Background
        pygame.draw.rect(self.screen, C_PANEL_BG, (0, 0, SIDEBAR_W, SCREEN_H))
        pygame.draw.line(self.screen, C_PANEL_BORD, (SIDEBAR_W, 0), (SIDEBAR_W, SCREEN_H))

        y = 8
        # Title
        title = self.fonts.large.render("FACTIONS", True, C_TEXT)
        self.screen.blit(title, (SIDEBAR_W // 2 - title.get_width() // 2, y))
        y += 30
        sub = self.fonts.small.render("Cold War Shadow War", True, C_TEXT_DIM)
        self.screen.blit(sub, (SIDEBAR_W // 2 - sub.get_width() // 2, y))
        y += 24

        # Turn / profile
        pygame.draw.line(self.screen, C_PANEL_BORD, (8, y), (SIDEBAR_W - 8, y))
        y += 6
        turn_txt = self.fonts.normal.render(f"Turn {gs.turn}/{MAX_TURNS}", True, C_TEXT)
        self.screen.blit(turn_txt, (8, y))
        y += 20

        profile_color = {PROFILE_LOW: C_TEXT_GOOD, PROFILE_MEDIUM: C_TEXT_WARN,
                         PROFILE_HIGH: C_TEXT_BAD}[gs.profile_level]
        profile_txt = self.fonts.small.render(
            f"Profile: {gs.profile_level.upper()} ({gs.player_profile_score})",
            True, profile_color)
        self.screen.blit(profile_txt, (8, y))
        y += 20

        # Government HP
        gov_frac = gs.government_hp / 100
        gov_bar_w = SIDEBAR_W - 16
        pygame.draw.rect(self.screen, (60, 60, 70), (8, y, gov_bar_w, 10))
        gov_color = (100, 140, 200) if gov_frac > 0.5 else \
                    (200, 180, 60) if gov_frac > 0.25 else (220, 80, 60)
        pygame.draw.rect(self.screen, gov_color, (8, y, int(gov_bar_w * gov_frac), 10))
        gov_lbl = self.fonts.tiny.render(f"Govt: {gs.government_hp}%", True, C_TEXT_DIM)
        self.screen.blit(gov_lbl, (8, y + 12))
        y += 28

        # Resources
        pygame.draw.line(self.screen, C_PANEL_BORD, (8, y), (SIDEBAR_W - 8, y))
        y += 6
        res_lbl = self.fonts.small.render("RESOURCES", True, C_TEXT_DIM)
        self.screen.blit(res_lbl, (8, y))
        y += 18
        res_items = [
            (RES_FUNDS,     "Funds",     "$"),
            (RES_RECRUITS,  "Recruits",  "R"),
            (RES_WEAPONS,   "Weapons",   "W"),
            (RES_INTEL,     "Intel",     "I"),
        ]
        for res_id, label, sym in res_items:
            val = gs.resources.get(res_id, 0)
            line = self.fonts.small.render(f"  {sym} {label}: {val}", True, C_TEXT)
            self.screen.blit(line, (8, y))
            y += 16
        inf_txt = self.fonts.small.render(f"  ★ Influence: {gs.player_influence}", True, C_TEXT_WARN)
        self.screen.blit(inf_txt, (8, y))
        y += 20

        # Factions
        pygame.draw.line(self.screen, C_PANEL_BORD, (8, y), (SIDEBAR_W - 8, y))
        y += 6
        fac_lbl = self.fonts.small.render("FACTION RELATIONS", True, C_TEXT_DIM)
        self.screen.blit(fac_lbl, (8, y))
        y += 18
        show_facs = [F_EAGLE, F_BEAR, F_CROSS, F_OIL, F_JAGUAR, F_GOV]
        for fid in show_facs:
            rel = gs.rels.get(F_PLAYER, fid)
            label = gs.rels.get_label(rel)
            color = gs.rels.get_label_color(rel)
            fdef = FACTIONS[fid]
            # Bar
            bar_w = 80
            bar_x = SIDEBAR_W - bar_w - 8
            frac = (rel + 100) / 200
            bar_color = (int(200 * (1 - frac)), int(200 * frac), 80)
            pygame.draw.rect(self.screen, (50, 55, 65), (bar_x, y + 2, bar_w, 10))
            pygame.draw.rect(self.screen, bar_color, (bar_x, y + 2, int(bar_w * frac), 10))
            name_txt = self.fonts.tiny.render(f"{fdef.short}", True, fdef.color)
            self.screen.blit(name_txt, (8, y))
            rel_txt = self.fonts.tiny.render(f"{rel:+d} {label[:4]}", True, color)
            self.screen.blit(rel_txt, (40, y))
            y += 16

        # Selected unit info
        y += 4
        pygame.draw.line(self.screen, C_PANEL_BORD, (8, y), (SIDEBAR_W - 8, y))
        y += 6
        if selected_unit and selected_unit.alive:
            self._draw_unit_panel(y, selected_unit)
        elif hover_hex:
            self._draw_hex_panel(y, hover_hex, gs)

    def _draw_unit_panel(self, y: int, unit: Unit):
        utype = UNIT_TYPES[unit.type_id]
        fdef = FACTIONS.get(unit.owner)
        hdr = self.fonts.medium.render(utype.name, True,
                                       fdef.color if fdef else C_TEXT)
        self.screen.blit(hdr, (8, y))
        y += 20
        lines = [
            f"HP:    {unit.hp}/{unit.hp_max}",
            f"Atk:   {unit.attack}  Def: {unit.defense}",
            f"Move:  {unit.moves_left}/{unit.move}",
            f"Sight: {unit.sight}  Stealth: {unit.stealth}",
            f"XP:    {unit.experience}{'  [VET]' if unit.veteran else ''}",
        ]
        for line in lines:
            t = self.fonts.small.render(line, True, C_TEXT)
            self.screen.blit(t, (8, y))
            y += 16
        # Description
        desc_words = utype.description.split()
        line_buf = ""
        for w in desc_words:
            if len(line_buf) + len(w) > 28:
                t = self.fonts.tiny.render(line_buf, True, C_TEXT_DIM)
                self.screen.blit(t, (8, y))
                y += 13
                line_buf = w + " "
            else:
                line_buf += w + " "
        if line_buf:
            t = self.fonts.tiny.render(line_buf, True, C_TEXT_DIM)
            self.screen.blit(t, (8, y))

    def _draw_hex_panel(self, y: int, hover_hex: Tuple[int,int], gs: GameState):
        c, r = hover_hex
        tile = gs.grid.get((c, r))
        if not tile or not tile.explored:
            return
        hdr = self.fonts.medium.render(tile.name, True, C_TEXT)
        self.screen.blit(hdr, (8, y))
        y += 20
        if tile.poi:
            poi_txt = self.fonts.small.render(tile.poi, True, C_TEXT_WARN)
            self.screen.blit(poi_txt, (8, y))
            y += 18
        owner_name = FACTIONS[tile.owner].name if tile.owner in FACTIONS else "Neutral"
        lines = [
            f"Owner:   {owner_name[:14]}",
            f"Conceal: {'▮' * tile.conceal_bonus}{'▯' * (3 - tile.conceal_bonus)}",
            f"Move:    {tile.move_cost}AP",
        ]
        for line in lines:
            t = self.fonts.small.render(line, True, C_TEXT)
            self.screen.blit(t, (8, y))
            y += 16
        if tile.population:
            pop_txt = self.fonts.small.render(f"Pop: {tile.population // 1000}k", True, C_TEXT_DIM)
            self.screen.blit(pop_txt, (8, y))

    def draw_bottom_panel(self, gs: GameState, log_offset: int = 0):
        panel_y = SCREEN_H - BOTTOM_H
        pygame.draw.rect(self.screen, C_PANEL_BG, (MAP_X, panel_y, MAP_W, BOTTOM_H))
        pygame.draw.line(self.screen, C_PANEL_BORD,
                         (MAP_X, panel_y), (SCREEN_W, panel_y))
        # Log header
        lbl = self.fonts.small.render("ACTIVITY LOG", True, C_TEXT_DIM)
        self.screen.blit(lbl, (MAP_X + 8, panel_y + 4))
        # Log lines (most recent at bottom)
        visible_lines = 8
        log_lines = gs.log[-(visible_lines + log_offset):len(gs.log) - log_offset
                           if log_offset > 0 else None]
        y = panel_y + 18
        for line in log_lines[-visible_lines:]:
            # Colour based on keywords
            color = C_TEXT_DIM
            if any(k in line.lower() for k in ("victory", "unlock", "veteran")):
                color = C_TEXT_GOOD
            elif any(k in line.lower() for k in ("defeat", "lost", "destroy")):
                color = C_TEXT_BAD
            elif any(k in line.lower() for k in ("warning", "profile", "bribed")):
                color = C_TEXT_WARN
            txt = self.fonts.tiny.render(line[:100], True, color)
            self.screen.blit(txt, (MAP_X + 8, y))
            y += 13
