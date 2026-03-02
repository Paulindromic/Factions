# factions.py – Faction definitions and relationship system

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .constants import *


@dataclass
class FactionDef:
    id: str
    name: str
    short: str          # 2-3 letter abbreviation
    color: tuple        # (R,G,B)
    description: str
    is_superpower: bool = False
    is_guerilla: bool = False
    is_government: bool = False
    is_minor: bool = False
    # What they can provide at various relationship levels
    # List of (rel_threshold, unlock_key, description)
    unlocks: List[tuple] = field(default_factory=list)
    # Starting relationship with player
    start_rel: int = 0
    # Starting relationship with government
    gov_rel: int = 0
    # AI personality weights
    ai_aggression: float = 0.5
    ai_greed: float = 0.5


FACTIONS: Dict[str, FactionDef] = {
    F_PLAYER: FactionDef(
        id=F_PLAYER,
        name="Liberation Front",
        short="LF",
        color=(80, 200, 120),
        description="Your guerilla movement. Fight for independence and shape the nation's future.",
        is_guerilla=True,
    ),
    F_EAGLE: FactionDef(
        id=F_EAGLE,
        name="Eagle Alliance",
        short="EA",
        color=(60, 100, 200),
        description="A western superpower funding anti-communist movements worldwide. Generous but ideologically demanding.",
        is_superpower=True,
        start_rel=5,
        gov_rel=30,
        ai_aggression=0.4,
        ai_greed=0.7,
        unlocks=[
            (20, "eagle_funds",    "Regular funding (Eagle): +30 funds/turn"),
            (20, "eagle_medic",    "Medical Advisors: Units heal +1 HP/turn in friendly territory"),
            (35, "eagle_intel",    "CIA briefings: +2 Intel/turn, reveal rival positions"),
            (50, "eagle_advisor",  "Military Advisors: Can train Advisor units"),
            (50, "eagle_weapons",  "M16 Shipment: Unlock Light Weapons cache (units +1 attack)"),
            (70, "eagle_heavy",    "Heavy Weapons: Unlock Heavy unit type"),
            (85, "eagle_airsupp",  "Air Support: Once per 5 turns, call airstrike on target hex"),
        ],
    ),
    F_BEAR: FactionDef(
        id=F_BEAR,
        name="Bear Collective",
        short="BC",
        color=(200, 60, 60),
        description="An eastern superpower backing socialist liberation movements. Provides robust military equipment.",
        is_superpower=True,
        start_rel=5,
        gov_rel=-20,
        ai_aggression=0.6,
        ai_greed=0.6,
        unlocks=[
            (20, "bear_funds",    "Regular funding (Bear): +25 funds/turn"),
            (20, "bear_recon",    "Recon Training: Recon units +1 range"),
            (35, "bear_weapons",  "AK Shipment: Platoons gain +1 attack, -10 cost"),
            (50, "bear_advisor",  "Political Commissars: Villages under control +1 loyalty/turn"),
            (50, "bear_armor",    "Armored Vehicles: Unlock Heavy unit type"),
            (70, "bear_intel",    "KGB Network: +3 Intel/turn, chance to flip rival cells"),
            (85, "bear_artillery","Artillery Support: +2 attack for adjacent friendly units 1/4 turns"),
        ],
    ),
    F_CROSS: FactionDef(
        id=F_CROSS,
        name="Neutral Cross",
        short="NC",
        color=(220, 50, 50),
        description="A small neutral nation providing humanitarian aid. Raises legitimacy globally but won't arm you.",
        is_minor=True,
        start_rel=10,
        gov_rel=20,
        ai_aggression=0.1,
        ai_greed=0.2,
        unlocks=[
            (20, "cross_aid",      "Humanitarian Aid: +1 recruit/turn, villages +loyalty"),
            (35, "cross_hospital", "Field Hospitals: Units heal 2x in any terrain"),
            (50, "cross_legit",    "International Recognition: +5 Influence/turn, rivals -5"),
            (70, "cross_immunity", "Protected Status: Government cannot target player villages diplomatically"),
            (85, "cross_ceasefire","Ceasefire Broker: Force 3-turn ceasefire with government once"),
        ],
    ),
    F_OIL: FactionDef(
        id=F_OIL,
        name="Oil Sheikdom",
        short="OS",
        color=(220, 180, 40),
        description="A wealthy oil state with money to burn. Purely transactional – they want stability and trade routes.",
        is_minor=True,
        start_rel=0,
        gov_rel=15,
        ai_aggression=0.2,
        ai_greed=0.9,
        unlocks=[
            (20, "oil_funds",     "Oil Money: +40 funds/turn"),
            (35, "oil_smuggle",   "Smuggling Network: Buy weapons at -30% cost"),
            (50, "oil_bribe",     "Bribery Fund: Can bribe government officials (reduce gov action points)"),
            (70, "oil_pipeline",  "Pipeline Deal: +80 funds/turn, but must protect route (hex)"),
            (85, "oil_private",   "Private Security: Hire mercenary Heavy units"),
        ],
    ),
    F_JAGUAR: FactionDef(
        id=F_JAGUAR,
        name="Southern Tiger",
        short="ST",
        color=(40, 180, 100),
        description="A regional power building its own influence. Offers training and a diplomatic voice in regional affairs.",
        is_minor=True,
        start_rel=0,
        gov_rel=10,
        ai_aggression=0.3,
        ai_greed=0.5,
        unlocks=[
            (20, "jag_training",  "Jungle Training: All units +1 defense in jungle/mountain"),
            (35, "jag_smuggle",   "Regional Contacts: +10 funds/turn per controlled village"),
            (50, "jag_recon",     "Counter-Intel: +2 Intel, enemies have -1 detection range"),
            (70, "jag_weapons",   "Regional Arms: Unlock Militia upgrade to trained Platoon"),
            (85, "jag_shield",    "Diplomatic Shield: Protects against superpower sanctions for 5 turns"),
        ],
    ),
    F_GOV: FactionDef(
        id=F_GOV,
        name="Central Government",
        short="GOV",
        color=(160, 160, 180),
        description="The ruling government – corrupt, slow, but still powerful. Too much attention invites crackdowns.",
        is_government=True,
        start_rel=-10,
        gov_rel=100,
        ai_aggression=0.5,
        ai_greed=0.4,
    ),
    F_RIVAL1: FactionDef(
        id=F_RIVAL1,
        name="Red Vanguard",
        short="RV",
        color=(200, 80, 40),
        description="A rival guerilla movement with communist leanings. Competes for territory and recruits.",
        is_guerilla=True,
        start_rel=-5,
        ai_aggression=0.7,
        ai_greed=0.6,
    ),
    F_RIVAL2: FactionDef(
        id=F_RIVAL2,
        name="National Legion",
        short="NL",
        color=(180, 140, 40),
        description="A rival nationalist guerilla force. Ruthless and territorial.",
        is_guerilla=True,
        start_rel=-5,
        ai_aggression=0.8,
        ai_greed=0.5,
    ),
}


