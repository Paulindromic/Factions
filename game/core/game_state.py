# game_state.py – Central game state and turn logic

import random
from typing import Dict, List, Optional, Tuple, Set
from .constants import *
from .hex_grid import HexTile, hex_neighbors, hex_distance, hex_reachable
from .factions import RelationshipManager, UnlockManager, FACTIONS
from .units import Unit, UNIT_TYPES, calculate_combat, can_detect
from .map_gen import generate_map
from .events import EventQueue, GameEvent


class GameState:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.turn = 1
        self.phase = "player"   # player / ai / event
        self.game_over = False
        self.win_condition = None
        self.log: List[str] = []

        # Map
        self.grid: Dict[Tuple[int,int], HexTile] = generate_map(seed)

        # Relationships
        self.rels = RelationshipManager()
        self.unlocks = UnlockManager()

        # Resources
        self.resources = dict(START_RESOURCES)

        # Units
        self.all_units: Dict[str, Unit] = {}

        # Government stats
        self.government_hp = 100          # 0 = collapsed
        self.government_legitimacy = 60   # 0-100
        self.government_action_points = 3

        # Player profile (visibility/heat)
        self.player_profile_score = 0    # 0-100; high = government knows about you
        self.profile_level = PROFILE_LOW

        # Influence
        self.player_influence = 0

        # Events
        self.event_queue = EventQueue()
        self.event_queue.seed(seed + 99)
        self.pending_event: Optional[GameEvent] = None

        # Buffs (persistent global buffs from unlocks/events)
        self.active_buffs: Set[str] = set()

        # Per-turn income cache
        self._income_this_turn: Dict[str, int] = {}

        # Oil pipeline objective
        self.oil_pipeline_hex: Optional[Tuple[int,int]] = None
        self.peace_talks_ceasefire: int = 0   # turns remaining

        # Tracking
        self._rng = random.Random(seed)

        # Place starting units
        self._place_starting_units()

        # Reveal starting area
        self._update_visibility()

        self._add_log("Liberation Front established. The struggle begins.")

    # ── Unit management ──────────────────────────────────────────────────────

    def _place_starting_units(self):
        """Place initial units for all factions."""
        # Player – 2 cells and 1 recon in jungle
        player_starts = [(2, 3), (3, 4), (2, 5)]
        utypes = [UT_CELL, UT_PLATOON, UT_RECON]
        for (c, r), ut in zip(player_starts, utypes):
            self._spawn_unit(ut, F_PLAYER, c, r)

        # Mark player start tile as owned
        self.grid[(2, 3)].owner = F_PLAYER

        # Rivals
        self._spawn_unit(UT_CELL, F_RIVAL1, 18, 3)
        self._spawn_unit(UT_PLATOON, F_RIVAL1, 17, 4)
        self._spawn_unit(UT_CELL, F_RIVAL2, 10, 12)
        self._spawn_unit(UT_PLATOON, F_RIVAL2, 11, 13)

        # Government – in cities
        for (c, r), tile in self.grid.items():
            if tile.terrain == "city":
                self._spawn_unit(UT_GOV_INF, F_GOV, c, r)
                self._spawn_unit(UT_GOV_POLICE, F_GOV, c, r)

    def _spawn_unit(self, type_id: str, owner: str, col: int, row: int) -> Unit:
        u = Unit(type_id, owner, col, row)
        self.all_units[u.id] = u
        tile = self.grid.get((col, row))
        if tile and u.id not in tile.units:
            tile.units.append(u.id)
        return u

    def _remove_unit(self, unit: Unit):
        tile = self.grid.get((unit.col, unit.row))
        if tile and unit.id in tile.units:
            tile.units.remove(unit.id)
        self.all_units.pop(unit.id, None)

    # ── Visibility ────────────────────────────────────────────────────────────

    def _update_visibility(self):
        """Update fog of war based on player unit positions."""
        # Reset
        for tile in self.grid.values():
            tile.visible = False
        # Reveal hexes in sight range of each player unit
        for unit in self._player_units():
            for (nc, nr), tile in self.grid.items():
                d = hex_distance(unit.col, unit.row, nc, nr)
                eff_sight = unit.sight
                if "bear_recon" in self.unlocks.unlocked and unit.type_id == UT_RECON:
                    eff_sight += 1
                if d <= eff_sight:
                    tile.visible = True
                    tile.explored = True

    def _player_units(self) -> List[Unit]:
        return [u for u in self.all_units.values() if u.owner == F_PLAYER]

    # ── Actions ──────────────────────────────────────────────────────────────

    def move_unit(self, unit: Unit, dest_col: int, dest_row: int) -> str:
        """Move a unit to destination. Returns result string."""
        if unit.owner != F_PLAYER:
            return "Not your unit."
        if unit.has_acted:
            return "Unit has already acted this turn."
        reachable = hex_reachable(unit.col, unit.row, unit.moves_left, self.grid)
        if (dest_col, dest_row) not in reachable:
            return "Destination out of range."
        cost = self.grid[(dest_col, dest_row)].move_cost
        self.grid[(unit.col, unit.row)].units.remove(unit.id)
        unit.col, unit.row = dest_col, dest_row
        self.grid[(dest_col, dest_row)].units.append(unit.id)
        unit.moves_left -= cost
        self._update_visibility()
        # Entering enemy territory raises profile
        dest_tile = self.grid[(dest_col, dest_row)]
        if dest_tile.owner in (F_GOV, F_RIVAL1, F_RIVAL2):
            self._raise_profile(1)
        return f"Moved to ({dest_col},{dest_row})."

    def attack_unit(self, attacker: Unit, defender: Unit) -> str:
        if attacker.owner != F_PLAYER:
            return "Not your unit."
        if attacker.has_acted:
            return "Unit has already acted this turn."
        d = hex_distance(attacker.col, attacker.row, defender.col, defender.row)
        if d > 1:
            return "Target not adjacent."
        atk_tile = self.grid.get((attacker.col, attacker.row))
        def_tile = self.grid.get((defender.col, defender.row))
        atk_conceal = atk_tile.conceal_bonus if atk_tile else 0
        def_conceal = def_tile.conceal_bonus if def_tile else 0

        # Ambush if attacker is guerilla and defender can't see
        ambush = (attacker.utype.can_ambush and
                  not can_detect(defender, attacker, 1, atk_conceal) and
                  self._rng.random() < 0.4)

        def_dmg, atk_dmg, log = calculate_combat(
            attacker, defender, atk_conceal, def_conceal, ambush)

        defender.take_damage(def_dmg)
        attacker.take_damage(atk_dmg)
        attacker.has_acted = True
        attacker.moves_left = 0
        self._add_log(log)

        # XP
        if def_dmg > 0:
            promoted = attacker.gain_xp(1)
            if promoted:
                self._add_log(f"{attacker.utype.name} becomes a Veteran!")

        # Government awareness
        if defender.owner == F_GOV:
            self._raise_profile(3)
            self.rels.change(F_PLAYER, F_GOV, -5, self.log)

        # Remove dead
        result = log
        if not defender.alive:
            self._remove_unit(defender)
            result += f"\n{defender.utype.name} destroyed!"
            if defender.owner == F_GOV:
                self.government_hp = max(0, self.government_hp - 2)
        if not attacker.alive:
            self._remove_unit(attacker)
            result += f"\n{attacker.utype.name} lost!"

        self._update_visibility()
        return result

    def subvert_village(self, unit: Unit) -> str:
        """Attempt to subvert the village the unit is on."""
        if unit.owner != F_PLAYER:
            return "Not your unit."
        if not unit.utype.can_subvert:
            return "This unit cannot subvert villages."
        if unit.has_acted:
            return "Unit has already acted this turn."
        tile = self.grid.get((unit.col, unit.row))
        if not tile or tile.terrain not in ("village", "city"):
            return "No settlement here."
        if tile.owner == F_PLAYER:
            return "Already under your influence."

        # Chance depends on tile terrain concealment and current owner
        base_chance = 0.4
        if tile.owner == F_GOV:
            base_chance -= 0.15
            if "cross_immunity" in self.unlocks.unlocked:
                base_chance += 0.1
        if "bear_advisor" in self.unlocks.unlocked:
            base_chance += 0.15

        success = self._rng.random() < base_chance
        unit.has_acted = True
        unit.moves_left = 0
        self._raise_profile(2)

        if success:
            prev_owner = tile.owner
            tile.owner = F_PLAYER
            self._add_log(f"Subverted {tile.poi or 'village'} from {prev_owner or 'neutral'}!")
            if prev_owner == F_GOV:
                self.rels.change(F_PLAYER, F_GOV, -8, self.log)
                self.government_hp = max(0, self.government_hp - 1)
            return f"Successfully subverted {tile.poi or 'the village'}!"
        else:
            if self._rng.random() < 0.3:
                self.rels.change(F_PLAYER, F_GOV, -3, self.log)
                self._raise_profile(3)
                return "Subversion failed! Government informants spotted your activities."
            return "Subversion failed. The village is not ready to turn."

    def recruit_unit(self, type_id: str, col: int, row: int) -> str:
        """Recruit a new unit at a player-controlled tile."""
        if self.grid[(col, row)].owner != F_PLAYER:
            return "You don't control this area."
        utype = UNIT_TYPES.get(type_id)
        if not utype:
            return "Unknown unit type."
        # Check unlock requirements
        if type_id == UT_ADVISOR:
            if not (self.unlocks.has("eagle_advisor") or self.unlocks.has("bear_advisor")):
                return "Requires advisor unlock from Eagle or Bear."
        if type_id == UT_HEAVY:
            if not (self.unlocks.has("eagle_heavy") or self.unlocks.has("bear_armor") or
                    self.unlocks.has("oil_private")):
                return "Requires heavy weapons unlock."
        # Check resources
        cost_f = utype.cost_funds
        if self.unlocks.has("bear_weapons") and type_id == UT_PLATOON:
            cost_f = max(0, cost_f - 10)
        if self.unlocks.has("oil_smuggle"):
            cost_w = int(utype.cost_weapons * 0.7)
        else:
            cost_w = utype.cost_weapons

        if self.resources[RES_FUNDS] < cost_f:
            return f"Not enough funds (need {cost_f}, have {self.resources[RES_FUNDS]})."
        if self.resources[RES_RECRUITS] < utype.cost_recruits:
            return f"Not enough recruits (need {utype.cost_recruits})."
        if self.resources[RES_WEAPONS] < cost_w:
            return f"Not enough weapons (need {cost_w})."

        self.resources[RES_FUNDS]    -= cost_f
        self.resources[RES_RECRUITS] -= utype.cost_recruits
        self.resources[RES_WEAPONS]  -= cost_w

        u = self._spawn_unit(type_id, F_PLAYER, col, row)
        # Apply global buffs
        self._apply_buffs_to_unit(u)
        return f"Recruited {utype.name} at ({col},{row})."

    def _apply_buffs_to_unit(self, unit: Unit):
        """Apply active global buffs to a newly spawned or existing unit."""
        if "eagle_weapons" in self.unlocks.unlocked:
            unit.attack_bonus = max(unit.attack_bonus, 1)
        if "bear_weapons" in self.unlocks.unlocked and unit.type_id == UT_PLATOON:
            unit.attack_bonus = max(unit.attack_bonus, 1)
        if "jag_training" in self.unlocks.unlocked:
            unit.defense_bonus = max(unit.defense_bonus, 1)
        if "bear_recon" in self.unlocks.unlocked and unit.type_id == UT_RECON:
            unit.sight_bonus = max(unit.sight_bonus, 1)

    def conduct_diplomacy(self, faction_id: str, action: str) -> str:
        """Player-initiated diplomatic action."""
        if faction_id not in FACTIONS:
            return "Unknown faction."
        current_rel = self.rels.get(F_PLAYER, faction_id)
        fdef = FACTIONS[faction_id]

        if action == "gift":
            cost = 50
            if self.resources[RES_FUNDS] < cost:
                return f"Not enough funds (need {cost})."
            self.resources[RES_FUNDS] -= cost
            gain = self._rng.randint(5, 12)
            actual = self.rels.change(F_PLAYER, faction_id, gain, self.log)
            # Superpower rivalry penalty
            if fdef.is_superpower and current_rel >= REL_SOFTCAP:
                self.rels.apply_superpower_rivalry(F_PLAYER, faction_id, gain, self.log)
            return f"Sent gift to {fdef.name}. Relations +{actual}."

        elif action == "intelligence":
            cost_i = 3
            if self.resources[RES_INTEL] < cost_i:
                return f"Not enough intel (need {cost_i})."
            self.resources[RES_INTEL] -= cost_i
            gain = self._rng.randint(8, 15)
            actual = self.rels.change(F_PLAYER, faction_id, gain, self.log)
            if fdef.is_superpower and current_rel >= REL_SOFTCAP:
                self.rels.apply_superpower_rivalry(F_PLAYER, faction_id, gain, self.log)
            return f"Shared intelligence with {fdef.name}. Relations +{actual}."

        elif action == "concession":
            # Give up a village to improve relations with government
            if faction_id != F_GOV:
                return "Concession only works with the Government."
            player_villages = [(c, r) for (c, r), t in self.grid.items()
                               if t.terrain == "village" and t.owner == F_PLAYER]
            if not player_villages:
                return "No villages to concede."
            c, r = self._rng.choice(player_villages)
            self.grid[(c, r)].owner = F_GOV
            self.rels.change(F_PLAYER, F_GOV, 20, self.log)
            return f"Conceded {self.grid[(c,r)].poi or 'a village'} to the Government. Relations improved."

        elif action == "lie_low":
            # Reduce profile score (diplomacy to reassure)
            reduction = self._rng.randint(3, 8)
            self.player_profile_score = max(0, self.player_profile_score - reduction)
            self._update_profile_level()
            return f"Reduced profile by {reduction}. Current heat: {self.player_profile_score}."

        return "Unknown action."

    # ── Turn end ──────────────────────────────────────────────────────────────

    def end_player_turn(self) -> List[str]:
        """Process end of player turn and run AI turns."""
        messages = []

        # 1. Collect income
        income_msgs = self._collect_income()
        messages.extend(income_msgs)

        # 2. Pay upkeep
        upkeep_msgs = self._pay_upkeep()
        messages.extend(upkeep_msgs)

        # 3. Heal units in safe terrain
        self._heal_units()

        # 4. Check unlocks
        new_unlocks = self.unlocks.check_unlocks(F_PLAYER, self.rels)
        for key, desc, fname in new_unlocks:
            msg = f"UNLOCK from {fname}: {desc}"
            messages.append(msg)
            self._add_log(msg)
            # Apply buffs immediately
            for u in self._player_units():
                self._apply_buffs_to_unit(u)

        # 5. Passive income from faction unlocks
        self._apply_faction_income()

        # 6. Profile decay (low profile operations reduce heat)
        if self.profile_level == PROFILE_LOW:
            self.player_profile_score = max(0, self.player_profile_score - 2)
        self._update_profile_level()

        # 7. AI turns
        from ..ai.ai_controller import AIController
        ai = AIController(self)
        if self.peace_talks_ceasefire <= 0:
            ai.run_government_turn()
        ai.run_rival_turn(F_RIVAL1)
        ai.run_rival_turn(F_RIVAL2)
        ai.run_outside_faction_turn()

        # 8. Ceasefire countdown
        if self.peace_talks_ceasefire > 0:
            self.peace_talks_ceasefire -= 1

        # 9. Check events
        events = self.event_queue.check_events(self)
        if events:
            self.pending_event = events[0]

        # 10. Check win/lose
        win_msg = self._check_win_conditions()
        if win_msg:
            messages.append(win_msg)

        # 11. Advance turn
        self.turn += 1
        if self.turn > MAX_TURNS:
            self.game_over = True
            self.win_condition = WIN_NEGOTIATED if self.player_influence >= 50 else WIN_DEFEAT

        # 12. Reset player units for new turn
        for u in self._player_units():
            u.new_turn()

        self._update_visibility()
        return messages

    def _collect_income(self) -> List[str]:
        msgs = []
        fund_gain = rec_gain = inf_gain = 0
        for (c, r), tile in self.grid.items():
            if tile.owner == F_PLAYER:
                if tile.terrain == "village":
                    fund_gain += INCOME_VILLAGE[RES_FUNDS]
                    rec_gain  += INCOME_VILLAGE[RES_RECRUITS]
                    if "jag_smuggle" in self.unlocks.unlocked:
                        fund_gain += 10
                elif tile.terrain == "city":
                    fund_gain += INCOME_CITY[RES_FUNDS]
                    rec_gain  += INCOME_CITY[RES_RECRUITS]
                    inf_gain  += INCOME_CITY[RES_INFLUENCE]

        # Oil pipeline
        if self.oil_pipeline_hex:
            pc, pr = self.oil_pipeline_hex
            nearby = any(u.owner == F_PLAYER
                         for u in self.all_units.values()
                         if hex_distance(u.col, u.row, pc, pr) <= 2)
            if nearby:
                fund_gain += 80
            else:
                fund_gain += 20
                msgs.append("Warning: pipeline unprotected!")

        if fund_gain > 0 or rec_gain > 0:
            self.resources[RES_FUNDS]    += fund_gain
            self.resources[RES_RECRUITS] += rec_gain
            self.player_influence        += inf_gain
            msgs.append(f"Income: +{fund_gain} funds, +{rec_gain} recruits, +{inf_gain} influence.")
        return msgs

    def _apply_faction_income(self):
        """Passive income from faction unlock bonuses."""
        if self.unlocks.has("eagle_funds"):
            self.resources[RES_FUNDS] += 30
        if self.unlocks.has("bear_funds"):
            self.resources[RES_FUNDS] += 25
        if self.unlocks.has("oil_funds") or self.unlocks.has("oil_pipeline"):
            extra = 80 if self.unlocks.has("oil_pipeline") else 40
            self.resources[RES_FUNDS] += extra
        if self.unlocks.has("eagle_intel") or self.unlocks.has("bear_intel"):
            self.resources[RES_INTEL] += 2
        if self.unlocks.has("bear_intel"):
            self.resources[RES_INTEL] += 1
        if self.unlocks.has("cross_legit"):
            self.player_influence += 5
        if self.unlocks.has("cross_aid"):
            self.resources[RES_RECRUITS] += 1

    def _pay_upkeep(self) -> List[str]:
        msgs = []
        total_upkeep = 0
        for u in self._player_units():
            total_upkeep += u.utype.upkeep_funds
        if total_upkeep > 0:
            if self.resources[RES_FUNDS] >= total_upkeep:
                self.resources[RES_FUNDS] -= total_upkeep
            else:
                # Can't pay – units lose HP
                shortfall = total_upkeep - self.resources[RES_FUNDS]
                self.resources[RES_FUNDS] = 0
                msgs.append(f"Cannot pay upkeep! Units suffer ({shortfall} funds short).")
                for u in self._player_units():
                    u.take_damage(1)
        return msgs

    def _heal_units(self):
        """Units in safe, friendly territory heal."""
        for u in self._player_units():
            tile = self.grid.get((u.col, u.row))
            if not tile:
                continue
            heal = 0
            if tile.owner == F_PLAYER:
                heal = 1
            if self.unlocks.has("eagle_medic"):
                heal = max(heal, 1)
            if self.unlocks.has("cross_hospital"):
                heal = max(heal, 2)
            if heal:
                u.heal(heal)

    def _raise_profile(self, amount: int):
        """Increase player profile/visibility score."""
        self.player_profile_score = min(100, self.player_profile_score + amount)
        self._update_profile_level()

    def _update_profile_level(self):
        if self.player_profile_score < 20:
            self.profile_level = PROFILE_LOW
        elif self.player_profile_score < 50:
            self.profile_level = PROFILE_MEDIUM
        else:
            self.profile_level = PROFILE_HIGH

    def _check_win_conditions(self) -> Optional[str]:
        """Check if any win/lose condition is met."""
        player_units = self._player_units()

        # Defeat: no units and no controlled territory
        if not player_units:
            player_territory = [t for t in self.grid.values() if t.owner == F_PLAYER]
            if not player_territory:
                self.game_over = True
                self.win_condition = WIN_DEFEAT
                return "DEFEAT: Liberation Front has been eliminated."

        # Win: government collapses
        if self.government_hp <= 0:
            self.game_over = True
            self.win_condition = WIN_REVOLUTION
            return "VICTORY: The government has collapsed! The revolution succeeds!"

        # Win: dominance (control majority of cities)
        cities = [t for t in self.grid.values() if t.terrain == "city"]
        player_cities = [t for t in cities if t.owner == F_PLAYER]
        if cities and len(player_cities) >= len(cities) * 0.6:
            self.game_over = True
            self.win_condition = WIN_DOMINANCE
            return "VICTORY: You control the nation's cities! Political dominance achieved."

        # Win: negotiated (high influence, low profile)
        if (self.player_influence >= 80 and
                self.profile_level == PROFILE_LOW and
                self.rels.get(F_PLAYER, F_CROSS) >= 50):
            self.game_over = True
            self.win_condition = WIN_NEGOTIATED
            return "VICTORY: Negotiated transition achieved through influence and restraint."

        return None

    def _add_log(self, msg: str):
        self.log.append(msg)
        if len(self.log) > 200:
            self.log = self.log[-200:]

    # ── Event effects ─────────────────────────────────────────────────────────

    def event_effect_rel(self, faction_id: str, delta: int,
                         funds: int = 0, intel: int = 0,
                         influence: int = 0, buff: str = None,
                         rival_pen: bool = False) -> str:
        fdef = FACTIONS[faction_id]
        actual = self.rels.change(F_PLAYER, faction_id, delta, self.log)
        if rival_pen and fdef.is_superpower:
            cur = self.rels.get(F_PLAYER, faction_id)
            if cur >= REL_SOFTCAP:
                self.rels.apply_superpower_rivalry(F_PLAYER, faction_id, delta, self.log)
        msgs = [f"Relations with {fdef.name}: +{actual}"]
        if funds:
            self.resources[RES_FUNDS] += funds
            msgs.append(f"+{funds} funds")
        if intel:
            self.resources[RES_INTEL] += intel
            msgs.append(f"+{intel} intel")
        if influence:
            self.player_influence += influence
            msgs.append(f"+{influence} influence")
        if buff:
            self.active_buffs.add(buff)
            msgs.append(f"Buff gained: {buff}")
        return ". ".join(msgs) + "."

    def event_gain_resources(self, funds: int = 0, recruits: int = 0,
                             weapons: int = 0, intel: int = 0,
                             influence: int = 0, loyalty_bonus: bool = False,
                             big: bool = False, profile_up: bool = False,
                             weaken_gov: bool = False) -> str:
        msgs = []
        if funds:
            self.resources[RES_FUNDS] = max(0, self.resources[RES_FUNDS] + funds)
            msgs.append(f"{'+' if funds>0 else ''}{funds} funds")
        if recruits:
            self.resources[RES_RECRUITS] += recruits
            msgs.append(f"+{recruits} recruits")
        if weapons:
            self.resources[RES_WEAPONS] += weapons
            msgs.append(f"+{weapons} weapons")
        if intel:
            self.resources[RES_INTEL] += intel
            msgs.append(f"+{intel} intel")
        if influence:
            self.player_influence += influence
            msgs.append(f"+{influence} influence")
        if loyalty_bonus:
            n = self._rng.randint(1, 3)
            villages = [(c, r) for (c, r), t in self.grid.items()
                        if t.terrain == "village" and t.owner == F_PLAYER]
            if not villages and big:
                villages = [(c, r) for (c, r), t in self.grid.items()
                            if t.terrain == "village"]
            for (c, r) in self._rng.sample(villages, min(n, len(villages))):
                if self.grid[(c, r)].owner != F_PLAYER:
                    self.grid[(c, r)].owner = F_PLAYER
                    msgs.append(f"{self.grid[(c,r)].poi or 'village'} joins your cause")
        if profile_up:
            self._raise_profile(5)
        if weaken_gov:
            self.government_legitimacy = max(0, self.government_legitimacy - 5)
        return ". ".join(msgs) + "." if msgs else "Done."

    def event_heal_all(self, rel_gain: int) -> str:
        self.rels.change(F_PLAYER, F_CROSS, rel_gain, self.log)
        for u in self._player_units():
            u.heal(2)
        return f"Relations with Neutral Cross +{rel_gain}. All units healed +2 HP."

    def event_oil_deal(self) -> str:
        self.rels.change(F_PLAYER, F_OIL, 20, self.log)
        self.resources[RES_FUNDS] += 80
        # Set a random hex as pipeline objective
        plains = [(c, r) for (c, r), t in self.grid.items()
                  if t.terrain in ("plain", "savanna") and not t.poi]
        if plains:
            self.oil_pipeline_hex = self._rng.choice(plains)
        return "+80 funds. Pipeline objective set – keep your forces nearby to collect income!"

    def event_scatter_units(self) -> str:
        """Move player units into jungle."""
        jungles = [(c, r) for (c, r), t in self.grid.items()
                   if t.terrain == "jungle" and not t.units]
        moved = 0
        for u in self._player_units():
            if jungles:
                c, r = self._rng.choice(jungles)
                self.grid[(u.col, u.row)].units.remove(u.id)
                u.col, u.row = c, r
                self.grid[(c, r)].units.append(u.id)
                jungles.remove((c, r))
                moved += 1
        self.player_profile_score = max(0, self.player_profile_score - 10)
        self._update_profile_level()
        return f"Scattered {moved} units into jungle cover. Profile reduced."

    def event_ambush_gov(self) -> str:
        gov_units = [u for u in self.all_units.values() if u.owner == F_GOV]
        player_units = self._player_units()
        if gov_units and player_units:
            attacker = self._rng.choice(player_units)
            defender = min(gov_units,
                           key=lambda u: hex_distance(attacker.col, attacker.row, u.col, u.row))
            def_dmg, atk_dmg, log = calculate_combat(attacker, defender, 2, 0, ambush=True)
            defender.take_damage(def_dmg)
            attacker.take_damage(atk_dmg)
            if not defender.alive:
                self._remove_unit(defender)
                return f"Ambush successful! {log}. Enemy unit destroyed."
            if not attacker.alive:
                self._remove_unit(attacker)
                return f"Ambush failed! {log}. Lost a unit."
            return f"Ambush: {log}"
        return "No targets for ambush."

    def event_bribe_gen(self) -> str:
        if self.resources[RES_FUNDS] >= 60:
            self.resources[RES_FUNDS] -= 60
            self.government_action_points = max(0, self.government_action_points - 2)
            return "Bribed a general. Government sweep called off! (-60 funds)"
        return "Not enough funds to bribe."

    def event_retaliate_rival(self) -> str:
        rivals = [u for u in self.all_units.values() if u.owner in (F_RIVAL1, F_RIVAL2)]
        players = self._player_units()
        if rivals and players:
            att = self._rng.choice(players)
            defn = min(rivals, key=lambda u: hex_distance(att.col, att.row, u.col, u.row))
            def_dmg, atk_dmg, log = calculate_combat(att, defn, 1, 1)
            defn.take_damage(def_dmg)
            att.take_damage(atk_dmg)
            result = log
            if not defn.alive:
                self._remove_unit(defn)
                result += " Rival unit destroyed."
            if not att.alive:
                self._remove_unit(att)
                result += " Lost a unit."
            return result
        return "No rivals in range."

    def event_assassinate_rival(self) -> str:
        if self.resources[RES_FUNDS] < 80:
            return "Not enough funds."
        self.resources[RES_FUNDS] -= 80
        # Remove a random rival unit
        rivals = [u for u in self.all_units.values() if u.owner in (F_RIVAL1, F_RIVAL2)]
        if rivals:
            target = self._rng.choice(rivals)
            self._remove_unit(target)
            self._raise_profile(5)
            return f"Rival leader eliminated. (-80 funds, +profile)"
        return "No rival to eliminate."

    def event_raid_convoy(self, half: bool = False) -> str:
        gain = 40 if half else 80
        gov_anger = 5 if half else 10
        profile_up = 2 if half else 4
        self.resources[RES_FUNDS] += gain
        self.rels.change(F_PLAYER, F_GOV, -gov_anger, self.log)
        self._raise_profile(profile_up)
        return f"Raided convoy! +{gain} funds. Government relations -{gov_anger}."

    def event_bluff_eagle(self) -> str:
        if self._rng.random() < 0.5:
            self.rels.change(F_PLAYER, F_EAGLE, 20, self.log)
            self.resources[RES_FUNDS] += 80
            return "The Eagle Alliance respects the bold ask! +20 relations, +80 funds."
        else:
            self.rels.change(F_PLAYER, F_EAGLE, -10, self.log)
            return "Eagle Alliance is offended by your demands. -10 relations."

    def event_peace_talks(self) -> str:
        self.rels.change(F_PLAYER, F_CROSS, 20, self.log)
        self.rels.change(F_PLAYER, F_BEAR, -20, self.log)
        self.player_influence += 10
        self.peace_talks_ceasefire = 5
        return "+20 Cross relations, +10 influence. 5-turn ceasefire with government."

    def event_sabotage_talks(self) -> str:
        self.player_influence += 5
        self.rels.change(F_PLAYER, F_CROSS, -20, self.log)
        return "+5 influence short term. Neutral Cross is furious. -20 relations."
