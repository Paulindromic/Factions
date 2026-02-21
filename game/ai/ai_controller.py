# ai_controller.py – AI for government, rival guerilla movements, and outside factions

import random
from typing import Dict, List, Optional, Tuple
from ..core.constants import *
from ..core.units import Unit, UNIT_TYPES, calculate_combat
from ..core.hex_grid import hex_neighbors, hex_distance, hex_reachable, hex_path


class AIController:
    """Drives all non-player factions."""

    def __init__(self, game_state):
        self.gs = game_state
        self._rng = random.Random(game_state.seed + 1337)

    def run_government_turn(self):
        """Government AI: expand slowly, reinforce threatened areas, respond to player."""
        gs = self.gs
        gov_units = [u for u in gs.all_units.values() if u.owner == F_GOV]

        # Government gets periodic reinforcements in cities
        for (c, r), tile in gs.grid.items():
            if tile.terrain == "city" and tile.owner == F_GOV:
                if self._rng.random() < 0.3:
                    # Spawn infantry if not overcrowded
                    present = [u for u in gov_units if u.col == c and u.row == r]
                    if len(present) < 2:
                        gs._spawn_unit(UT_GOV_INF, F_GOV, c, r)

        # Move government units toward player and rival presence
        for unit in gov_units:
            unit.new_turn()
            # Find nearest threat
            threats = [(u.col, u.row) for u in gs.all_units.values()
                       if u.owner != F_GOV and unit.sight >= hex_distance(
                           unit.col, unit.row, u.col, u.row)]
            if not threats:
                # Patrol toward player-controlled tiles
                player_tiles = [(c, r) for (c, r), t in gs.grid.items()
                                if t.owner == F_PLAYER]
                if player_tiles:
                    threats = [self._rng.choice(player_tiles)]

            if threats:
                target = min(threats, key=lambda t: hex_distance(unit.col, unit.row, t[0], t[1]))
                path = hex_path((unit.col, unit.row), target, gs.grid)
                moved = 0
                for (nc, nr) in path:
                    if moved >= unit.move:
                        break
                    # Attack if enemy present
                    enemies = [u for u in gs.all_units.values()
                               if u.owner != F_GOV and u.col == nc and u.row == nr]
                    if enemies:
                        target_unit = enemies[0]
                        self._do_combat(unit, target_unit, gs)
                        break
                    cost = gs.grid[(nc, nr)].move_cost
                    if moved + cost <= unit.move:
                        gs.grid[(unit.col, unit.row)].units.remove(unit.id)
                        unit.col, unit.row = nc, nr
                        gs.grid[(nc, nr)].units.append(unit.id)
                        moved += cost
                    else:
                        break

        # Government builds profile response
        if gs.player_profile_score >= 15:
            gs.government_hp = max(0, gs.government_hp - 0)  # just tracking
            gs.government_action_points = max(0, gs.government_action_points - 1)
        gs.government_action_points += 2  # replenish

        # Occasionally reclaim villages
        if self._rng.random() < 0.15:
            contested = [(c, r) for (c, r), t in gs.grid.items()
                         if t.terrain in ("village",) and t.owner != F_GOV
                         and any(u.owner == F_GOV for u in
                                 [gs.all_units.get(uid) for uid in t.units] if u)]
            if contested:
                c, r = self._rng.choice(contested)
                gs.grid[(c, r)].owner = F_GOV
                gs._add_log(f"Government reasserted control over {gs.grid[(c,r)].poi or 'a village'}.")

    def run_rival_turn(self, rival_id: str):
        """Rival guerilla AI: expand, raid, compete for villages."""
        gs = self.gs
        rival_units = [u for u in gs.all_units.values() if u.owner == rival_id]
        fdef = __import__('game.core.factions', fromlist=['FACTIONS']).FACTIONS[rival_id]

        # Spawn a unit occasionally
        if self._rng.random() < 0.25 and len(rival_units) < 6:
            # Find a safe jungle/savanna hex far from player
            candidates = [(c, r) for (c, r), t in gs.grid.items()
                          if t.terrain in ("jungle", "savanna", "plain")
                          and not t.units and t.owner != F_PLAYER]
            if candidates:
                c, r = self._rng.choice(candidates)
                utype = self._rng.choice([UT_CELL, UT_PLATOON])
                gs._spawn_unit(utype, rival_id, c, r)
                rival_units = [u for u in gs.all_units.values() if u.owner == rival_id]

        for unit in rival_units:
            unit.new_turn()
            moved = 0
            best_target = self._find_rival_target(unit, rival_id, fdef.ai_aggression)

            if best_target:
                path = hex_path((unit.col, unit.row), best_target, gs.grid)
                for (nc, nr) in path:
                    if moved >= unit.move:
                        break
                    enemies = [u for u in gs.all_units.values()
                               if u.owner == F_PLAYER and u.col == nc and u.row == nr]
                    if enemies:
                        self._do_combat(unit, enemies[0], gs)
                        break
                    cost = gs.grid[(nc, nr)].move_cost
                    if moved + cost <= unit.move:
                        gs.grid[(unit.col, unit.row)].units.remove(unit.id)
                        unit.col, unit.row = nc, nr
                        gs.grid[(nc, nr)].units.append(unit.id)
                        moved += cost
                    else:
                        break

            # Try to subvert village
            tile = gs.grid[(unit.col, unit.row)]
            if tile.terrain == "village" and tile.owner != rival_id:
                if self._rng.random() < 0.3:
                    tile.owner = rival_id
                    gs._add_log(f"{fdef.name} subverted {tile.poi or 'a village'}.")

    def _find_rival_target(self, unit, rival_id, aggression) -> Optional[Tuple[int, int]]:
        gs = self.gs
        # Aggressive: target player units
        if self._rng.random() < aggression:
            player_units = [(u.col, u.row) for u in gs.all_units.values()
                            if u.owner == F_PLAYER]
            if player_units:
                return min(player_units,
                           key=lambda t: hex_distance(unit.col, unit.row, t[0], t[1]))
        # Otherwise go for uncontrolled villages
        villages = [(c, r) for (c, r), t in gs.grid.items()
                    if t.terrain == "village" and t.owner not in (F_PLAYER, rival_id)]
        if villages:
            return min(villages,
                       key=lambda t: hex_distance(unit.col, unit.row, t[0], t[1]))
        return None

    def _do_combat(self, attacker: Unit, defender: Unit, gs):
        """Execute AI-initiated combat."""
        from ..core.units import calculate_combat
        atk_tile = gs.grid.get((attacker.col, attacker.row))
        def_tile = gs.grid.get((defender.col, defender.row))
        atk_conceal = atk_tile.conceal_bonus if atk_tile else 0
        def_conceal = def_tile.conceal_bonus if def_tile else 0

        ambush = (attacker.utype.can_ambush and
                  self._rng.random() < 0.3 and
                  def_conceal == 0)

        def_dmg, atk_dmg, log = calculate_combat(
            attacker, defender, atk_conceal, def_conceal, ambush)

        defender.take_damage(def_dmg)
        attacker.take_damage(atk_dmg)
        gs._add_log(f"Combat: {log}")

        if not defender.alive:
            gs._remove_unit(defender)
        if not attacker.alive:
            gs._remove_unit(attacker)

    def run_outside_faction_turn(self):
        """
        Simulate outside faction relationship dynamics:
        - Superpowers occasionally increase pressure on player
        - Minor factions react to events
        """
        gs = self.gs
        rels = gs.rels

        # Eagle and Bear compete: if player is close to one, the other gets nervous
        eagle_rel = rels.get(F_PLAYER, F_EAGLE)
        bear_rel  = rels.get(F_PLAYER, F_BEAR)

        if eagle_rel > 50 and self._rng.random() < 0.2:
            delta = self._rng.randint(-3, -1)
            rels.change(F_PLAYER, F_BEAR, delta, gs.log)

        if bear_rel > 50 and self._rng.random() < 0.2:
            delta = self._rng.randint(-3, -1)
            rels.change(F_PLAYER, F_EAGLE, delta, gs.log)

        # Government responds to player profile
        if gs.player_profile_score > 20:
            rels.change(F_PLAYER, F_GOV, self._rng.randint(-3, -1), gs.log)

        # Relations drift slightly toward neutral over time (–1 per 5 turns)
        if gs.turn % 5 == 0:
            for fid in [F_EAGLE, F_BEAR, F_CROSS, F_OIL, F_JAGUAR]:
                rel = rels.get(F_PLAYER, fid)
                if rel > 0:
                    rels.change(F_PLAYER, fid, -1)
                elif rel < 0:
                    rels.change(F_PLAYER, fid, 1)
