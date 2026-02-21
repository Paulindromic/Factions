# faction_chooser.py – Popup to pick which faction to open diplomacy with

import pygame
from typing import Optional
from ..core.constants import *
from ..core.factions import FACTIONS
from .renderer import Fonts
from .panels import Panel, Button


class FactionChooser(Panel):
    """Small popup to select which faction to open diplomacy with."""

    FACTIONS_LIST = [F_EAGLE, F_BEAR, F_CROSS, F_OIL, F_JAGUAR, F_GOV]

    def __init__(self):
        rect = pygame.Rect(SIDEBAR_W + 20, 40, 360, 260)
        super().__init__(rect, "Choose Faction")
        self._selected: Optional[str] = None

    def show(self, gs=None):
        self.visible = True
        self._selected = None
        self.buttons.clear()
        for i, fid in enumerate(self.FACTIONS_LIST):
            fdef = FACTIONS[fid]
            rel = gs.rels.get(F_PLAYER, fid) if gs else 0
            label_str = f"{fdef.short:4s} {fdef.name[:18]:18s} {rel:+d}"
            btn = Button(
                rect=pygame.Rect(self.rect.x + 10,
                                 self.rect.y + 36 + i * 34,
                                 self.rect.width - 20, 28),
                label=label_str,
                color=tuple(v // 2 for v in fdef.color),
                text_color=fdef.color,
            )
            btn._fid = fid
            self.buttons.append(btn)
        close_btn = Button(
            rect=pygame.Rect(self.rect.right - 80, self.rect.y + 6, 70, 24),
            label="Cancel", color=C_DANGER)
        close_btn._fid = None
        self.buttons.append(close_btn)

    def draw(self, surf: pygame.Surface, fonts: Fonts):
        if not self.visible:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surf.blit(overlay, (0, 0))
        self.draw_base(surf, fonts)
        for btn in self.buttons:
            btn.draw(surf, fonts)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if not self.visible:
            return None
        for btn in self.buttons:
            if btn.handle_event(event):
                fid = getattr(btn, '_fid', None)
                self.hide()
                return fid if fid else "cancel"
        return None
