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


def idf_from_strength(score: int) -> int:
    """
    Base IDF derived from STR/POW.
      - STR 10 => IDF 1
      - STR 8  => IDF 0
      - +1 IDF per 2 STR above 10
    Clamped to >= 0.
    """
    try:
        score = int(score or 0)
    except Exception:
        score = 0
    idf = 1 + ((score - 10) // 2)
    return max(0, int(idf))
