# units.py – Unit definitions and combat system

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .constants import *


@dataclass
class UnitType:
    id: str
    name: str
    symbol: str         # single character for map display
    description: str
    hp_max: int
    attack: int
    defense: int
    move: int           # movement points
    sight: int          # detection range (hexes)
    stealth: int        # how hard to detect (reduces enemy sight)
    cost_funds: int
    cost_recruits: int
    cost_weapons: int
    upkeep_funds: int
    # which unlock key is required (None = always available)
    requires_unlock: Optional[str] = None
    # which faction can recruit this
    faction_filter: Optional[str] = None   # None = any, or faction id
    guerilla: bool = False   # True = guerilla unit, gains conceal bonus
    can_ambush: bool = False
    can_subvert: bool = False   # can try to flip villages


UNIT_TYPES: Dict[str, UnitType] = {
    UT_CELL: UnitType(
        id=UT_CELL,
        name="Guerilla Cell",
        symbol="c",
        description="Small covert cell. Excellent at subversion and staying hidden. Weak in open combat.",
        hp_max=6, attack=2, defense=3, move=3, sight=2, stealth=3,
        cost_funds=30, cost_recruits=3, cost_weapons=1, upkeep_funds=5,
        guerilla=True, can_subvert=True,
    ),
    UT_PLATOON: UnitType(
        id=UT_PLATOON,
        name="Guerilla Platoon",
        symbol="p",
        description="Core combat unit. Mobile, adaptable, stronger in cover.",
        hp_max=10, attack=4, defense=3, move=3, sight=2, stealth=1,
        cost_funds=60, cost_recruits=6, cost_weapons=3, upkeep_funds=10,
        guerilla=True, can_ambush=True,
    ),
    UT_MILITIA: UnitType(
        id=UT_MILITIA,
        name="Village Militia",
        symbol="m",
        description="Local defenders. Cheap but limited. Strong defending their home village.",
        hp_max=8, attack=2, defense=4, move=2, sight=1, stealth=1,
        cost_funds=20, cost_recruits=4, cost_weapons=1, upkeep_funds=3,
        guerilla=True,
    ),
    UT_RECON: UnitType(
        id=UT_RECON,
        name="Recon Team",
        symbol="r",
        description="Intelligence specialists. Extended sight range, minimal combat role.",
        hp_max=5, attack=1, defense=2, move=4, sight=4, stealth=3,
        cost_funds=50, cost_recruits=3, cost_weapons=1, upkeep_funds=8,
        guerilla=True,
    ),
    UT_ADVISOR: UnitType(
        id=UT_ADVISOR,
        name="Foreign Advisor",
        symbol="A",
        description="Superpower-sponsored advisor. Boosts adjacent units and provides intel.",
        hp_max=6, attack=2, defense=2, move=3, sight=3, stealth=2,
        cost_funds=100, cost_recruits=1, cost_weapons=2, upkeep_funds=15,
        requires_unlock=None,   # eagle_advisor OR bear_advisor – checked in code
        guerilla=True,
    ),
    UT_HEAVY: UnitType(
        id=UT_HEAVY,
        name="Heavy Weapons",
        symbol="H",
        description="Heavy weapons team or armoured vehicle. Devastating but visible and expensive.",
        hp_max=14, attack=7, defense=5, move=2, sight=2, stealth=0,
        cost_funds=150, cost_recruits=4, cost_weapons=8, upkeep_funds=20,
        requires_unlock=None,   # eagle_heavy OR bear_armor – checked in code
        guerilla=False,
    ),
    UT_GOV_INF: UnitType(
        id=UT_GOV_INF,
        name="Government Infantry",
        symbol="G",
        description="Standard government troops. Professional but unmotivated.",
        hp_max=10, attack=4, defense=4, move=2, sight=3, stealth=0,
        cost_funds=0, cost_recruits=0, cost_weapons=0, upkeep_funds=0,
        faction_filter=F_GOV,
    ),
    UT_GOV_ARMOR: UnitType(
        id=UT_GOV_ARMOR,
        name="Government Armour",
        symbol="T",
        description="Armoured vehicle. Very powerful in open terrain, nearly helpless in jungle.",
        hp_max=18, attack=8, defense=7, move=3, sight=2, stealth=0,
        cost_funds=0, cost_recruits=0, cost_weapons=0, upkeep_funds=0,
        faction_filter=F_GOV,
    ),
    UT_GOV_POLICE: UnitType(
        id=UT_GOV_POLICE,
        name="Government Police",
        symbol="P",
        description="Counter-insurgency police. Good at detecting hidden units.",
        hp_max=7, attack=3, defense=3, move=2, sight=4, stealth=0,
        cost_funds=0, cost_recruits=0, cost_weapons=0, upkeep_funds=0,
        faction_filter=F_GOV,
    ),
}

