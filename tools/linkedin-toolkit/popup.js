// =====================================================================
// ANTEK LINKEDIN TOOLKIT — popup.js
// Lead scraper + AI recs + prospects + quoted keywords
// =====================================================================

// ——— ICP PRESET DATA ———
const PRESETS = {
  clients: [
    {
      group: 'Legal',
      items: [
        { name: 'Personal Injury Solicitors', kw: '"personal injury" solicitor', postKw: '"personal injury"' },
        { name: 'Employment Lawyers', kw: '"employment law" solicitor', postKw: '"employment law"' },
        { name: 'Family Law Solicitors', kw: '"family law" solicitor', postKw: '"family law"' },
        { name: 'Immigration Lawyers', kw: '"immigration" lawyer', postKw: '"immigration lawyer"' },
        { name: 'Criminal Defence Solicitors', kw: '"criminal defence" solicitor', postKw: '"criminal defence"' },
        { name: 'Conveyancing Solicitors', kw: '"conveyancing" solicitor', postKw: '"conveyancing"' },
        { name: 'Medical Negligence Lawyers', kw: '"clinical negligence" solicitor', postKw: '"clinical negligence"' },
        { name: 'Wills & Probate Solicitors', kw: '"wills" "probate" solicitor', postKw: '"wills and probate"' },
      ]
    },
    {
      group: 'Financial & Professional',
      items: [
        { name: 'IFAs / Financial Advisers', kw: '"independent financial adviser"', postKw: '"financial adviser"' },
        { name: 'Mortgage Brokers', kw: '"mortgage broker"', postKw: '"mortgage broker"' },
        { name: 'Accountants (Solo/Small)', kw: '"chartered accountant"', postKw: '"chartered accountant"' },
        { name: 'Insurance Brokers', kw: '"insurance broker"', postKw: '"insurance broker"' },
        { name: 'Tax Advisers', kw: '"tax adviser" OR "tax advisor"', postKw: '"tax advice"' },
      ]
    },
    {
      group: 'Health & Wellness',
      items: [
        { name: 'Private Dentists', kw: '"dental practice" owner OR principal', postKw: '"dental practice"' },
        { name: 'Vet Practice Owners', kw: '"veterinary practice" owner OR director', postKw: '"veterinary practice"' },
        { name: 'Physiotherapy Clinics', kw: '"physiotherapy" clinic owner', postKw: '"physiotherapy"' },
        { name: 'Chiropractors', kw: '"chiropractor" owner OR director', postKw: '"chiropractic"' },
        { name: 'Opticians (Independent)', kw: '"optician" OR "optometrist" practice', postKw: '"optometry"' },
      ]
    },
    {
      group: 'Property & Home',
      items: [
        { name: 'Estate Agents (Independent)', kw: '"estate agent" director OR owner', postKw: '"estate agent"' },
        { name: 'Letting Agents', kw: '"letting agent" director OR owner', postKw: '"letting agent"' },
        { name: 'Property Management', kw: '"property management" director', postKw: '"property management"' },
        { name: 'Surveyors', kw: '"chartered surveyor"', postKw: '"surveyor"' },
      ]
    }
  ],
  partners: [
    {
      group: 'Web & Digital',
      items: [
        { name: 'Freelance Web Designers', kw: '"web designer" freelance', postKw: '"web design"' },
        { name: 'WordPress Developers', kw: '"wordpress" developer freelance', postKw: '"wordpress"' },
        { name: 'Small Web Agencies', kw: '"web design agency" director OR founder', postKw: '"web design agency"' },
        { name: 'Shopify / E-com Devs', kw: '"shopify" developer OR consultant', postKw: '"shopify"' },
      ]
    },
    {
      group: 'Marketing & Content',
      items: [
        { name: 'SEO Consultants', kw: '"SEO consultant" OR "SEO freelancer"', postKw: '"SEO"' },
        { name: 'Social Media Managers', kw: '"social media manager" freelance', postKw: '"social media management"' },
        { name: 'Marketing Consultants', kw: '"marketing consultant" freelance', postKw: '"marketing consultant"' },
        { name: 'Copywriters (Freelance)', kw: '"copywriter" freelance', postKw: '"copywriting"' },
        { name: 'PPC / Google Ads', kw: '"google ads" OR "PPC" freelance consultant', postKw: '"google ads"' },
      ]
    },
    {
      group: 'Business Services',
      items: [
        { name: 'Business Coaches', kw: '"business coach" OR "business coaching"', postKw: '"business coaching"' },
        { name: 'VA Agencies', kw: '"virtual assistant" agency director', postKw: '"virtual assistant"' },
        { name: 'IT Support Companies', kw: '"IT support" OR "managed IT" director', postKw: '"managed IT"' },
        { name: 'CRM Consultants', kw: '"CRM consultant" OR "CRM specialist"', postKw: '"CRM"' },
      ]
    }
  ]
};


// ——— URL BUILDERS (quoted keywords) ———

