# engine/stats.py

STAT_MOD_TABLE = {
    0: -5,
    1: -4,
    2: -4,
    3: -4,
    4: -3,
    5: -2,
    6: -2,
    7: -1,
    8: -1,
    10: 0,
    11: 0,
    12: 1,
    13: 1,   # your rule
    14: 1,
    15: 2,
    16: 2,  
    17: 3,
    18: 4,
    19: 4,
    20: 5,
    21: 5,
    22: 6
}

def stat_mod(score: int) -> int:
    # clamp to nearest supported key (or raise if you prefer strict)
    keys = sorted(STAT_MOD_TABLE.keys())
    if score in STAT_MOD_TABLE:
        return STAT_MOD_TABLE[score]
    # nearest lower key
    lower = max(k for k in keys if k <= score)
    return STAT_MOD_TABLE[lower]
