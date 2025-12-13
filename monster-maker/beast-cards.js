const $ = (sel, ctx = document) => ctx.querySelector(sel);
const cardsEl = $('#cards');

const fillFromFile = $('#jsonFile');
const loadSampleBtn = $('#loadSample');
const printBtn = $('#printBtn');

if (fillFromFile) {
  fillFromFile.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      renderData(data);
    } catch (err) {
      alert('Failed to read JSON: ' + err.message);
    }
  });
}

if (loadSampleBtn) {
  loadSampleBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('bestiary.json');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      renderData(data);
    } catch (err) {
      alert('Failed to load bestiary.json: ' + err.message);
    }
  });
}

if (printBtn) {
  printBtn.addEventListener('click', () => window.print());
}

function renderData(data) {
  const enemies = Array.isArray(data)
    ? data
    : Array.isArray(data.enemies)
    ? data.enemies
    : [];
  if (!enemies.length) {
    cardsEl.innerHTML = '<p style="color:#666">No enemies found. Expected `{ enemies: [...] }`.</p>';
    return;
  }
  cardsEl.innerHTML = '';
  enemies.forEach((enemy, idx) => cardsEl.appendChild(renderCard(enemy, idx)));
}

function renderCard(enemy, idx) {
  const {
    name = 'Unknown',
    tier,
    role,
    rarity = 'common',
    tags = [],
    stat_block = {},
    moves = [],
  } = enemy || {};

  const hp = stat_block.hp?.max ?? stat_block.hp ?? '?';
  const idf = stat_block.defense?.idf ?? 0;
  const dv = stat_block.defense?.dv_base ?? 0;
  const dmgBase = stat_block.damage_profile?.baseline;
  const dmgSpike = stat_block.damage_profile?.spike;

  const card = document.createElement('article');
  card.className = 'card';
  card.setAttribute('aria-label', name);

  const top = document.createElement('div');
  top.className = 'card__top';

  const title = document.createElement('div');
  title.className = 'title';
  title.textContent = name;

  const rarityEl = document.createElement('span');
  rarityEl.className = 'rarity';
  rarityEl.textContent = rarity;

  top.appendChild(title);
  top.appendChild(rarityEl);

  const meta = document.createElement('div');
  meta.className = 'meta';
  const metaParts = [];
  if (tier !== undefined) metaParts.push(`Tier ${tier}`);
  if (role) metaParts.push(role);
  meta.textContent = metaParts.join(' • ');

  const tagWrap = document.createElement('div');
  tagWrap.className = 'tags';
  tags.forEach((t) => {
    const span = document.createElement('span');
    span.className = 'tag';
    span.textContent = t;
    tagWrap.appendChild(span);
  });

  const statline = document.createElement('div');
  statline.className = 'statline';
  statline.innerHTML = `
    <div><strong>HP:</strong> ${hp}</div>
    <div><strong>Defense:</strong> DV ${dv} | IDF ${idf}</div>
    <div><strong>Damage:</strong> ${fmtDamage(dmgBase)} / Spike ${fmtDamage(dmgSpike)}</div>
  `;

  const movesWrap = document.createElement('div');
  movesWrap.className = 'section';
  const movesList = document.createElement('div');
  movesList.className = 'moves';
  movesWrap.innerHTML = '<strong>Moves</strong>';
  moves.forEach((m) => {
    const mv = document.createElement('div');
    mv.className = 'move';
    const nameEl = document.createElement('div');
    nameEl.className = 'name';
    nameEl.textContent = m.name || 'Move';
    const textEl = document.createElement('div');
    textEl.className = 'text';
    textEl.textContent =
      m.card_text ||
      m.on_hit?.damage ||
      m.on_miss?.notes ||
      m.type ||
      '';
    mv.appendChild(nameEl);
    mv.appendChild(textEl);
    movesList.appendChild(mv);
  });
  if (!moves.length) {
    const mv = document.createElement('div');
    mv.className = 'move';
    mv.textContent = 'No moves listed.';
    movesList.appendChild(mv);
  }
  movesWrap.appendChild(movesList);

  card.appendChild(top);
  card.appendChild(meta);
  if (tags.length) card.appendChild(tagWrap);
  card.appendChild(statline);
  card.appendChild(movesWrap);

  return card;
}

function fmtDamage(dmg) {
  if (!dmg) return '—';
  const dice = dmg.dice || '';
  const flat = dmg.flat || 0;
  const pieces = [];
  if (dice) pieces.push(dice);
  if (flat) pieces.push((flat >= 0 ? '+' : '') + flat);
  return pieces.join(' ') || '—';
}