function quoteIfNeeded(str) {
  // If user already added quotes, leave it. Otherwise wrap in quotes.
  str = str.trim();
  if (!str) return '';
  if (str.startsWith('"') || str.includes('" ') || str.includes(' "')) return str;
  return `"${str}"`;
}

function buildPeopleUrl(keyword, geoUrn, network) {
  const parts = [];
  if (keyword) parts.push(`keywords=${encodeURIComponent(keyword)}`);
  if (geoUrn) parts.push(`geoUrn=%5B%22${geoUrn}%22%5D`);
  if (network) parts.push(`network=%5B%22${network}%22%5D`);
  parts.push('origin=FACETED_SEARCH');
  return `https://www.linkedin.com/search/results/people/?${parts.join('&')}`;
}

function buildPostUrl(keyword, datePosted) {
  const parts = [];
  if (keyword) parts.push(`keywords=${encodeURIComponent(keyword)}`);
  if (datePosted) parts.push(`datePosted=%22${datePosted}%22`);
  parts.push('origin=FACETED_SEARCH');
  parts.push('sortBy=%22date_posted%22');
  return `https://www.linkedin.com/search/results/content/?${parts.join('&')}`;
}


// ——— STORAGE ———

async function getStore(key, fallback) {
  return new Promise(r => chrome.storage.local.get({ [key]: fallback }, d => r(d[key])));
}
async function setStore(key, val) {
  return new Promise(r => chrome.storage.local.set({ [key]: val }, r));
}
async function getSaved() { return getStore('savedUrls', []); }
async function setSaved(v) { return setStore('savedUrls', v); }

async function addSaved(items) {
  const existing = await getSaved();
  const urls = new Set(existing.map(u => u.url));
  const fresh = items.filter(i => !urls.has(i.url));
  await setSaved([...existing, ...fresh]);
  return fresh.length;
}


// ——— OPENROUTER AI ———

async function callAI(prompt) {
  const apiKey = await getStore('openRouterKey', '');
  const model = await getStore('aiModel', 'anthropic/claude-sonnet-4');
  if (!apiKey) throw new Error('No API key. Set it in Settings.');

  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'HTTP-Referer': 'chrome-extension://antek-lead-scraper',
      'X-Title': 'Antek Lead Scraper'
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      messages: [
        {
          role: 'system',
          content: `You are a LinkedIn lead sourcing expert. The user will describe who they want to find on LinkedIn. 

Your job is to suggest 6-8 exact-match search terms they should use on LinkedIn.

For each suggestion provide:
- term: The exact search string to use (with quotes for exact match phrases)
- type: Either "people" (for people search) or "post" (for post search to find engagers)
- reason: One-line explanation of why this term works (max 10 words)

Return ONLY valid JSON array, no markdown, no backticks. Example:
[{"term":"\"personal injury\" solicitor","type":"people","reason":"Exact job match for PI lawyers"},{"term":"\"personal injury claims\"","type":"post","reason":"Post engagers are active and interested"}]

Mix people searches and post searches. Use UK English spellings where relevant. Include some lateral/creative terms the user might not think of.`
        },
        { role: 'user', content: prompt }
      ]
    })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error?.message || `API error ${res.status}`);
  }

  const data = await res.json();
  const text = data.choices?.[0]?.message?.content || '';
  // Parse JSON, stripping any markdown fences
  const clean = text.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
  return JSON.parse(clean);
}


// ——— HELPERS ———

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2200);
}

function esc(s) {
  return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;');
}

function detectPageType(url) {
  if (!url) return { type: 'unknown', label: '—' };
  if (url.includes('/posts/') || url.includes('/feed/update/')) return { type: 'post', label: 'POST' };
  if (url.includes('/search/results/people')) return { type: 'search', label: 'SEARCH' };
  if (url.includes('/search/results/content')) return { type: 'search', label: 'POSTS' };
  if (url.includes('/sales/search') || url.includes('/sales/lists')) return { type: 'search', label: 'SALESNAV' };
  if (url.includes('/in/')) return { type: 'profile', label: 'PROFILE' };
  if (url.includes('linkedin.com')) return { type: 'other', label: 'LINKEDIN' };
  return { type: 'unknown', label: '—' };
}


// ——— RENDER PRESETS ———

function renderPresets(icp) {
  const container = document.getElementById(`presets-${icp}`);
  container.innerHTML = '';
  const loc = document.getElementById('qLocation').value;
  const deg = document.getElementById('qDegree').value;

  PRESETS[icp].forEach(g => {
    const div = document.createElement('div');
    div.className = 'preset-group';
    div.innerHTML = `<div class="group-label">${g.group}</div>`;
    g.items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'preset-row';
      row.innerHTML = `
        <div>
          <div class="preset-name">${item.name}</div>
          <div class="preset-terms">${esc(item.kw)}</div>
        </div>
        <div class="preset-btns">
          <button class="p-btn" data-kw="${esc(item.kw)}">People</button>
          <button class="p-btn post" data-kw="${esc(item.postKw)}">Posts</button>
        </div>
      `;
      // People search
      row.querySelector('.p-btn:not(.post)').addEventListener('click', () => {
        chrome.tabs.create({ url: buildPeopleUrl(item.kw, loc, deg) });
      });
      // Post search
      row.querySelector('.p-btn.post').addEventListener('click', () => {
        chrome.tabs.create({ url: buildPostUrl(item.postKw, 'past-week') });
      });
      div.appendChild(row);
    });
    container.appendChild(div);
  });
}


