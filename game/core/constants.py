# constants.py - Game-wide constants

# Screen
SCREEN_W = 1280
SCREEN_H = 800
FPS = 30
TITLE = "Factions – Cold War Shadow War"

# Map
HEX_SIZE = 36          # pixel radius of each hex
MAP_COLS = 22
MAP_ROWS = 16

# Colours (R, G, B)
C_BG          = (18,  20,  24)
C_PANEL_BG    = (28,  32,  40)
C_PANEL_BORD  = (60,  70,  90)
C_TEXT        = (220, 220, 210)
C_TEXT_DIM    = (120, 130, 140)
C_TEXT_GOOD   = (100, 220, 120)
C_TEXT_BAD    = (220,  90,  80)
C_TEXT_WARN   = (220, 200,  80)
C_BUTTON      = (45,  55,  75)
C_BUTTON_HOV  = (65,  80, 110)
C_BUTTON_ACT  = (90, 130, 170)
C_TOOLTIP_BG  = (20,  25,  35)
C_HIGHLIGHT   = (255, 230,  80)
C_SELECT      = (80,  200, 255)
C_DANGER      = (220,  60,  60)

# Terrain colours
TERRAIN_COLORS = {
    "jungle":    (34,  85,  34),
    "savanna":   (140, 160,  60),
    "river":     (40,  100, 180),
    "village":   (180, 150,  80),
    "city":      (160, 160, 160),
    "mountain":  (120, 110, 100),
    "plain":     (100, 140,  60),
    "coast":     (60,  130, 180),
}

TERRAIN_NAMES = {
    "jungle":   "Jungle",
    "savanna":  "Savanna",
    "river":    "River Delta",
    "village":  "Village",
    "city":     "City",
    "mountain": "Mountains",
    "plain":    "Plains",
    "coast":    "Coastline",
}

# Terrain movement cost
TERRAIN_MOVE_COST = {
    "jungle":   2,
    "savanna":  1,
    "river":    3,
    "village":  1,
    "city":     1,
    "mountain": 3,
    "plain":    1,
    "coast":    2,
}

# Terrain concealment bonus (how hard to detect guerilla)
TERRAIN_CONCEAL = {
    "jungle":   3,
    "savanna":  1,
    "river":    1,
    "village":  2,
    "city":     1,
    "mountain": 2,
    "plain":    0,
    "coast":    0,
}

# Faction IDs
F_PLAYER   = "player"
F_EAGLE    = "eagle"    # USA analog
F_BEAR     = "bear"     # USSR analog
F_CROSS    = "cross"    # Switzerland analog
F_OIL      = "oil"      # Saudi Arabia analog
F_JAGUAR   = "jaguar"   # Brazil analog
F_GOV      = "gov"      # Central Government
F_RIVAL1   = "rival1"   # Rival guerilla movement 1
F_RIVAL2   = "rival2"   # Rival guerilla movement 2

# Relationship thresholds
REL_HOSTILE    = -100
REL_UNFRIENDLY = -30
REL_NEUTRAL    =   0
REL_FRIENDLY   =  40
REL_ALLY       =  70
REL_MAX        = 100

# Soft cap: above this, building with one faction hurts others
REL_SOFTCAP = 35

# Relationship penalty applied to rivals when you advance with a superpower
REL_RIVAL_PENALTY = 0.6   # fraction of gain applied as loss to rival superpower

# Action costs (in movement points or turns)
MOVE_POINTS_DEFAULT = 3

# Resource types
RES_FUNDS    = "funds"
RES_RECRUITS = "recruits"
RES_WEAPONS  = "weapons"
RES_INTEL    = "intel"
RES_INFLUENCE= "influence"

# Starting resources
START_RESOURCES = {
    RES_FUNDS:     200,
    RES_RECRUITS:  10,
    RES_WEAPONS:   5,
    RES_INTEL:     0,
    RES_INFLUENCE: 0,
}

# Income per controlled village/city per turn
INCOME_VILLAGE = {RES_FUNDS: 15, RES_RECRUITS: 2}
INCOME_CITY    = {RES_FUNDS: 40, RES_RECRUITS: 3, RES_INFLUENCE: 1}

# Profile / visibility
PROFILE_LOW    = "low"
PROFILE_MEDIUM = "medium"
PROFILE_HIGH   = "high"

# Unit types
UT_CELL        = "cell"          # small guerilla cell – cheap, stealthy
UT_PLATOON     = "platoon"       # guerilla platoon – combat
UT_MILITIA     = "militia"       # village militia – defensive
UT_RECON       = "recon"         # intelligence unit
UT_ADVISOR     = "advisor"       # foreign advisor (unlocked via faction)
UT_HEAVY       = "heavy"         # heavy weapons (unlocked via faction)
UT_GOV_INF     = "gov_infantry"  # government infantry
UT_GOV_ARMOR   = "gov_armor"     # government armored vehicle
UT_GOV_POLICE  = "gov_police"    # government police

# AI behaviour modes
AI_EXPAND  = "expand"
AI_DEFEND  = "defend"
AI_SUBVERT = "subvert"
AI_LIE_LOW = "lie_low"

# Event categories
EV_DIPLOMATIC = "diplomatic"
EV_MILITARY   = "military"
EV_ECONOMIC   = "economic"
EV_POLITICAL  = "political"
EV_RANDOM     = "random"

# Win conditions
WIN_DOMINANCE    = "dominance"    # control 60% of cities
WIN_REVOLUTION   = "revolution"   # destroy government
WIN_NEGOTIATED   = "negotiated"   # high influence + low profile = political win
WIN_DEFEAT       = "defeat"       # player eliminated

# Turn limit
MAX_TURNS = 80

# UI layout
SIDEBAR_W  = 280
BOTTOM_H   = 160
MAP_X      = SIDEBAR_W
MAP_Y      = 0
MAP_W      = SCREEN_W - SIDEBAR_W
MAP_H      = SCREEN_H - BOTTOM_H
