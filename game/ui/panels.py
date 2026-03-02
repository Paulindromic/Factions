# panels.py – Popup panels, dialogs, menus

import pygame
from typing import List, Optional, Tuple, Callable
from ..core.constants import *
from ..core.factions import FACTIONS
from ..core.units import UNIT_TYPES
from .renderer import Fonts


class Button:
    def __init__(self, rect: pygame.Rect, label: str, tooltip: str = "",
                 enabled: bool = True, color=C_BUTTON, text_color=C_TEXT):
        self.rect = rect
        self.label = label
        self.tooltip = tooltip
        self.enabled = enabled
        self.color = color
        self.text_color = text_color
        self.hovered = False

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        color = (self.color if self.enabled
                 else tuple(v // 2 for v in self.color))
        if self.hovered and self.enabled:
            color = C_BUTTON_HOV
        pygame.draw.rect(surf, color, self.rect, border_radius=4)
        pygame.draw.rect(surf, C_PANEL_BORD, self.rect, 1, border_radius=4)
        lbl = fonts.small.render(self.label, True,
                                 self.text_color if self.enabled else C_TEXT_DIM)
        surf.blit(lbl, (self.rect.centerx - lbl.get_width() // 2,
                        self.rect.centery - lbl.get_height() // 2))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if clicked."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.enabled:
                return True
        return False


class Panel:
    """Base popup panel."""
    def __init__(self, rect: pygame.Rect, title: str):
        self.rect = rect
        self.title = title
        self.visible = False
        self.buttons: List[Button] = []

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def draw_base(self, surf: pygame.Surface, fonts: Fonts):
        pygame.draw.rect(surf, C_PANEL_BG, self.rect, border_radius=6)
        pygame.draw.rect(surf, C_PANEL_BORD, self.rect, 2, border_radius=6)
        title_surf = fonts.medium.render(self.title, True, C_TEXT)
        surf.blit(title_surf, (self.rect.x + 10, self.rect.y + 8))
        pygame.draw.line(surf, C_PANEL_BORD,
                         (self.rect.x + 8, self.rect.y + 28),
                         (self.rect.right - 8, self.rect.y + 28))

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible:
            return
        self.draw_base(surf, fonts)
        for btn in self.buttons:
            btn.draw(surf, fonts)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Returns button label if clicked."""
        if not self.visible:
            return None
        for btn in self.buttons:
            if btn.handle_event(event):
                return btn.label
        return None


class EventPanel(Panel):
    """Full-screen (ish) event popup with narrative text and choices."""

    def __init__(self):
        rect = pygame.Rect(160, 80, 960, 480)
        super().__init__(rect, "")
        self.event_obj = None
        self._choice_callbacks: List[Callable] = []

    def show_event(self, event_obj, game_state):
        self.event_obj = event_obj
        self.title = event_obj.title
        self.visible = True
        self.buttons.clear()
        self._choice_callbacks.clear()
        # Build choice buttons
        for i, (label, effect_fn) in enumerate(event_obj.choices):
            y = self.rect.y + 320 + i * 44
            btn = Button(
                rect=pygame.Rect(self.rect.x + 20, y, self.rect.width - 40, 38),
                label=label[:70],
                enabled=True,
                color=C_BUTTON_ACT,
            )
            self.buttons.append(btn)
            self._choice_callbacks.append(effect_fn)

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible or not self.event_obj:
            return
        # Dim background
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))

        self.draw_base(surf, fonts)

        # Description text – word wrap
        desc = self.event_obj.description
        words = desc.split()
        max_w = self.rect.width - 30
        lines = []
        current = ""
        for w in words:
            test = current + ("" if not current else " ") + w
            if fonts.small.size(test)[0] <= max_w:
                current = test
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)

        y = self.rect.y + 36
        for line in lines:
            t = fonts.small.render(line, True, C_TEXT)
            surf.blit(t, (self.rect.x + 12, y))
            y += 18

        for btn in self.buttons:
            btn.draw(surf, fonts)

    def handle_event(self, event: pygame.event.Event, game_state) -> Optional[str]:
        if not self.visible:
            return None
        for i, btn in enumerate(self.buttons):
            if btn.handle_event(event):
                # Execute choice
                result = self._choice_callbacks[i](game_state)
                game_state._add_log(f"[Event] {self.event_obj.title}: {result}")
                self.hide()
                return result
        return None


class RecruitPanel(Panel):
    """Panel to recruit new units."""

    AVAILABLE = [UT_CELL, UT_PLATOON, UT_MILITIA, UT_RECON]

    def __init__(self):
        rect = pygame.Rect(100, 100, 600, 500)
        super().__init__(rect, "Recruit Units")
        self._recruit_type: Optional[str] = None
        self._spawn_hex: Optional[Tuple[int,int]] = None
        self._status = ""

    def show_for_hex(self, col: int, row: int, game_state):
        self._spawn_hex = (col, row)
        self._status = ""
        self.visible = True
        self.buttons.clear()
        # Also show advisor and heavy if unlocked
        available = list(self.AVAILABLE)
        if (game_state.unlocks.has("eagle_advisor") or
                game_state.unlocks.has("bear_advisor")):
            available.append(UT_ADVISOR)
        if (game_state.unlocks.has("eagle_heavy") or
                game_state.unlocks.has("bear_armor") or
                game_state.unlocks.has("oil_private")):
            available.append(UT_HEAVY)

        for i, ut_id in enumerate(available):
            utype = UNIT_TYPES[ut_id]
            y = self.rect.y + 60 + i * 56
            btn = Button(
                rect=pygame.Rect(self.rect.x + 10, y, self.rect.width - 20, 50),
                label=f"{utype.name}  F:{utype.cost_funds} R:{utype.cost_recruits} W:{utype.cost_weapons}",
            )
            btn._ut_id = ut_id
            self.buttons.append(btn)

        close_btn = Button(
            rect=pygame.Rect(self.rect.right - 100, self.rect.y + 8, 88, 26),
            label="Close", color=C_DANGER)
        close_btn._ut_id = None
        self.buttons.append(close_btn)

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surf.blit(overlay, (0, 0))

        self.draw_base(surf, fonts)

        available_label = [UT_CELL, UT_PLATOON, UT_MILITIA, UT_RECON,
                           UT_ADVISOR, UT_HEAVY]
        for i, btn in enumerate(self.buttons):
            ut_id = getattr(btn, '_ut_id', None)
            if ut_id:
                utype = UNIT_TYPES[ut_id]
                btn.draw(surf, fonts)
                # Description below button
                desc_y = btn.rect.bottom - 16
                desc = fonts.tiny.render(utype.description[:70], True, C_TEXT_DIM)
                surf.blit(desc, (btn.rect.x + 4, desc_y))
            else:
                btn.draw(surf, fonts)

        # Status
        if self._status:
            st = fonts.small.render(self._status, True, C_TEXT_WARN)
            surf.blit(st, (self.rect.x + 10, self.rect.bottom - 30))

    def handle_event(self, event: pygame.event.Event, game_state) -> Optional[str]:
        if not self.visible:
            return None
        for btn in self.buttons:
            if btn.handle_event(event):
                ut_id = getattr(btn, '_ut_id', None)
                if ut_id is None:
                    self.hide()
                    return "closed"
                if self._spawn_hex:
                    c, r = self._spawn_hex
                    result = game_state.recruit_unit(ut_id, c, r)
                    self._status = result
                    if "Recruited" in result:
                        self.hide()
                    return result
        return None


class DiplomacyPanel(Panel):
    """Diplomacy actions panel for a selected faction."""

    def __init__(self):
        rect = pygame.Rect(80, 60, 700, 600)
        super().__init__(rect, "Diplomacy")
        self._faction_id: Optional[str] = None
        self._status = ""

    def show_for_faction(self, faction_id: str, game_state):
        from ..core.factions import FACTIONS
        self._faction_id = faction_id
        fdef = FACTIONS[faction_id]
        self.title = f"Relations: {fdef.name}"
        self.visible = True
        self.buttons.clear()
        self._status = ""

        actions = [
            ("Gift (-50 funds)", "gift",
             "Send funds as a goodwill gesture. Small relation boost."),
            ("Share Intelligence (-3 intel)", "intelligence",
             "Share valuable intelligence. Significant relation boost."),
        ]
        if faction_id == F_GOV:
            actions.append(("Concede Village", "concession",
                            "Give up a village to appease the government."))
        actions.append(("Lie Low", "lie_low",
                        "Reduce your profile. Less likely to attract attention."))

        for i, (label, action_id, _) in enumerate(actions):
            y = self.rect.y + 260 + i * 44
            btn = Button(
                rect=pygame.Rect(self.rect.x + 20, y, self.rect.width - 40, 38),
                label=label, color=C_BUTTON_ACT)
            btn._action = action_id
            self.buttons.append(btn)

        close_btn = Button(
            rect=pygame.Rect(self.rect.right - 100, self.rect.y + 8, 88, 26),
            label="Close", color=C_DANGER)
        close_btn._action = None
        self.buttons.append(close_btn)
        self._actions_desc = [a[2] for a in actions]

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible or not self._faction_id:
            return
        from ..core.factions import FACTIONS
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surf.blit(overlay, (0, 0))

        self.draw_base(surf, fonts)
        fdef = FACTIONS[self._faction_id]

        y = self.rect.y + 36
        # Faction description
        desc_words = fdef.description.split()
        max_w = self.rect.width - 24
        lines = []
        cur = ""
        for w in desc_words:
            test = cur + ("" if not cur else " ") + w
            if fonts.small.size(test)[0] <= max_w:
                cur = test
            else:
                lines.append(cur); cur = w
        if cur: lines.append(cur)
        for line in lines:
            t = fonts.small.render(line, True, C_TEXT_DIM)
            surf.blit(t, (self.rect.x + 12, y))
            y += 17

        y += 8
        # Unlocks
        unlock_lbl = fonts.small.render("Available Unlocks:", True, C_TEXT_DIM)
        surf.blit(unlock_lbl, (self.rect.x + 12, y))
        y += 18

        import game_state_ref
        gs = game_state_ref.GS
        rel = gs.rels.get(F_PLAYER, self._faction_id)

        for threshold, key, desc in fdef.unlocks:
            unlocked = gs.unlocks.has(key)
            met = rel >= threshold
            color = C_TEXT_GOOD if unlocked else (C_TEXT_WARN if met else C_TEXT_DIM)
            status = "✓" if unlocked else ("→" if met else f"  ({threshold})")
            line = fonts.tiny.render(f"{status} {desc[:65]}", True, color)
            surf.blit(line, (self.rect.x + 12, y))
            y += 14

        # Action buttons
        for btn in self.buttons:
            btn.draw(surf, fonts)

        # Status
        if self._status:
            st = fonts.small.render(self._status[:80], True, C_TEXT_WARN)
            surf.blit(st, (self.rect.x + 10, self.rect.bottom - 30))

    def handle_event(self, event: pygame.event.Event, game_state) -> Optional[str]:
        if not self.visible:
            return None
        for btn in self.buttons:
            if btn.handle_event(event):
                action = getattr(btn, '_action', None)
                if action is None:
                    self.hide()
                    return "closed"
                result = game_state.conduct_diplomacy(self._faction_id, action)
                self._status = result
                game_state._add_log(f"[Diplomacy] {result}")
                return result
        return None


class TooltipRenderer:
    """Small floating tooltip on hover."""

    def __init__(self):
        self.text = ""
        self.pos = (0, 0)
        self.visible = False

    def show(self, text: str, pos: Tuple[int, int]):
        self.text = text
        self.pos = pos
        self.visible = True

    def hide(self):
        self.visible = False

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible or not self.text:
            return
        lines = self.text.split("\n")
        w = max(fonts.tiny.size(l)[0] for l in lines) + 16
        h = len(lines) * 14 + 8
        x, y = self.pos
        # Keep on screen
        x = min(x, SCREEN_W - w - 4)
        y = min(y, SCREEN_H - h - 4)
        pygame.draw.rect(surf, C_TOOLTIP_BG, (x, y, w, h), border_radius=4)
        pygame.draw.rect(surf, C_PANEL_BORD, (x, y, w, h), 1, border_radius=4)
        for i, line in enumerate(lines):
            t = fonts.tiny.render(line, True, C_TEXT)
            surf.blit(t, (x + 8, y + 4 + i * 14))


class HelpPanel(Panel):
    """In-game help/tutorial panel."""
    HELP_TEXT = [
        ("Controls", [
            "Left click: Select unit / Select hex",
            "Right click: Move selected unit / Attack",
            "Middle click + drag: Pan map (or arrow keys)",
            "End Turn button: End your turn",
            "R key: Open Recruit panel on selected hex",
            "D key: Open Diplomacy panel",
            "H key: Toggle this help",
            "Scroll: Zoom (future)",
        ]),
        ("Game Concept", [
            "You lead a guerilla movement in a Cold War era conflict.",
            "Build support quietly or grab territory aggressively.",
            "High profile = government cracks down harder.",
            "Outside factions unlock powerful bonuses.",
            "Superpower relations are RIVALROUS above +35.",
            "Win by collapsing the government, dominating cities,",
            "  or achieving a negotiated political transition.",
        ]),
        ("Units", [
            "Cell (c):    Stealthy, subverts villages",
            "Platoon (p): Core combat, can ambush",
            "Militia (m): Cheap village defense",
            "Recon (r):   Long sight, gathers intel",
            "Advisor (A): Buffs adjacent units (needs faction unlock)",
            "Heavy (H):   Powerful but visible (needs faction unlock)",
        ]),
        ("Faction Relations", [
            "Gift/Intel: improve relations",
            "Soft cap at +35: gaining with superpowers penalises rival",
            "Each faction unlocks bonuses at thresholds",
            "Government relation = how much they target you",
            "Low profile = slower resources but safer",
        ]),
    ]

    def __init__(self):
        rect = pygame.Rect(60, 40, 900, 680)
        super().__init__(rect, "Help & Game Guide")

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        self.draw_base(surf, fonts)

        y = self.rect.y + 36
        col_w = self.rect.width // 2 - 16
        col = 0
        for section_title, lines in self.HELP_TEXT:
            x = self.rect.x + 12 + col * (col_w + 16)
            title_surf = fonts.medium.render(f"◆ {section_title}", True, C_TEXT_WARN)
            surf.blit(title_surf, (x, y))
            y += 20
            for line in lines:
                t = fonts.small.render(line, True, C_TEXT_DIM)
                surf.blit(t, (x + 8, y))
                y += 16
            y += 8
            if y > self.rect.bottom - 60:
                y = self.rect.y + 36
                col += 1

        # Close hint
        hint = fonts.small.render("Press H or click anywhere to close", True, C_TEXT_DIM)
        surf.blit(hint, (self.rect.centerx - hint.get_width() // 2,
                         self.rect.bottom - 28))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if panel consumed the event."""
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.hide()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.hide()
            return True
        return False


class GameOverPanel(Panel):
    def __init__(self):
        rect = pygame.Rect(240, 200, 800, 400)
        super().__init__(rect, "GAME OVER")

    def show_result(self, win_condition: str, gs):
        self.visible = True
        self.buttons.clear()
        titles = {
            WIN_REVOLUTION: "REVOLUTION SUCCEEDS",
            WIN_DOMINANCE:  "POLITICAL DOMINANCE",
            WIN_NEGOTIATED: "NEGOTIATED TRANSITION",
            WIN_DEFEAT:     "LIBERATION FRONT ELIMINATED",
        }
        descs = {
            WIN_REVOLUTION: "The government has collapsed under the weight of your military campaign.",
            WIN_DOMINANCE:  "Your movement controls the nation's major cities. Power is yours.",
            WIN_NEGOTIATED: "Through restraint and diplomacy, you achieved a peaceful transition.",
            WIN_DEFEAT:     "Your movement has been crushed. The struggle is over.",
        }
        self.title = titles.get(win_condition, "GAME OVER")
        self._desc = descs.get(win_condition, "")
        self._is_win = win_condition != WIN_DEFEAT
        self._stats = [
            f"Turns played: {gs.turn}",
            f"Influence: {gs.player_influence}",
            f"Government HP: {gs.government_hp}%",
            f"Profile: {gs.profile_level}",
        ]
        btn = Button(
            rect=pygame.Rect(self.rect.centerx - 80, self.rect.bottom - 60, 160, 40),
            label="Play Again", color=C_BUTTON_ACT)
        self.buttons.append(btn)

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surf.blit(overlay, (0, 0))
        self.draw_base(surf, fonts)

        y = self.rect.y + 36
        color = C_TEXT_GOOD if self._is_win else C_TEXT_BAD
        title = fonts.large.render(self.title, True, color)
        surf.blit(title, (self.rect.centerx - title.get_width() // 2, y))
        y += 40
        desc = fonts.normal.render(self._desc, True, C_TEXT)
        surf.blit(desc, (self.rect.centerx - desc.get_width() // 2, y))
        y += 40
        for stat in self._stats:
            t = fonts.small.render(stat, True, C_TEXT_DIM)
            surf.blit(t, (self.rect.centerx - t.get_width() // 2, y))
            y += 20
        for btn in self.buttons:
            btn.draw(surf, fonts)

    def handle_event(self, event: pygame.event.Event) -> bool:
        for btn in self.buttons:
            if btn.handle_event(event):
                return True  # restart signal
        return False
