# Trading Card Maker

Static, client-side card generator for VeinBreaker abilities. Loads JSON, renders printable 3x3 sheets, and can pad to full sheets for clean printing.

## What it does
- Reads a local JSON file (or the built-in `abilities.json`) and renders each entry as a card.
- Supports both the VeinBreaker ability schema and a legacy TradingCard schema.
- Optional “Fill to 3x3” pads the last card until the sheet is complete for printing.
- Prints via the browser’s print dialog (`Print 3x3` button).

## How it works
- `index.html` wires up the controls and shows example schemas.
- `app.js` parses JSON, normalizes to an array from `abilities`, `cards`, or the root array, and builds cards in DOM.
- Images come from `image` / `imageUrl` fields (absolute, relative, or data URLs). Missing images fall back to a gradient background.
- `styles.css` handles the layout, gradients, and print-ready sizing.

## How to use
1) Open `trading-card-maker/index.html` in a browser (file:// works; no build needed).  
2) Click **Select JSON** and choose your file, or click **Load Sample** to use `abilities.json`.  
3) Leave **Fill to 3x3** on if you want full sheets (9 cards per page).  
4) Use **Print 3x3** to open the print dialog; pick your printer or “Save as PDF”.

Accepted JSON shapes:
```json
{ "abilities": [ { "path": "spellforged", "tier": 3, "name": "Law of the Stormcore", "type": "attack", "cost": 3, "cooldown": 3, "effect": "..." } ] }
{ "cards": [ { "name": "Law of the Stormcore", "type": "Attack", "attack": 8, "defense": 3, "description": "...", "imageUrl": "images/stormcore.jpg", "rarity": "rare", "setSymbol": "VB" } ] }
[ { "name": "...", "type": "...", "description": "..." } ]
```

## How to modify the cards
- Edit `abilities.json` (or your own file) and reload. Key fields the renderer looks for:
  - Ability schema: `path`, `tier`, `name`, `type`, `tags` (array), `cost`, `cooldown`, `effect`, `image` (or `imageUrl`), `rarity`, `setSymbol`.
  - Legacy schema: `name`, `type`, `attack`, `defense`, `description`, `imageUrl`, `rarity`, `setSymbol`.
  - Extras are ignored unless used above; missing fields simply do not render.
- To change visuals, tweak `styles.css` (colors, frames, print spacing) or adjust HTML structure in `index.html`.
- To change layout logic (padding, schema detection, text), edit `app.js` in `renderData` or `renderCard` and reload the page.
