# events.py – Random and scripted event system

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from .constants import *


@dataclass
class GameEvent:
    id: str
    category: str
    title: str
    description: str
    # List of (label, effect_fn) choices the player can take
    # effect_fn signature: (game_state) -> str (result description)
    choices: List[tuple] = field(default_factory=list)
    # Conditions: (game_state) -> bool
    condition: Optional[Callable] = None
    # Once only?
    once: bool = True
    # Minimum turn to fire
    min_turn: int = 0
    # Weight for random selection
    weight: float = 1.0


def make_events() -> List[GameEvent]:
    """Return the library of possible game events."""
    events = []

    # ── Diplomatic Events ──────────────────────────────────────────────────
    events.append(GameEvent(
        id="ev_eagle_approaches",
        category=EV_DIPLOMATIC,
        title="Eagle Alliance Approaches",
        description=(
            "An Eagle Alliance attaché makes contact in the capital's back-alleys. "
            "'We know your struggle,' he says, setting down a briefcase. "
            "'We can make things… easier. But we expect certain commitments.'"
        ),
        choices=[
            ("Accept discreetly (+15 Eagle, +50 funds, -10 Bear)",
             lambda gs: gs.event_effect_rel(F_EAGLE, +15, funds=50, rival_pen=True)),
            ("Decline politely (no change)",
             lambda gs: "You decline the offer without burning bridges."),
            ("Demand more (+5 Eagle chance, or anger them)",
             lambda gs: gs.event_bluff_eagle()),
        ],
        min_turn=3, once=True,
    ))

    events.append(GameEvent(
        id="ev_bear_radio",
        category=EV_DIPLOMATIC,
        title="Bear Collective Radio Contact",
        description=(
            "A scratchy shortwave signal: comrades from the Bear Collective reach out. "
            "They offer logistical support 'for the liberation struggle.' "
            "Their weapons are proven – and plentiful."
        ),
        choices=[
            ("Engage (+15 Bear, +30 funds, -10 Eagle)",
             lambda gs: gs.event_effect_rel(F_BEAR, +15, funds=30, rival_pen=True)),
            ("Politely decline (no change)",
             lambda gs: "You keep your options open."),
            ("Counter-offer: intelligence exchange (+10 Bear, +5 Intel)",
             lambda gs: gs.event_effect_rel(F_BEAR, +10, intel=5)),
        ],
        min_turn=5, once=True,
    ))

    events.append(GameEvent(
        id="ev_neutral_aid",
        category=EV_DIPLOMATIC,
        title="Neutral Cross Medical Mission",
        description=(
            "A Neutral Cross convoy rolls into a village near your operating area. "
            "The doctor in charge quietly asks if your fighters need medical attention – "
            "no questions asked."
        ),
        choices=[
            ("Accept – allow access (+15 Cross, all units +2 HP)",
             lambda gs: gs.event_heal_all(15)),
            ("Decline to avoid attention (no change)",
             lambda gs: "You keep your distance to preserve operational security."),
        ],
        min_turn=2, once=True,
    ))

    events.append(GameEvent(
        id="ev_oil_contact",
        category=EV_DIPLOMATIC,
        title="Oil Sheikdom Trade Offer",
        description=(
            "A discreet message from the Oil Sheikdom: they are worried about instability "
            "affecting their interests. They will fund any group that can 'guarantee' the trade routes."
        ),
        choices=[
            ("Promise to protect their routes (+20 Oil, +80 funds, new objective)",
             lambda gs: gs.event_oil_deal()),
            ("Decline – no strings attached",
             lambda gs: "You remain independent of petrostate money."),
        ],
        min_turn=8, once=True,
    ))

    events.append(GameEvent(
        id="ev_jaguar_solidarity",
        category=EV_DIPLOMATIC,
        title="Southern Tiger Solidarity",
        description=(
            "Guerilla fighters from the Southern Tiger nation have slipped across the border. "
            "They've come with knowledge of jungle tactics learned in their own wars."
        ),
        choices=[
            ("Welcome them (+15 Tiger, all units +1 defense in jungle)",
             lambda gs: gs.event_effect_rel(F_JAGUAR, +15, buff="jungle_def")),
            ("Accept covertly (+8 Tiger, avoid attention)",
             lambda gs: gs.event_effect_rel(F_JAGUAR, +8, buff="jungle_def")),
        ],
        min_turn=4, once=True,
    ))

    # ── Military Events ────────────────────────────────────────────────────
    events.append(GameEvent(
        id="ev_gov_sweep",
        category=EV_MILITARY,
        title="Government Sweep Operation",
        description=(
            "Military intelligence reports a major government sweep is being planned "
            "in your primary operating zone. Troops are massing at the nearest city."
        ),
        choices=[
            ("Scatter and hide (units move to jungle, -2 profile turns)",
             lambda gs: gs.event_scatter_units()),
            ("Prepare an ambush (risk: -20% chance of big combat victory)",
             lambda gs: gs.event_ambush_gov()),
            ("Bribe a general (-60 funds, sweep is called off)",
             lambda gs: gs.event_bribe_gen()),
        ],
        condition=lambda gs: gs.profile_level != PROFILE_LOW,
        min_turn=6, once=False, weight=0.8,
    ))

    events.append(GameEvent(
        id="ev_rival_attack",
        category=EV_MILITARY,
        title="Rival Movement Attack",
        description=(
            "A rival guerilla movement has attacked one of your cells! "
            "They struck fast and faded into the jungle."
        ),
        choices=[
            ("Pursue and retaliate (risk combat, +10 militia morale)",
             lambda gs: gs.event_retaliate_rival()),
            ("Let it go – focus on the mission (avoid escalation)",
             lambda gs: "You swallow the insult and stay focused."),
            ("Send a message – assassinate their leader (-80 funds)",
             lambda gs: gs.event_assassinate_rival()),
        ],
        condition=lambda gs: len([u for u in gs.all_units.values()
                                  if u.owner in (F_RIVAL1, F_RIVAL2)]) > 2,
        min_turn=5, once=False, weight=0.7,
    ))

    events.append(GameEvent(
        id="ev_weapons_cache",
        category=EV_MILITARY,
        title="Abandoned Weapons Cache",
        description=(
            "Your scouts find a cache of abandoned weapons from a previous conflict – "
            "rusted but serviceable rifles, ammunition, even a mortar."
        ),
        choices=[
            ("Secure the cache (+15 weapons)",
             lambda gs: gs.event_gain_resources(weapons=15)),
            ("Share with local militia (+8 weapons, +10 village loyalty)",
             lambda gs: gs.event_gain_resources(weapons=8, loyalty_bonus=True)),
        ],
        min_turn=3, once=False, weight=0.6,
    ))

    events.append(GameEvent(
        id="ev_defector",
        category=EV_MILITARY,
        title="Government Defector",
        description=(
            "A government army sergeant approaches your camp. He's disgusted by the "
            "regime's corruption and wants to join. He knows troop dispositions."
        ),
        choices=[
            ("Accept (+5 Intel, +1 recruit, minor profile raise)",
             lambda gs: gs.event_gain_resources(intel=5, recruits=1, profile_up=True)),
            ("Interrogate only (+8 Intel, send him back)",
             lambda gs: gs.event_gain_resources(intel=8)),
            ("Turn him away (safe, no gain)",
             lambda gs: "You send him away. Can't risk an informer."),
        ],
        min_turn=4, once=False, weight=0.5,
    ))

    # ── Economic Events ────────────────────────────────────────────────────
    events.append(GameEvent(
        id="ev_tax_convoy",
        category=EV_ECONOMIC,
        title="Government Tax Convoy",
        description=(
            "A government tax convoy is passing through your territory, "
            "laden with funds extracted from the villages. Easy pickings – "
            "but raiding it will anger the government."
        ),
        choices=[
            ("Raid the convoy (+80 funds, +10 gov hostility, +profile)",
             lambda gs: gs.event_raid_convoy()),
            ("Let it pass (maintain low profile)",
             lambda gs: "You let the convoy pass. Pick your battles."),
            ("Rob discreetly (+40 funds, +5 gov hostility, disguised)",
             lambda gs: gs.event_raid_convoy(half=True)),
        ],
        min_turn=3, once=False, weight=0.7,
    ))

    events.append(GameEvent(
        id="ev_drought",
        category=EV_ECONOMIC,
        title="Regional Drought",
        description=(
            "A severe drought is crippling the region. Villages are struggling. "
            "This is a chance to show the people who cares for them – "
            "or to exploit their desperation."
        ),
        choices=[
            ("Distribute food aid (+20 village loyalty, -50 funds)",
             lambda gs: gs.event_gain_resources(funds=-50, loyalty_bonus=True, big=True)),
            ("Do nothing – wait it out",
             lambda gs: "You conserve resources and wait."),
            ("Blame the government (propaganda: +5 Influence, +10 village loyalty)",
             lambda gs: gs.event_gain_resources(influence=5, loyalty_bonus=True)),
        ],
        min_turn=10, once=False, weight=0.4,
    ))

    # ── Political Events ───────────────────────────────────────────────────
    events.append(GameEvent(
        id="ev_press_story",
        category=EV_POLITICAL,
        title="Foreign Press Interest",
        description=(
            "A foreign journalist has found your movement and wants to write a story. "
            "International attention is a double-edged sword."
        ),
        choices=[
            ("Grant interview (+10 Influence, +profile exposure)",
             lambda gs: gs.event_gain_resources(influence=10, profile_up=True)),
            ("Decline – operational security first",
             lambda gs: "You stay in the shadows."),
            ("Arrange controlled interview (+5 Influence, no profile change)",
             lambda gs: gs.event_gain_resources(influence=5)),
        ],
        min_turn=7, once=False, weight=0.5,
    ))

    events.append(GameEvent(
        id="ev_gov_corruption",
        category=EV_POLITICAL,
        title="Government Corruption Scandal",
        description=(
            "A major corruption scandal rocks the capital. Government credibility is at "
            "an all-time low. The people are angry. This is your moment."
        ),
        choices=[
            ("Launch propaganda campaign (+15 Influence, -5 gov legitimacy)",
             lambda gs: gs.event_gain_resources(influence=15, weaken_gov=True)),
            ("Offer to 'help' with anti-corruption (+8 Cross rel, +5 Influence)",
             lambda gs: gs.event_effect_rel(F_CROSS, +8, influence=5)),
            ("Stay quiet – let them destroy themselves",
             lambda gs: "You watch the government burn from the sidelines."),
        ],
        condition=lambda gs: gs.turn > 10,
        min_turn=10, once=True, weight=0.8,
    ))

    events.append(GameEvent(
        id="ev_peace_talks",
        category=EV_POLITICAL,
        title="Peace Talks Proposed",
        description=(
            "The government, weakened by your operations and internal scandal, "
            "proposes talks. The international community applauds. "
            "But peace now may mean less gain later."
        ),
        choices=[
            ("Attend talks (+20 Cross, +10 Influence, -20 Bear, ceasefire 5 turns)",
             lambda gs: gs.event_peace_talks()),
            ("Publicly refuse (governments don't negotiate in good faith)",
             lambda gs: gs.event_gain_resources(influence=-5, profile_up=False)),
            ("Attend, then sabotage (+5 Influence short term, -20 Cross later)",
             lambda gs: gs.event_sabotage_talks()),
        ],
        condition=lambda gs: gs.government_hp < 60,
        min_turn=20, once=True, weight=1.0,
    ))

    return events


class EventQueue:
    """Manages scheduling and delivery of game events."""

    def __init__(self):
        self.library = make_events()
        self.fired: set = set()
        self.pending: List[GameEvent] = []
        self._rng = random.Random()

    def seed(self, s):
        self._rng.seed(s)

    def check_events(self, game_state) -> List[GameEvent]:
        """Check for events that should fire this turn."""
        triggered = []
        for ev in self.library:
            if ev.once and ev.id in self.fired:
                continue
            if game_state.turn < ev.min_turn:
                continue
            if ev.condition and not ev.condition(game_state):
                continue
            # Random weight check (20% base chance per turn)
            if self._rng.random() < 0.20 * ev.weight:
                triggered.append(ev)
                if ev.once:
                    self.fired.add(ev.id)
        # Return at most 1 event per turn to avoid overwhelming the player
        if triggered:
            return [self._rng.choice(triggered)]
        return []
