# Veinbreaker Tooling

This repo contains the working files and generators for the Veinbreaker TTRPG: rules, wiki exports, bestiary, and path/ability lists.

## What is here
- docs/wiki: Markdown pages for the wiki (player guide, GM codex, bestiary grids, abilities by tier, sidebar).
- monster-maker: Enemy data (archetypes, enemies, beasts) and a builder that outputs JSON and Markdown for the bestiary.
- Path-maker: Ability data and a builder that outputs Markdown tables for abilities by tier.
- GM Guide / Player Guide: Source text for the game.

## Tools
- monster-maker/build_bestiary.py
  - Reads archetype.json, enemy.json, and any beasts in bestiary/beasts/*.json.
  - Merges archetype defaults with enemy overrides.
  - Outputs monster-maker/bestiary.json.
  - Generates Markdown either per enemy, per tier grid, or both (default).
  - Copies tier grid files into docs/wiki (names: tier-#-beasts.md).
  - Configure via monster-maker/config.json, e.g.:
    {
      "markdown_mode": "both",  // options: single, grid, both
      "markdown_columns": 3
    }

- Path-maker/build_abilities.py
  - Reads abilities.json and groups by tier.
  - Outputs Markdown tables (3 columns) to Path-maker/build/tier-#-abilities.md.
  - Copies those tier files into docs/wiki.

## How to run
From repo root (PowerShell):

- Build bestiary (JSON + Markdown, copies tier grids to wiki):
  python monster-maker/build_bestiary.py

- Build abilities by tier (copies to wiki):
  python Path-maker/build_abilities.py

## Wiki sidebar
- Sidebar links to bestiary tiers (tier-#-beasts.md) and ability tiers (tier-#-abilities.md) are in docs/wiki/_Sidebar.md.
- After running the builders, the new files are available for the wiki publish action.

## Notes
- Markdown outputs use ASCII-safe characters; emojis in sidebar are encoded as HTML entities.
- Bestiary beast files can be added under monster-maker/bestiary/beasts/ as JSON (single enemy, list, or {"enemies": [...] }). They are auto-ingested by the builder.


## ⚠️ Rights & Usage Notice

This repository is provided for reference and discussion only.

All content, code, mechanics, and narrative elements are © [Chris Weeks] [2026].  
All rights reserved.

No license is granted to copy, modify, distribute, or use this material without
explicit written permission from the author.