// ——— RENDER AI RESULTS ———

function renderAiResults(suggestions) {
  const container = document.getElementById('aiResults');
  const loc = document.getElementById('qLocation').value;
  const deg = document.getElementById('qDegree').value;
  container.innerHTML = '';

  suggestions.forEach(s => {
    const card = document.createElement('div');
    card.className = 'ai-card';
    card.innerHTML = `
      <div class="ai-card-left">
        <div class="ai-card-term">${esc(s.term)}</div>
        <div class="ai-card-reason">${s.type === 'post' ? '📝 Post' : '👤 People'} · ${esc(s.reason || '')}</div>
      </div>
      <div class="ai-card-btns">
        <button class="p-btn ai-use">Use</button>
      </div>
    `;
    card.querySelector('.ai-use').addEventListener('click', () => {
      if (s.type === 'post') {
        chrome.tabs.create({ url: buildPostUrl(s.term, 'past-week') });
      } else {
        chrome.tabs.create({ url: buildPeopleUrl(s.term, loc, deg) });
      }
    });
    container.appendChild(card);
  });

  container.classList.remove('hidden');
}


// ——— RENDER SAVED LIST ———

async function renderSaved(filter = 'all') {
  const list = document.getElementById('savedList');
  const items = await getSaved();
  const filtered = filter === 'all' ? items : items.filter(i => i.category === filter);

  document.getElementById('savedCount').textContent = items.length;

  if (filtered.length === 0) {
    list.innerHTML = '<p class="empty">Nothing saved yet.</p>';
    return;
  }

  list.innerHTML = '';
  filtered.forEach(item => {
    const realIdx = items.indexOf(item);
    const el = document.createElement('div');
    el.className = 'saved-item';
    el.innerHTML = `
      <span class="si-type ${item.category}">${(item.category || 'other').toUpperCase()}</span>
      <div class="si-body">
        <div class="si-note">${item.note || 'No note'}</div>
        <div class="si-url" title="Click to copy">${item.url}</div>
        <div class="si-icp">${item.icp || '—'}</div>
      </div>
      <div class="si-actions">
        <button class="si-copy" title="Copy URL">&#128203;</button>
        <button class="si-open" title="Open in new tab">&#8599;</button>
        <button class="si-del" data-idx="${realIdx}" title="Remove">&times;</button>
      </div>
    `;
    // Click URL text → copy
    el.querySelector('.si-url').addEventListener('click', async () => {
      await navigator.clipboard.writeText(item.url);
      toast('URL copied');
    });
    // Copy button
    el.querySelector('.si-copy').addEventListener('click', async () => {
      await navigator.clipboard.writeText(item.url);
      toast('URL copied');
    });
    // Open button
    el.querySelector('.si-open').addEventListener('click', () => {
      chrome.tabs.create({ url: item.url });
    });
    el.querySelector('.si-del').addEventListener('click', async (e) => {
      const all = await getSaved();
      all.splice(parseInt(e.target.dataset.idx), 1);
      await setSaved(all);
      renderSaved(filter);
      toast('Removed');
    });
    list.appendChild(el);
  });
}


// ——— INIT ———

