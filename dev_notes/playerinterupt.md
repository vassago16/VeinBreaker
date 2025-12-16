PLAYER_INTERRUPT_RULESET = {
  "interrupt_windows": [
    {
      "when": "before_link",
      "if": {"type": "chain_index_at_least", "value": 1},
      "rp_cost": 1,
      "priority": 10
    }
  ]
}

defender["_damage_taken_this_link"] = True