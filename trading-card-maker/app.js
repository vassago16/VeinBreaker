const $ = (sel, ctx=document) => ctx.querySelector(sel);
const cardsEl = $('#cards');
const fillGridEl = $('#fillGrid');

$('#jsonFile').addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    renderData(data);
  } catch(err){
    alert('Failed to read JSON: ' + err.message);
  }
});

$('#loadSample').addEventListener('click', async () => {
  try {
    const res = await fetch('abilities.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    renderData(data);
  } catch(err){
    alert('Failed to load abilities.json: ' + err.message);
  }
});

$('#printBtn').addEventListener('click', () => {
  window.print();
});

function renderData(data){
  let arr = Array.isArray(data)
    ? data
    : Array.isArray(data.cards)
      ? data.cards
      : Array.isArray(data.abilities)
        ? data.abilities
        : [];
  if (!arr.length){
    cardsEl.innerHTML = '<p style="color:#9fb3c8">No cards found in JSON. Expected `{ abilities: [...] }`, `{ cards: [...] }`, or an array.</p>';
    return;
  }
  // If requested, pad to full 3x3 sheets by repeating the last card
  if (fillGridEl && fillGridEl.checked){
    const remainder = arr.length % 9;
    if (remainder){
      const toAdd = 9 - remainder;
      const last = arr[arr.length - 1] || {};
      for (let i=0;i<toAdd;i++) arr.push(last);
    }
  }

  cardsEl.innerHTML = '';
  arr.forEach((card, idx) => cardsEl.appendChild(renderCard(card, idx)));
}

function renderCard(card, idx){
  // Support ability schema, previous schema, and TradingCard schema
  const isAbility = 'path' in (card || {}) || 'tier' in (card || {});
  const isTrading = !isAbility && ('description' in (card||{}) || 'imageUrl' in (card||{}));

  const title = (card.name || card.title || 'Untitled');
  const type = card.type || '';
  const cost = isAbility ? (card.cost ?? '') : (!isTrading ? (card.cost || '') : '');
  const cooldown = isAbility ? (card.cooldown ?? '') : (!isTrading ? (card.cooldown || '') : '');
  const effect = isAbility ? (card.effect || '') : (card.description || card.effect || '');
  const image = card.imageUrl || card.image || '';
  const attack = isTrading ? (card.attack ?? undefined) : undefined;
  const defense = isTrading ? (card.defense ?? undefined) : undefined;
  const rarity = (isTrading ? (card.rarity || 'common') : (card.rarity || '')) || 'common';
  const setSymbol = isAbility
    ? (card.path ? card.path.toUpperCase().slice(0,3) : '')
    : (card.setSymbol || '');

  const el = document.createElement('article');
  el.className = 'card';
  el.setAttribute('role','group');
  el.setAttribute('aria-label', title);

  // Background layers
  const bg = document.createElement('div');
  bg.className = 'card__bg';
  const vignette = document.createElement('div');
  vignette.className = 'card__vignette';

  // Content frame
  const content = document.createElement('div');
  content.className = 'card__content';

  // Title bar
  const titlebar = document.createElement('div');
  titlebar.className = 'titlebar';
  titlebar.textContent = title;

  // Emblems (rarity pip + set symbol)
  const emblems = document.createElement('div');
  emblems.className = 'emblems';
  const pip = document.createElement('span');
  pip.className = 'rarity ' + rarity.toLowerCase();
  emblems.appendChild(pip);
  if (setSymbol){
    const set = document.createElement('span');
    set.className = 'set-symbol';
    set.textContent = setSymbol;
    emblems.appendChild(set);
  }
  titlebar.appendChild(emblems);

  // Art window
  const art = document.createElement('div');
  art.className = 'image-box';
  if (image) art.style.backgroundImage = `url("${image}")`;

  // Type line and optional cost/cooldown badges (legacy)
  const typeline = document.createElement('div');
  typeline.className = 'typeline';
  const parts = [];
  if (type) parts.push(type);
  if (isAbility && card.tier) parts.push('Tier ' + card.tier);
  if (!isAbility && !isTrading && cost) parts.push('Cost: ' + cost);
  if (!isAbility && !isTrading && cooldown) parts.push('CD: ' + cooldown);
  typeline.textContent = parts.join(' • ');

  // Text box
  const textbox = document.createElement('div');
  textbox.className = 'textbox';
  textbox.textContent = effect;

  // Stats (ATK/DEF) for TradingCard
  if (isTrading && (attack !== undefined || defense !== undefined)){
    const stats = document.createElement('div');
    stats.className = 'stats';
    if (attack !== undefined){
      const s = document.createElement('div');
      s.className = 'stat';
      s.textContent = 'ATK ' + attack;
      stats.appendChild(s);
    }
    if (defense !== undefined){
      const s = document.createElement('div');
      s.className = 'stat';
      s.textContent = 'DEF ' + defense;
      stats.appendChild(s);
    }
    content.appendChild(stats);
  }

  // Footer
  const footer = document.createElement('div');
  footer.className = 'card__footer';
  const brand = document.createElement('div');
  brand.className = 'brand';
  brand.textContent = 'VeinBreaker — Card ' + (idx+1);
  footer.appendChild(brand);

  // Cost + cooldown overlay inside the art window for ability schema
  if (isAbility && (cost !== '' || cooldown !== '')){
    const overlay = document.createElement('div');
    overlay.className = 'image-overlay';
    if (cost !== ''){
      const c = document.createElement('span');
      c.className = 'overlay-badge';
      c.textContent = 'Cost ' + cost;
      overlay.appendChild(c);
    }
    if (cooldown !== ''){
      const cd = document.createElement('span');
      cd.className = 'overlay-badge overlay-badge--muted';
      cd.textContent = 'CD ' + (cooldown ?? '—');
      overlay.appendChild(cd);
    }
    art.appendChild(overlay);
  }

  content.appendChild(titlebar);
  content.appendChild(art);
  content.appendChild(typeline);
  content.appendChild(textbox);
  content.appendChild(footer);

  el.appendChild(bg);
  el.appendChild(vignette);
  el.appendChild(content);
  return el;
}

function makeBadge(text, extra=''){
  const b = document.createElement('span');
  b.className = 'badge ' + extra;
  b.textContent = text;
  return b;
}