document.addEventListener('DOMContentLoaded', async () => {

  // --- Settings ---
  const settingsOverlay = document.getElementById('settingsOverlay');
  document.getElementById('gearBtn').addEventListener('click', async () => {
    const key = await getStore('openRouterKey', '');
    const model = await getStore('aiModel', 'anthropic/claude-sonnet-4');
    document.getElementById('apiKeyInput').value = key;
    document.getElementById('aiModel').value = model;
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (key) { dot.classList.add('ok'); txt.textContent = 'Key set'; }
    else { dot.classList.remove('ok'); txt.textContent = 'No key set'; }
    settingsOverlay.classList.remove('hidden');
  });

  document.getElementById('closeSettings').addEventListener('click', () => {
    settingsOverlay.classList.add('hidden');
  });

  document.getElementById('saveSettingsBtn').addEventListener('click', async () => {
    const key = document.getElementById('apiKeyInput').value.trim();
    const model = document.getElementById('aiModel').value;
    await setStore('openRouterKey', key);
    await setStore('aiModel', model);
    document.getElementById('statusDot').classList.toggle('ok', !!key);
    document.getElementById('statusText').textContent = key ? 'Key saved' : 'No key set';
    toast('Settings saved');
  });

  // --- Tabs ---
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
      if (tab.dataset.tab === 'saved') renderSaved();
      if (tab.dataset.tab === 'prospects') renderProspects();
    });
  });

  // --- ICP toggle ---
  document.querySelectorAll('.icp-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.icp-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.presets-section').forEach(s => s.classList.add('hidden'));
      document.getElementById(`presets-${btn.dataset.icp}`).classList.remove('hidden');
    });
  });

  // --- Render presets ---
  renderPresets('clients');
  renderPresets('partners');
  document.getElementById('qLocation').addEventListener('change', () => { renderPresets('clients'); renderPresets('partners'); });
  document.getElementById('qDegree').addEventListener('change', () => { renderPresets('clients'); renderPresets('partners'); });

  // --- AI Recommendations ---
  document.getElementById('getAiRecs').addEventListener('click', async () => {
    const ctx = document.getElementById('aiContext').value.trim();
    if (!ctx) { toast('Describe who you want to find'); return; }

    const activeIcp = document.querySelector('.icp-btn.active')?.dataset.icp || 'clients';
    const loading = document.getElementById('aiLoading');
    const results = document.getElementById('aiResults');
    const hint = document.getElementById('aiHint');

    loading.classList.remove('hidden');
    results.classList.add('hidden');
    hint.style.display = 'none';

    try {
      const prompt = `I want to find LinkedIn leads matching this description: ${ctx}

I'm looking for ${activeIcp === 'clients' ? 'direct clients (solo professionals, practice owners, small firms)' : 'channel partners (freelancers, small agencies who need a techy to build voice AI agents and do GEO/SEO for their clients)'}.

Location focus: UK unless specified otherwise.

Suggest 6-8 LinkedIn search terms. Mix "people" searches (for finding profiles) and "post" searches (for finding active engagers). Use "quoted phrases" for exact match. Include some lateral/creative terms I might not think of.`;

      const suggestions = await callAI(prompt);
      renderAiResults(suggestions);
    } catch (err) {
      results.innerHTML = `<p class="hint" style="color:var(--red)">${esc(err.message)}</p>`;
      results.classList.remove('hidden');
    } finally {
      loading.classList.add('hidden');
    }
  });

  // --- Custom search (with auto-quoting) ---
  document.getElementById('runSearchBtn').addEventListener('click', () => {
    const title = document.getElementById('qTitle').value.trim();
    const kw = document.getElementById('qKeyword').value.trim();
    const loc = document.getElementById('qLocation').value;
    const deg = document.getElementById('qDegree').value;
    if (!title && !kw) { toast('Enter a title or keyword'); return; }
    // Build combined keyword with quoting
    const parts = [];
    if (kw) parts.push(quoteIfNeeded(kw));
    if (title) parts.push(title); // titles often use OR so don't auto-quote
    const url = buildPeopleUrl(parts.join(' '), loc, deg);
    chrome.tabs.create({ url });
  });

  document.getElementById('runPostBtn').addEventListener('click', () => {
    const title = document.getElementById('qTitle').value.trim();
    const kw = document.getElementById('qKeyword').value.trim();
    const term = quoteIfNeeded([title, kw].filter(Boolean).join(' '));
    if (!term) { toast('Enter a title or keyword'); return; }
    chrome.tabs.create({ url: buildPostUrl(term, 'past-week') });
  });

  // --- Post finder ---
  document.getElementById('findPostsBtn').addEventListener('click', () => {
    let kw = document.getElementById('postKeyword').value.trim();
    const date = document.getElementById('postDate').value;
    if (!kw) { toast('Enter a keyword'); return; }
    kw = quoteIfNeeded(kw);
    chrome.tabs.create({ url: buildPostUrl(kw, date) });
  });

  // --- Page detection ---
  document.getElementById('detectPageBtn').addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab?.url) { toast('Cannot read page'); return; }
      const url = tab.url;
      const info = detectPageType(url);

      document.getElementById('detectDot').classList.toggle('on', url.includes('linkedin.com'));
      document.getElementById('detectText').textContent = url.includes('linkedin.com') ? 'LinkedIn' : 'Not LinkedIn';

      document.getElementById('capType').textContent = info.label;
      document.getElementById('capType').className = `cap-label ${info.type}`;
      document.getElementById('capUrl').textContent = url;
      document.getElementById('capUrl').title = url;

      const cat = document.getElementById('capCategory');
      if (info.type === 'post') cat.value = 'post';
      else if (info.type === 'search') cat.value = 'search';
      else if (info.type === 'profile') cat.value = 'profile';

      document.getElementById('captureControls').classList.remove('hidden');
      document.getElementById('savePageBtn').dataset.url = url;
    });
  });

  // --- Save current page ---
  document.getElementById('savePageBtn').addEventListener('click', async () => {
    const url = document.getElementById('savePageBtn').dataset.url;
    if (!url) { toast('Detect a page first'); return; }
    const added = await addSaved([{
      url,
      category: document.getElementById('capCategory').value,
      icp: document.getElementById('capIcp').value,
      note: document.getElementById('capNote').value.trim(),
      ts: Date.now()
    }]);
    toast(added ? 'Saved' : 'Already saved');
    document.getElementById('savedCount').textContent = (await getSaved()).length;
  });

  // --- Paste URLs ---
  document.getElementById('savePasteBtn').addEventListener('click', async () => {
    const raw = document.getElementById('pasteUrls').value.trim();
    if (!raw) { toast('Paste some URLs'); return; }
    const urls = raw.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
    if (!urls.length) { toast('No valid URLs'); return; }
    const icp = document.getElementById('pasteIcp').value;
    const note = document.getElementById('pasteNote').value.trim();
    const items = urls.map(url => ({
      url,
      category: detectPageType(url).type === 'post' ? 'post' : 'search',
      icp, note, ts: Date.now()
    }));
    const added = await addSaved(items);
    toast(`Saved ${added} URL${added !== 1 ? 's' : ''}`);
    document.getElementById('pasteUrls').value = '';
    document.getElementById('savedCount').textContent = (await getSaved()).length;
  });

  // --- Saved filters ---
  document.querySelectorAll('.filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderSaved(btn.dataset.f);
    });
  });

  // --- Export ---
  document.getElementById('copyPostsBtn').addEventListener('click', async () => {
    const items = await getSaved();
    const posts = items.filter(i => i.category === 'post').map(i => i.url);
    if (!posts.length) { toast('No post URLs saved'); return; }
    await navigator.clipboard.writeText(posts.join('\n'));
    toast(`Copied ${posts.length} post URL${posts.length !== 1 ? 's' : ''}`);
  });

  document.getElementById('copyAllBtn').addEventListener('click', async () => {
    const items = await getSaved();
    if (!items.length) { toast('Nothing saved'); return; }
    const text = items.map(i => `[${i.category}] ${i.url}${i.note ? ' — ' + i.note : ''}`).join('\n');
    await navigator.clipboard.writeText(text);
    toast(`Copied ${items.length} URL${items.length !== 1 ? 's' : ''}`);
  });

  document.getElementById('clearBtn').addEventListener('click', async () => {
    if (!confirm('Clear all saved URLs?')) return;
    await setSaved([]);
    renderSaved();
    toast('Cleared');
  });

  // --- Initial state ---
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.url?.includes('linkedin.com')) {
      document.getElementById('detectDot').classList.add('on');
      document.getElementById('detectText').textContent = 'LinkedIn';
    }
  });

  document.getElementById('savedCount').textContent = (await getSaved()).length;


  // =====================================================================
  // PROSPECTS TAB — CSV import + one-click LinkedIn search
  // =====================================================================

  async function getProspects() { return getStore('prospects', []); }
  async function setProspects(v) { return setStore('prospects', v); }

  // Turn a domain like "wards.uk.com" or "thefamilylawpractice.co.uk" into a clean firm
  // string we can put into a LinkedIn search. Strips TLD chain and title-cases first label.
  function cleanFirmFromDomain(d) {
    if (!d) return '';
    let s = String(d).trim().toLowerCase();
    s = s.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    const label = s.split('.')[0] || s;
    if (!label) return '';
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2) return [];
    const headerLine = lines[0];
    const delim = headerLine.includes('\t') ? '\t' : ',';

    // Parse a single CSV line respecting quoted fields
    function parseLine(line) {
      const fields = [];
      let current = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"' && (i === 0 || line[i - 1] !== '\\')) {
          inQuotes = !inQuotes;
        } else if (ch === delim && !inQuotes) {
          fields.push(current.trim().replace(/^["']|["']$/g, ''));
          current = '';
        } else {
          current += ch;
        }
      }
      fields.push(current.trim().replace(/^["']|["']$/g, ''));
      return fields;
    }

    const headers = parseLine(headerLine).map(h => h.toLowerCase());

    return lines.slice(1).map((line, idx) => {
      if (!line.trim()) return null;
      const vals = parseLine(line);
      const row = {};
      headers.forEach((h, i) => { row[h] = vals[i] || ''; });

      const name = row.name || [row.first_name, row.last_name].filter(Boolean).join(' ') || '';
      const domain = row.domain || '';
      // Prefer real firm name. Fall back to cleaned domain (no TLD, title-cased) so
      // LinkedIn search never gets "wards.uk.com" as a query term.
      const explicitFirm = row.business_name || row.firm || row.company || row.company_name || row.organisation || '';
      const company = explicitFirm || cleanFirmFromDomain(domain);
      const title = row.title || row.job_title || row.role || '';
      const score = parseInt(row.score || row.icp_score || row.ppos_score || row.pitchability_score || '0') || 0;
      const email = row.email || '';
      const phone = row.phone || '';
      const linkedin_url = row.linkedin_url || row.linkedin || '';
      const firm_address = row.firm_address || row.address || '';
      const notes = row.notes || row.note || row.summary || '';

      // Audit / scan signals — present when CSV came from enriched_contacts.csv
      const geo_score = row.geo_score || '';
      const best_position = row.best_position || '';
      const top_gap_1 = row.top_gap_1 || row.top_gap || '';
      const top_gap_2 = row.top_gap_2 || '';
      const top_gap_3 = row.top_gap_3 || '';
      const has_llmstxt = (row.has_llmstxt || '').toLowerCase() === 'true';
      const has_schema = (row.has_schema || '').toLowerCase() === 'true';
      const keywords = row.keywords || '';
      const linkedin_dm = row.linkedin_dm || '';
      const email_subject = row.email_subject || '';
      const email_body = row.email_body || '';
      const voice_opener = row.voice_opener || '';

      return {
        id: idx, name, company, domain, title, score, email, phone,
        linkedin_url, firm_address, notes,
        geo_score, best_position, top_gap_1, top_gap_2, top_gap_3,
        has_llmstxt, has_schema, keywords,
        linkedin_dm, email_subject, email_body, voice_opener,
        found: false,
      };
    }).filter(p => p && p.name);
  }

  function renderProspects(filterText = '') {
    getProspects().then(prospects => {
      const list = document.getElementById('prospectList');
      const stats = document.getElementById('prospectStats');
      const q = filterText.toLowerCase();
      const filtered = q
        ? prospects.filter(p => p.name.toLowerCase().includes(q) || p.company.toLowerCase().includes(q))
        : prospects;

      const found = prospects.filter(p => p.found).length;
      stats.textContent = prospects.length
        ? `${prospects.length} prospects · ${found} found · ${prospects.length - found} remaining`
        : '';

      if (filtered.length === 0) {
        list.innerHTML = '<p class="empty">No prospects loaded. Import a CSV above.</p>';
        return;
      }

      list.innerHTML = '';
      filtered.forEach(p => {
        const card = document.createElement('div');
        card.className = `prospect-card${p.found ? ' found' : ''}`;
        const directLinkedIn = p.linkedin_url && /linkedin\.com\/in\//i.test(p.linkedin_url);
        const titleLine = p.title ? `<div class="pc-title">${esc(p.title)}</div>` : '';
        const addrLine = p.firm_address ? `<div class="pc-addr" title="${esc(p.firm_address)}">📍 ${esc(p.firm_address.substring(0, 60))}${p.firm_address.length > 60 ? '…' : ''}</div>` : '';

        // Audit summary line — only render when audit data present
        const scanBits = [];
        if (p.geo_score) scanBits.push(`GEO ${p.geo_score}`);
        if (p.best_position) scanBits.push(`#${p.best_position}`);
        if (p.top_gap_1) scanBits.push(esc(p.top_gap_1));
        if (p.has_llmstxt === false && p.geo_score) scanBits.push('no llms.txt');
        if (p.has_schema === false && p.geo_score) scanBits.push('no schema');
        const scanLine = scanBits.length
          ? `<div class="pc-scan" title="${esc([p.top_gap_1, p.top_gap_2, p.top_gap_3].filter(Boolean).join(' · '))}">⚡ ${scanBits.slice(0, 4).join(' · ')}</div>`
          : '';

        const hasDM = !!p.linkedin_dm;
        const hasEmail = !!(p.email_subject || p.email_body);

        card.innerHTML = `
          <div class="pc-info">
            <div class="pc-name">${esc(p.name)}</div>
            <div class="pc-company">${esc(p.company)}${p.notes ? ' · ' + esc(p.notes.substring(0, 40)) : ''}</div>
            ${titleLine}
            ${addrLine}
            ${scanLine}
          </div>
          ${p.score ? `<span class="pc-score${p.score >= 70 ? ' high' : ''}">${p.score}</span>` : ''}
          <div class="pc-btns">
            <button class="pc-btn find-btn" data-id="${p.id}" title="${directLinkedIn ? 'Open LinkedIn profile' : 'Search LinkedIn'}">${directLinkedIn ? 'Open' : 'Find'}</button>
            <button class="pc-btn google-btn" data-id="${p.id}" title="Google site:linkedin.com/in search">G</button>
            ${hasDM ? `<button class="pc-btn dm-btn" data-id="${p.id}" title="Copy LinkedIn DM to clipboard">DM</button>` : ''}
            ${hasEmail ? `<button class="pc-btn email-btn" data-id="${p.id}" title="Copy email subject + body to clipboard">@</button>` : ''}
            <button class="pc-btn ${p.found ? 'done' : ''}" data-id="${p.id}" data-action="toggle" title="${p.found ? 'Mark not found' : 'Mark as found'}">${p.found ? '✓' : '○'}</button>
          </div>
        `;

        // Primary: direct LinkedIn profile URL if known, else LinkedIn people search
        card.querySelector('.find-btn').addEventListener('click', () => {
          let url;
          if (directLinkedIn) {
            url = p.linkedin_url;
          } else {
            const q = `"${p.name}" ${p.company}`.trim();
            url = `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(q)}&origin=GLOBAL_SEARCH_HEADER`;
          }
          chrome.tabs.create({ url });
        });

        // Fallback: Google site:linkedin.com/in/ search (works when LinkedIn search hides matches)
        card.querySelector('.google-btn').addEventListener('click', () => {
          const q = `site:linkedin.com/in/ "${p.name}" "${p.company}"`;
          chrome.tabs.create({ url: `https://www.google.com/search?q=${encodeURIComponent(q)}` });
        });

        // Copy LinkedIn DM
        const dmBtn = card.querySelector('.dm-btn');
        if (dmBtn) {
          dmBtn.addEventListener('click', async () => {
            try {
              await navigator.clipboard.writeText(p.linkedin_dm);
              toast('DM copied — paste into LinkedIn');
            } catch {
              toast('Copy failed');
            }
          });
        }

        // Copy email (subject + body)
        const emailBtn = card.querySelector('.email-btn');
        if (emailBtn) {
          emailBtn.addEventListener('click', async () => {
            const text = `Subject: ${p.email_subject}\n\n${p.email_body}`;
            try {
              await navigator.clipboard.writeText(text);
              toast('Email copied');
            } catch {
              toast('Copy failed');
            }
          });
        }

        // Toggle found
        card.querySelector('[data-action="toggle"]').addEventListener('click', async () => {
          const all = await getProspects();
          const match = all.find(x => x.id === p.id);
          if (match) {
            match.found = !match.found;
            await setProspects(all);
            renderProspects(filterText);
          }
        });

        list.appendChild(card);
      });
    });
  }

  // CSV file import
  document.getElementById('csvFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    const prospects = parseCSV(text);
    if (prospects.length === 0) { toast('No valid rows found in CSV'); return; }
    await setProspects(prospects);
    renderProspects();
    toast(`Imported ${prospects.length} prospects`);
  });

  // Filter
  document.getElementById('prospectSearch').addEventListener('input', (e) => {
    renderProspects(e.target.value.trim());
  });

  // Clear
  document.getElementById('clearProspectsBtn').addEventListener('click', async () => {
    if (!confirm('Clear all prospects?')) return;
    await setProspects([]);
    renderProspects();
    toast('Prospects cleared');
  });

  // Bulk open — first 10 unfound prospects, prefer direct LinkedIn URLs, fall back to people search
  document.getElementById('bulkOpenBtn').addEventListener('click', async () => {
    const all = await getProspects();
    const queue = all.filter(p => !p.found).slice(0, 10);
    if (queue.length === 0) { toast('Nothing to open — all marked found, or none imported'); return; }
    queue.forEach(p => {
      let url;
      if (p.linkedin_url && /linkedin\.com\/in\//i.test(p.linkedin_url)) {
        url = p.linkedin_url;
      } else {
        const q = `"${p.name}" ${p.company}`.trim();
        url = `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(q)}&origin=GLOBAL_SEARCH_HEADER`;
      }
      chrome.tabs.create({ url, active: false });
    });
    toast(`Opened ${queue.length} tabs`);
  });


  // =====================================================================
  // GROUPS TAB — scraped group posts + engagement filter + CSV export
  // =====================================================================

  async function getGroupPosts() { return getStore('groupPosts', []); }
  async function setGroupPosts(v) { return setStore('groupPosts', v); }

  function formatGrpStat(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
  }

  async function renderGroups() {
    const posts = await getGroupPosts();
    const minComments = parseInt(document.getElementById('grpMinComments').value) || 0;
    const minLikes = parseInt(document.getElementById('grpMinLikes').value) || 0;

    document.getElementById('grpCount').textContent = posts.length;

    // Sort by engagement (comments + likes/10 as a soft secondary)
    const sorted = [...posts].sort((a, b) => {
      const aScore = (a.comment_count || 0) * 10 + (a.like_count || 0);
      const bScore = (b.comment_count || 0) * 10 + (b.like_count || 0);
      return bScore - aScore;
    });

    const matchingCount = sorted.filter(p =>
      (p.comment_count || 0) >= minComments && (p.like_count || 0) >= minLikes
    ).length;
    document.getElementById('grpFilteredCount').textContent =
      posts.length ? `${matchingCount} match filter` : '';

    const list = document.getElementById('grpList');
    if (sorted.length === 0) {
      list.innerHTML = '<p class="empty">No posts scraped yet. Open a group page and use the floating panel.</p>';
      return;
    }

    list.innerHTML = '';
    sorted.forEach(p => {
      const matches = (p.comment_count || 0) >= minComments && (p.like_count || 0) >= minLikes;
      const card = document.createElement('div');
      card.className = `grp-card${matches ? ' match' : ''}`;
      card.innerHTML = `
        <div class="grp-card-top">
          <div class="grp-author" title="${esc(p.author_name || '')}">${esc(p.author_name || 'Unknown')}</div>
          <div class="grp-date">${esc(p.post_date_text || '')}</div>
        </div>
        ${p.author_headline ? `<div class="grp-headline" title="${esc(p.author_headline)}">${esc(p.author_headline)}</div>` : ''}
        <div class="grp-meta">
          <span class="grp-stat"><strong>${formatGrpStat(p.like_count || 0)}</strong> likes</span>
          <span class="grp-stat"><strong>${formatGrpStat(p.comment_count || 0)}</strong> comments</span>
          ${p.exported ? '<span class="grp-exported">✓ exported</span>' : ''}
          <div class="grp-actions">
            <button class="pc-btn grp-open" data-url="${esc(p.post_url)}">Open</button>
            <button class="pc-btn grp-del" data-url="${esc(p.post_url)}">×</button>
          </div>
        </div>
      `;
      card.querySelector('.grp-open').addEventListener('click', () => {
        chrome.tabs.create({ url: p.post_url });
      });
      card.querySelector('.grp-del').addEventListener('click', async () => {
        const all = await getGroupPosts();
        await setGroupPosts(all.filter(x => x.post_url !== p.post_url));
        renderGroups();
      });
      list.appendChild(card);
    });
  }

  // CSV escape — RFC 4180
  function csvEscape(v) {
    if (v == null) return '';
    const s = String(v);
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  function downloadCSV(content, filename) {
    const blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function timestampForFilename() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
  }

  async function exportGroupPostsSendPilot() {
    const posts = await getGroupPosts();
    const minComments = parseInt(document.getElementById('grpMinComments').value) || 0;
    const minLikes = parseInt(document.getElementById('grpMinLikes').value) || 0;
    const filtered = posts.filter(p =>
      (p.comment_count || 0) >= minComments && (p.like_count || 0) >= minLikes
    );
    if (!filtered.length) { toast('No posts match the engagement filter'); return; }

    const lines = ['post_url'];
    filtered.forEach(p => lines.push(p.post_url));

    const groupId = filtered[0]?.group_id || 'group';
    downloadCSV(lines.join('\n'), `linkedin-group-${groupId}-sendpilot-${timestampForFilename()}.csv`);

    // Mark as exported
    const exportedUrls = new Set(filtered.map(p => p.post_url));
    const updated = posts.map(p =>
      exportedUrls.has(p.post_url) ? { ...p, exported: true, exported_at: new Date().toISOString() } : p
    );
    await setGroupPosts(updated);
    renderGroups();
    toast(`Exported ${filtered.length} URL${filtered.length !== 1 ? 's' : ''}`);
  }

  async function exportGroupPostsFull() {
    const posts = await getGroupPosts();
    const minComments = parseInt(document.getElementById('grpMinComments').value) || 0;
    const minLikes = parseInt(document.getElementById('grpMinLikes').value) || 0;
    const filtered = posts.filter(p =>
      (p.comment_count || 0) >= minComments && (p.like_count || 0) >= minLikes
    );
    if (!filtered.length) { toast('No posts match the engagement filter'); return; }

    const headers = ['post_url','author_name','author_headline','author_profile_url','like_count','comment_count','post_date_text','group_id','scraped_at'];
    const lines = [headers.join(',')];
    filtered.forEach(p => {
      lines.push(headers.map(h => csvEscape(p[h])).join(','));
    });

    const groupId = filtered[0]?.group_id || 'group';
    downloadCSV(lines.join('\n'), `linkedin-group-${groupId}-full-${timestampForFilename()}.csv`);
    toast(`Exported ${filtered.length} row${filtered.length !== 1 ? 's' : ''}`);
  }

  // Status indicator — checks the current tab for group page + scraped count
  async function updateGroupStatus() {
    const dot = document.getElementById('grpDot');
    const txt = document.getElementById('grpStatusText');
    const posts = await getGroupPosts();

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const url = tabs[0]?.url || '';
      const onGroupPage = /linkedin\.com\/groups\/\d+/.test(url);
      if (onGroupPage) {
        dot.classList.add('ok');
        const m = url.match(/\/groups\/(\d+)/);
        txt.textContent = `On group ${m ? m[1] : ''}. Use floating panel to scrape. ${posts.length} posts in storage.`;
      } else {
        dot.classList.remove('ok');
        txt.textContent = posts.length
          ? `${posts.length} posts in storage. Open a group page to scrape more.`
          : 'Open a LinkedIn group page to start.';
      }
    });
  }

  // Wire Groups tab
  document.getElementById('grpOpenBtn').addEventListener('click', () => {
    const url = document.getElementById('grpOpenUrl').value.trim();
    if (!url) { toast('Paste a group URL'); return; }
    if (!/linkedin\.com\/groups\/\d+/.test(url)) { toast('Not a valid group URL'); return; }
    chrome.tabs.create({ url });
  });

  document.getElementById('grpMinComments').addEventListener('input', renderGroups);
  document.getElementById('grpMinLikes').addEventListener('input', renderGroups);

  document.getElementById('grpExportSendPilot').addEventListener('click', exportGroupPostsSendPilot);
  document.getElementById('grpExportFull').addEventListener('click', exportGroupPostsFull);

  document.getElementById('grpClear').addEventListener('click', async () => {
    if (!confirm('Clear all scraped group posts?')) return;
    await setGroupPosts([]);
    renderGroups();
    toast('Scraped posts cleared');
  });

  // Auto-refresh Groups tab when activated (storage may have updated via content script)
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.dataset.tab === 'groups') {
        renderGroups();
        updateGroupStatus();
      }
    });
  });

  // Listen for storage changes so the popup updates live while open
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.groupPosts) {
      const groupsPanelVisible = document.getElementById('panel-groups')?.classList.contains('active');
      if (groupsPanelVisible) renderGroups();
    }
  });

  // Initial group status update
  updateGroupStatus();

});