# Rival guerilla unit mappings
RIVAL_UNIT_TYPES = [UT_CELL, UT_PLATOON, UT_RECON]


class Unit:
    """A single unit instance on the map."""
    _next_id = 1

    def __init__(self, type_id: str, owner: str, col: int, row: int):
        self.id = f"u{Unit._next_id}"
        Unit._next_id += 1
        self.type_id = type_id
        self.owner = owner
        self.col = col
        self.row = row
        utype = UNIT_TYPES[type_id]
        self.hp = utype.hp_max
        self.moves_left = utype.move
        self.has_acted = False
        # Bonus modifiers from unlocks/buffs
        self.attack_bonus = 0
        self.defense_bonus = 0
        self.move_bonus = 0
        self.sight_bonus = 0
        self.veteran = False   # earned through combat
        self.experience = 0
        # Temporary effects
        self.effects: List[str] = []

    @property
    def utype(self) -> UnitType:
        return UNIT_TYPES[self.type_id]

    @property
    def attack(self) -> int:
        return self.utype.attack + self.attack_bonus + (1 if self.veteran else 0)

    @property
    def defense(self) -> int:
        return self.utype.defense + self.defense_bonus + (1 if self.veteran else 0)

    @property
    def move(self) -> int:
        return self.utype.move + self.move_bonus

    @property
    def sight(self) -> int:
        return self.utype.sight + self.sight_bonus

    @property
    def stealth(self) -> int:
        return self.utype.stealth

    @property
    def hp_max(self) -> int:
        return self.utype.hp_max

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def new_turn(self):
        self.moves_left = self.move
        self.has_acted = False
        self.effects = [e for e in self.effects if not e.startswith("tmp_")]

    def take_damage(self, dmg: int):
        self.hp = max(0, self.hp - dmg)

    def heal(self, amount: int):
        self.hp = min(self.hp_max, self.hp + amount)

    def gain_xp(self, amount: int):
        self.experience += amount
        if self.experience >= 3 and not self.veteran:
            self.veteran = True
            return True  # just promoted
        return False

    def __repr__(self):
        return f"Unit({self.id} {self.utype.name} owner={self.owner} hp={self.hp}/{self.hp_max} at {self.col},{self.row})"


def calculate_combat(attacker: Unit, defender: Unit,
                     atk_tile_conceal: int, def_tile_conceal: int,
                     ambush: bool = False) -> Tuple[int, int, str]:
    """
    Resolve combat between attacker and defender.
    Returns (attacker_damage_taken, defender_damage_taken, log_str)
    """
    # Base values
    atk = attacker.attack
    def_ = defender.defense

    # Terrain modifiers for defender
    terrain_def_bonus = def_tile_conceal // 2
    def_ += terrain_def_bonus

    # Ambush: attacker gets full attack, defender gets no terrain bonus
    if ambush:
        def_ = max(1, def_ - terrain_def_bonus - 1)
        atk += 2

    # Dice roll – 2d6 style variance
    atk_roll = random.randint(1, 4)
    def_roll = random.randint(1, 4)

    raw_atk_dmg = max(0, atk + atk_roll - def_roll)
    raw_def_dmg = max(0, def_ + def_roll - atk_roll - 1)

    # Scale by HP ratio to avoid swingy one-shots
    atk_dmg = max(1, raw_atk_dmg) if raw_atk_dmg > 0 else 0
    def_dmg = max(1, raw_def_dmg) if raw_def_dmg > 0 else 0

    log = (f"{attacker.utype.name}(atk={atk}) vs {defender.utype.name}(def={def_}) "
           f"{'[AMBUSH] ' if ambush else ''}"
           f"→ defender takes {atk_dmg}, attacker takes {def_dmg}")
    return def_dmg, atk_dmg, log


def can_detect(observer: Unit, target: Unit,
               distance: int, target_tile_conceal: int) -> bool:
    """Check if observer can detect a stealthy target."""
    effective_sight = observer.sight - target.stealth - target_tile_conceal
    return effective_sight >= distance