class RelationshipManager:
    """Tracks relationships between all faction pairs."""

    def __init__(self):
        self.relations: Dict[tuple, int] = {}
        # Initialise default relationships
        self._init_defaults()

    def _init_defaults(self):
        ids = list(FACTIONS.keys())
        for i, a in enumerate(ids):
            for b in ids[i+1:]:
                key = self._key(a, b)
                self.relations[key] = 0

        # Set meaningful starting values
        self._set(F_EAGLE, F_BEAR,   -60)  # Cold War rivals
        self._set(F_EAGLE, F_GOV,     30)  # Eagle backs the government
        self._set(F_BEAR,  F_GOV,    -20)  # Bear dislikes government
        self._set(F_EAGLE, F_CROSS,   20)
        self._set(F_BEAR,  F_CROSS,   10)
        self._set(F_CROSS, F_GOV,     25)
        self._set(F_OIL,   F_EAGLE,   35)  # Oil close to Eagle
        self._set(F_OIL,   F_BEAR,   -10)
        self._set(F_JAGUAR, F_EAGLE, -15)  # Tiger wary of Eagle hegemony
        self._set(F_JAGUAR, F_BEAR,    5)
        self._set(F_GOV,   F_RIVAL1, -80)
        self._set(F_GOV,   F_RIVAL2, -80)
        self._set(F_GOV,   F_PLAYER, -10)
        self._set(F_RIVAL1, F_RIVAL2,-40)
        self._set(F_RIVAL1, F_PLAYER,-15)
        self._set(F_RIVAL2, F_PLAYER,-15)
        # Player starts with slight relationships per faction defs
        for fid, fdef in FACTIONS.items():
            if fid != F_PLAYER:
                self._set(F_PLAYER, fid, fdef.start_rel)

    def _key(self, a: str, b: str) -> tuple:
        return (min(a, b), max(a, b))

    def _set(self, a: str, b: str, val: int):
        self.relations[self._key(a, b)] = max(-100, min(100, val))

    def get(self, a: str, b: str) -> int:
        return self.relations.get(self._key(a, b), 0)

    def change(self, a: str, b: str, delta: int, log: Optional[List] = None):
        key = self._key(a, b)
        old = self.relations.get(key, 0)
        new = max(-100, min(100, old + delta))
        self.relations[key] = new
        if log is not None and delta != 0:
            sign = "+" if delta > 0 else ""
            log.append(f"Relations {FACTIONS[a].short}↔{FACTIONS[b].short}: {sign}{delta} ({old}→{new})")
        return new - old   # actual change applied

    def apply_superpower_rivalry(self, player_id: str, superpower: str, gain: int,
                                 log: Optional[List] = None):
        """When player builds with one superpower past soft-cap, penalise rival superpower relation."""
        rival = F_BEAR if superpower == F_EAGLE else F_EAGLE
        current_with_rival = self.get(player_id, rival)
        penalty = int(gain * REL_RIVAL_PENALTY)
        if penalty > 0 and current_with_rival > REL_HOSTILE:
            self.change(player_id, rival, -penalty, log)

    def get_label(self, val: int) -> str:
        if val >= REL_ALLY:       return "Allied"
        if val >= REL_FRIENDLY:   return "Friendly"
        if val >= REL_NEUTRAL:    return "Neutral"
        if val >= REL_UNFRIENDLY: return "Cold"
        return "Hostile"

    def get_label_color(self, val: int) -> tuple:
        if val >= REL_FRIENDLY:   return C_TEXT_GOOD
        if val >= REL_NEUTRAL:    return C_TEXT
        if val >= REL_UNFRIENDLY: return C_TEXT_WARN
        return C_TEXT_BAD


class UnlockManager:
    """Tracks which faction unlocks the player has earned."""

    def __init__(self):
        self.unlocked: set = set()
        self._notified: set = set()

    def check_unlocks(self, player_id: str, rels: RelationshipManager) -> List[str]:
        """Return list of newly unlocked keys."""
        newly = []
        for fid, fdef in FACTIONS.items():
            if fid == player_id:
                continue
            rel = rels.get(player_id, fid)
            for threshold, key, desc in fdef.unlocks:
                if rel >= threshold and key not in self.unlocked:
                    self.unlocked.add(key)
                    if key not in self._notified:
                        self._notified.add(key)
                        newly.append((key, desc, fdef.name))
        return newly

    def has(self, key: str) -> bool:
        return key in self.unlocked
