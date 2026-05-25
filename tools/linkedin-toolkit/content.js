// =====================================================================
// ANTEK LINKEDIN TOOLKIT — Content Script
// Page detection + post URL auto-scraper
// =====================================================================
(function () {
  'use strict';

  // ——— Page detection for popup ———
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'getPageInfo') {
      sendResponse({ url: window.location.href, title: document.title });
    }
    return true;
  });


  // ——— Post URL Scraper ———
  // Injects a floating button on LinkedIn post search pages
  // that scrapes all visible post URLs and saves them to extension storage.

  const SCRAPER_ID = 'antek-post-scraper';
  let isOnPostSearch = false;
  let isScraping = false;

  function checkIfPostSearchPage() {
    return window.location.pathname.includes('/search/results/content');
  }

  // Extract post URNs/URLs from the current DOM
  function extractPostUrls() {
    const urls = new Set();

    // Validate that a URL is an individual post, not a company/profile listing page
    function isIndividualPost(href) {
      // Individual post: /posts/username_slug-activityID-hash
      // e.g. /posts/priya-ghataurhae-560859180_vaisakhi-harvestfestival-7449892976610131968-PLHb
      if (href.includes('/posts/')) {
        // Reject company listing pages like /company/xxx/posts/
        if (href.includes('/company/')) return false;
        // Must have actual content after /posts/ (not just trailing slash)
        const afterPosts = href.split('/posts/')[1];
        if (!afterPosts || afterPosts.replace(/\/$/, '').length < 5) return false;
        // Individual posts contain digits (activity IDs)
        if (!/\d{5,}/.test(afterPosts)) return false;
        return true;
      }
      // /feed/update/ URLs are always individual posts
      if (href.includes('/feed/update/')) {
        const afterUpdate = href.split('/feed/update/')[1];
        return afterUpdate && afterUpdate.length > 5;
      }
      return false;
    }

    // Strategy 1: data-urn attributes with activity/ugcPost/share URNs
    document.querySelectorAll('[data-urn]').forEach(el => {
      const urn = el.getAttribute('data-urn');
      if (urn && (urn.includes('urn:li:activity:') || urn.includes('urn:li:ugcPost:') || urn.includes('urn:li:share:'))) {
        urls.add(`https://www.linkedin.com/feed/update/${urn}`);
      }
    });

    // Strategy 2: data-activity-urn attributes
    document.querySelectorAll('[data-activity-urn]').forEach(el => {
      const urn = el.getAttribute('data-activity-urn');
      if (urn) urls.add(`https://www.linkedin.com/feed/update/${urn}`);
    });

    // Strategy 3: anchor links to individual posts (validated)
    document.querySelectorAll('a[href*="/feed/update/"], a[href*="/posts/"]').forEach(a => {
      const href = a.href.split('?')[0];
      if (isIndividualPost(href)) urls.add(href);
    });

    // Strategy 4: timestamp/permalink links inside post containers
    document.querySelectorAll(
      '.feed-shared-update-v2, .update-components-actor, ' +
      '[data-urn*="activity"], [data-urn*="ugcPost"], [data-urn*="share"]'
    ).forEach(el => {
      const timeLink = el.querySelector('a[href*="/feed/update/"]') ||
                        el.querySelector('a[href*="/posts/"]') ||
                        el.querySelector('a.update-components-actor__sub-description-link');
      if (timeLink?.href) {
        const href = timeLink.href.split('?')[0];
        if (isIndividualPost(href)) urls.add(href);
      }
    });

    // Strategy 5: look for activity IDs in any data attributes and construct URLs
    document.querySelectorAll('[data-id]').forEach(el => {
      const id = el.getAttribute('data-id');
      if (id && /^urn:li:(activity|ugcPost|share):/.test(id)) {
        urls.add(`https://www.linkedin.com/feed/update/${id}`);
      }
    });

    console.log(`[Antek Scraper] Extracted ${urls.size} individual post URLs`);
    return [...urls];
  }

  // Auto-scroll to load more posts
  function scrollDown() {
    return new Promise(resolve => {
      const currentHeight = document.body.scrollHeight;
      window.scrollTo(0, document.body.scrollHeight);
      // Wait for LinkedIn to load more content
      setTimeout(() => {
        const newHeight = document.body.scrollHeight;
        resolve(newHeight > currentHeight);
      }, 1500);
    });
  }

  // Main scrape function: scroll + extract + repeat
  async function scrapeAllPosts(statusEl) {
    if (isScraping) return;
    isScraping = true;

    const allUrls = new Set();
    let scrollAttempts = 0;
    const maxScrolls = 15; // cap at ~15 page-loads

    // Get initial posts
    extractPostUrls().forEach(u => allUrls.add(u));
    updateStatus(statusEl, `Found ${allUrls.size} posts... scrolling`);

    while (scrollAttempts < maxScrolls) {
      const didGrow = await scrollDown();
      const newUrls = extractPostUrls();
      const prevSize = allUrls.size;
      newUrls.forEach(u => allUrls.add(u));

      updateStatus(statusEl, `Found ${allUrls.size} posts... scrolling (${scrollAttempts + 1}/${maxScrolls})`);

      // Stop if no new posts loaded after scroll
      if (!didGrow && allUrls.size === prevSize) {
        scrollAttempts++;
        if (scrollAttempts >= 3) break; // 3 stale scrolls = done
      } else {
        scrollAttempts = 0; // reset on new content
      }

      scrollAttempts++;
    }

    // Scroll back to top
    window.scrollTo(0, 0);

    // Save to extension storage
    const urlArray = [...allUrls];
    const saved = await saveScrapedUrls(urlArray);

    updateStatus(statusEl, `Done. ${urlArray.length} posts scraped, ${saved} new saved.`);
    isScraping = false;

    return urlArray;
  }

  // Save scraped URLs to chrome.storage (same format as manual saves)
  async function saveScrapedUrls(urls) {
    return new Promise(resolve => {
      chrome.storage.local.get({ savedUrls: [] }, data => {
        const existing = data.savedUrls || [];
        const existingSet = new Set(existing.map(u => u.url));
        const searchTerms = new URLSearchParams(window.location.search).get('keywords') || '';
        const newItems = urls
          .filter(url => !existingSet.has(url))
          .map(url => ({
            url,
            category: 'post',
            icp: 'mixed',
            note: searchTerms ? `Auto-scraped: ${searchTerms}` : 'Auto-scraped',
            ts: Date.now()
          }));

        chrome.storage.local.set({
          savedUrls: [...existing, ...newItems]
        }, () => resolve(newItems.length));
      });
    });
  }

  function updateStatus(el, text) {
    if (el) el.textContent = text;
  }

  // ——— Inject floating scraper UI ———

  function injectScraperButton() {
    if (document.getElementById(SCRAPER_ID)) return;
    if (!checkIfPostSearchPage()) return;

    const container = document.createElement('div');
    container.id = SCRAPER_ID;
    container.innerHTML = `
      <style>
        #${SCRAPER_ID} {
          position: fixed; bottom: 20px; right: 20px; z-index: 99999;
          font-family: 'Outfit', -apple-system, sans-serif;
        }
        .antek-scraper-panel {
          background: #0A0A0A; border: 2px solid #E0654A;
          border-radius: 8px; padding: 12px 16px; min-width: 260px;
          box-shadow: 0 8px 32px rgba(0,0,0,.4);
          color: #E8DCC8;
        }
        .antek-scraper-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 8px;
        }
        .antek-scraper-logo {
          display: flex; align-items: center; gap: 6px;
          font-weight: 600; font-size: 13px;
        }
        .antek-scraper-mark {
          width: 20px; height: 20px; background: #E0654A; color: #0A0A0A;
          display: inline-flex; align-items: center; justify-content: center;
          font-weight: 700; font-size: 12px; border-radius: 3px;
        }
        .antek-scraper-close {
          background: none; border: none; color: #8a8072;
          font-size: 18px; cursor: pointer; line-height: 1;
        }
        .antek-scraper-close:hover { color: #E0654A; }
        .antek-scraper-status {
          font-size: 11px; color: #8a8072; margin-bottom: 8px;
          font-family: 'JetBrains Mono', monospace;
        }
        .antek-scraper-btns { display: flex; gap: 6px; }
        .antek-scraper-btn {
          flex: 1; padding: 8px 12px; border: none; border-radius: 4px;
          font-family: 'Outfit', sans-serif; font-size: 12px; font-weight: 500;
          cursor: pointer; transition: .15s;
        }
        .antek-scraper-btn.primary {
          background: #E0654A; color: #0A0A0A;
        }
        .antek-scraper-btn.primary:hover { background: #c4543b; }
        .antek-scraper-btn.primary:disabled {
          opacity: .5; cursor: not-allowed;
        }
        .antek-scraper-btn.secondary {
          background: #2C2C2C; color: #E8DCC8; border: 1px solid #3a3a3a;
        }
        .antek-scraper-btn.secondary:hover { border-color: #E0654A; color: #E0654A; }
        .antek-scraper-spinner {
          display: inline-block; width: 10px; height: 10px;
          border: 2px solid #3a3a3a; border-top-color: #E0654A;
          border-radius: 50%; animation: antek-spin .6s linear infinite;
          margin-right: 6px; vertical-align: middle;
        }
        @keyframes antek-spin { to { transform: rotate(360deg); } }
        .antek-scraper-minimized {
          width: 44px; height: 44px; background: #E0654A;
          border-radius: 50%; display: flex; align-items: center;
          justify-content: center; cursor: pointer;
          box-shadow: 0 4px 16px rgba(224,101,74,.4);
          font-weight: 700; font-size: 18px; color: #0A0A0A;
          transition: transform .15s;
        }
        .antek-scraper-minimized:hover { transform: scale(1.1); }
      </style>

      <div class="antek-scraper-panel" id="antek-panel">
        <div class="antek-scraper-header">
          <div class="antek-scraper-logo">
            <span class="antek-scraper-mark">A</span> Post Scraper
          </div>
          <button class="antek-scraper-close" id="antek-minimize" title="Minimize">&minus;</button>
        </div>
        <div class="antek-scraper-status" id="antek-status">Ready. Click scrape to collect all post URLs from this search.</div>
        <div class="antek-scraper-btns">
          <button class="antek-scraper-btn primary" id="antek-scrape-btn">Scrape Post URLs</button>
          <button class="antek-scraper-btn secondary" id="antek-copy-btn">Copy</button>
        </div>
      </div>

      <div class="antek-scraper-minimized" id="antek-fab" style="display:none" title="Open Post Scraper">
        A
      </div>
    `;

    document.body.appendChild(container);

    // Scrape button
    document.getElementById('antek-scrape-btn').addEventListener('click', async () => {
      const btn = document.getElementById('antek-scrape-btn');
      const status = document.getElementById('antek-status');
      btn.disabled = true;
      btn.innerHTML = '<span class="antek-scraper-spinner"></span> Scraping...';
      const urls = await scrapeAllPosts(status);
      btn.disabled = false;
      btn.textContent = `Scrape Again (${urls.length} found)`;
    });

    // Copy button
    document.getElementById('antek-copy-btn').addEventListener('click', async () => {
      const urls = extractPostUrls();
      if (urls.length === 0) {
        updateStatus(document.getElementById('antek-status'), 'No post URLs found yet. Scrape first.');
        return;
      }
      await navigator.clipboard.writeText(urls.join('\n'));
      updateStatus(document.getElementById('antek-status'), `Copied ${urls.length} URLs to clipboard.`);
    });

    // Minimize / restore
    document.getElementById('antek-minimize').addEventListener('click', () => {
      document.getElementById('antek-panel').style.display = 'none';
      document.getElementById('antek-fab').style.display = 'flex';
    });

    document.getElementById('antek-fab').addEventListener('click', () => {
      document.getElementById('antek-panel').style.display = 'block';
      document.getElementById('antek-fab').style.display = 'none';
    });
  }

  function removeScraperButton() {
    const el = document.getElementById(SCRAPER_ID);
    if (el) el.remove();
  }

  // ——— Watch for navigation changes ———

  let lastUrl = window.location.href;

  function checkPage() {
    const currentUrl = window.location.href;
    if (currentUrl !== lastUrl) {
      lastUrl = currentUrl;
      if (checkIfPostSearchPage()) {
        injectScraperButton();
      } else {
        removeScraperButton();
      }
    }
  }

  // LinkedIn is an SPA — poll for URL changes
  setInterval(checkPage, 1000);

  // Initial check
  if (checkIfPostSearchPage()) {
    setTimeout(injectScraperButton, 1500);
  }


  // =====================================================================
  // GROUP PAGE SCRAPER
  // Captures post URLs + engagement (likes/comments) from group feeds
  // Saves to chrome.storage under 'groupPosts' key
  // =====================================================================

  const GROUP_SCRAPER_ID = 'antek-group-scraper';
  let isGroupScraping = false;

  function checkIfGroupPage() {
    // Matches /groups/123456/ or /groups/123456/recent-activity/ etc
    return /\/groups\/\d+/.test(window.location.pathname);
  }

  function getGroupIdFromUrl() {
    const m = window.location.pathname.match(/\/groups\/(\d+)/);
    return m ? m[1] : null;
  }

  // Parse a number from text like "42", "1.2K", "3.4k", "1,234"
  function parseCount(text) {
    if (!text) return 0;
    const cleaned = text.replace(/,/g, '').trim();
    const m = cleaned.match(/([\d.]+)\s*([kKmM])?/);
    if (!m) return 0;
    let n = parseFloat(m[1]);
    if (isNaN(n)) return 0;
    if (m[2]) {
      const mult = m[2].toLowerCase() === 'k' ? 1000 : 1000000;
      n = Math.round(n * mult);
    }
    return Math.round(n);
  }

  // Extract a single post's data from its container element
  function extractPostFromContainer(container) {
    // ——— Post URL ———
    let postUrl = null;

    // Try data-urn first (most reliable on LinkedIn feed)
    const urn = container.getAttribute('data-urn') ||
                container.getAttribute('data-id') ||
                container.querySelector('[data-urn]')?.getAttribute('data-urn');
    if (urn && /urn:li:(activity|ugcPost|share):/.test(urn)) {
      postUrl = `https://www.linkedin.com/feed/update/${urn.match(/urn:li:(activity|ugcPost|share):\d+/)[0]}/`;
    }

    // Fallback: timestamp / permalink anchor
    if (!postUrl) {
      const link = container.querySelector('a[href*="/feed/update/"]');
      if (link) {
        const href = link.href.split('?')[0];
        if (/urn:li:(activity|ugcPost|share):\d+/.test(href)) postUrl = href;
      }
    }
    if (!postUrl) return null;

    // ——— Author ———
    let authorName = '';
    let authorHeadline = '';
    let authorProfileUrl = '';

    const actor = container.querySelector('.update-components-actor, .feed-shared-actor');
    if (actor) {
      const nameEl = actor.querySelector('.update-components-actor__title span[aria-hidden="true"], .update-components-actor__name span[aria-hidden="true"], .feed-shared-actor__name span[aria-hidden="true"]');
      authorName = nameEl?.textContent?.trim() || '';
      if (!authorName) {
        // Fallback to visually-hidden text
        const vh = actor.querySelector('.update-components-actor__title, .feed-shared-actor__name');
        authorName = vh?.textContent?.trim().split('\n')[0] || '';
      }

      const headEl = actor.querySelector('.update-components-actor__description span[aria-hidden="true"], .feed-shared-actor__description span[aria-hidden="true"]');
      authorHeadline = headEl?.textContent?.trim() || '';

      const profileLink = actor.querySelector('a[href*="/in/"]');
      if (profileLink) authorProfileUrl = profileLink.href.split('?')[0];
    }

    // ——— Date text (e.g. "3d", "2w") ———
    let postDateText = '';
    const dateEl = container.querySelector('.update-components-actor__sub-description span[aria-hidden="true"], .feed-shared-actor__sub-description span[aria-hidden="true"]');
    if (dateEl) {
      // Format is often "3d • 🌐" — take the bit before the dot
      postDateText = dateEl.textContent.trim().split(/[•·]/)[0].trim();
    }

    // ——— Engagement counts ———
    let likeCount = 0;
    let commentCount = 0;

    // Likes — usually in social-counts-reactions or aria-label
    const reactionsBtn = container.querySelector('.social-details-social-counts__reactions-count, .social-details-social-counts__count-value');
    if (reactionsBtn) {
      likeCount = parseCount(reactionsBtn.textContent);
    }
    // Fallback — aria-label like "123 reactions"
    if (!likeCount) {
      const ariaReact = container.querySelector('[aria-label*="reaction" i]');
      if (ariaReact) {
        const m = ariaReact.getAttribute('aria-label').match(/[\d.,]+\s*[kKmM]?/);
        if (m) likeCount = parseCount(m[0]);
      }
    }

    // Comments — usually a button with "X comments" text
    const commentBtn = container.querySelector('.social-details-social-counts__comments button, button[aria-label*="comment" i]');
    if (commentBtn) {
      const txt = commentBtn.textContent || commentBtn.getAttribute('aria-label') || '';
      const m = txt.match(/([\d.,]+\s*[kKmM]?)\s*comment/i);
      if (m) commentCount = parseCount(m[1]);
    }
    // Fallback — scan all buttons for "comment" text
    if (!commentCount) {
      const buttons = container.querySelectorAll('button, span');
      for (const b of buttons) {
        const t = (b.textContent || '').trim();
        const m = t.match(/^([\d.,]+\s*[kKmM]?)\s*comments?$/i);
        if (m) { commentCount = parseCount(m[1]); break; }
      }
    }

    return {
      post_url: postUrl,
      author_name: authorName,
      author_headline: authorHeadline,
      author_profile_url: authorProfileUrl,
      like_count: likeCount,
      comment_count: commentCount,
      post_date_text: postDateText,
      group_id: getGroupIdFromUrl() || '',
      scraped_at: new Date().toISOString()
    };
  }

  function extractAllGroupPosts() {
    const posts = [];
    const seen = new Set();
    // LinkedIn uses several wrappers — try each, dedupe by URL
    const containers = document.querySelectorAll(
      '.feed-shared-update-v2, ' +
      'div[data-urn*="urn:li:activity"], ' +
      'div[data-urn*="urn:li:ugcPost"], ' +
      'div[data-id*="urn:li:activity"], ' +
      'div[data-id*="urn:li:ugcPost"]'
    );
    containers.forEach(c => {
      const p = extractPostFromContainer(c);
      if (p && !seen.has(p.post_url)) {
        seen.add(p.post_url);
        posts.push(p);
      }
    });
    return posts;
  }

  // Auto-scroll, extract on each pass, merge by URL
  async function scrapeGroupFeed(maxPosts, statusEl) {
    if (isGroupScraping) return [];
    isGroupScraping = true;

    const byUrl = new Map();
    let staleScrolls = 0;
    let scrollIterations = 0;
    const maxIterations = 30;

    function mergeBatch(batch) {
      batch.forEach(p => {
        const existing = byUrl.get(p.post_url);
        if (!existing) byUrl.set(p.post_url, p);
        else {
          // Update with higher engagement counts (they tick up as more loads)
          existing.like_count = Math.max(existing.like_count, p.like_count);
          existing.comment_count = Math.max(existing.comment_count, p.comment_count);
        }
      });
    }

    // Initial extraction
    mergeBatch(extractAllGroupPosts());
    if (statusEl) statusEl.textContent = `Found ${byUrl.size} posts... scrolling`;

    while (scrollIterations < maxIterations && byUrl.size < maxPosts) {
      const prevHeight = document.body.scrollHeight;
      const prevCount = byUrl.size;
      window.scrollTo(0, document.body.scrollHeight);
      await new Promise(r => setTimeout(r, 1800));

      mergeBatch(extractAllGroupPosts());
      const newHeight = document.body.scrollHeight;
      const grew = newHeight > prevHeight;
      const foundNew = byUrl.size > prevCount;

      if (statusEl) statusEl.textContent = `Found ${byUrl.size} posts... scrolling (${scrollIterations + 1})`;

      if (!grew && !foundNew) {
        staleScrolls++;
        if (staleScrolls >= 3) break;
      } else {
        staleScrolls = 0;
      }
      scrollIterations++;
    }

    window.scrollTo(0, 0);

    const results = [...byUrl.values()];
    await saveGroupPosts(results);
    if (statusEl) statusEl.textContent = `Done. ${results.length} posts captured.`;

    isGroupScraping = false;
    return results;
  }

  // Merge into chrome.storage.local.groupPosts, dedupe by URL
  async function saveGroupPosts(newPosts) {
    return new Promise(resolve => {
      chrome.storage.local.get({ groupPosts: [] }, data => {
        const existing = data.groupPosts || [];
        const byUrl = new Map(existing.map(p => [p.post_url, p]));
        let added = 0;
        newPosts.forEach(p => {
          if (!byUrl.has(p.post_url)) added++;
          // Always update — engagement counts may have changed
          byUrl.set(p.post_url, { ...byUrl.get(p.post_url), ...p });
        });
        const merged = [...byUrl.values()];
        chrome.storage.local.set({ groupPosts: merged }, () => resolve(added));
      });
    });
  }

  function injectGroupPanel() {
    if (document.getElementById(GROUP_SCRAPER_ID)) return;
    if (!checkIfGroupPage()) return;

    const container = document.createElement('div');
    container.id = GROUP_SCRAPER_ID;
    container.innerHTML = `
      <style>
        #${GROUP_SCRAPER_ID} {
          position: fixed; bottom: 20px; right: 20px; z-index: 99999;
          font-family: 'Outfit', -apple-system, sans-serif;
        }
        .antek-grp-panel {
          background: #0A0A0A; border: 2px solid #E0654A;
          border-radius: 8px; padding: 12px 16px; min-width: 290px;
          box-shadow: 0 8px 32px rgba(0,0,0,.4);
          color: #E8DCC8;
        }
        .antek-grp-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 8px;
        }
        .antek-grp-logo {
          display: flex; align-items: center; gap: 6px;
          font-weight: 600; font-size: 13px;
        }
        .antek-grp-mark {
          width: 20px; height: 20px; background: #E0654A; color: #0A0A0A;
          display: inline-flex; align-items: center; justify-content: center;
          font-weight: 700; font-size: 12px; border-radius: 3px;
        }
        .antek-grp-close {
          background: none; border: none; color: #8a8072;
          font-size: 18px; cursor: pointer; line-height: 1;
        }
        .antek-grp-close:hover { color: #E0654A; }
        .antek-grp-status {
          font-size: 11px; color: #8a8072; margin-bottom: 8px;
          font-family: 'JetBrains Mono', monospace;
        }
        .antek-grp-input-row {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 6px; font-size: 11px; color: #b5a992;
        }
        .antek-grp-input-row input {
          width: 60px; padding: 3px 6px; background: #1A1A1A;
          border: 1px solid #3a3a3a; color: #E8DCC8;
          border-radius: 3px; font-family: 'JetBrains Mono', monospace;
          font-size: 11px; text-align: right;
        }
        .antek-grp-btns { display: flex; gap: 6px; margin-top: 8px; }
        .antek-grp-btn {
          flex: 1; padding: 8px 12px; border: none; border-radius: 4px;
          font-family: 'Outfit', sans-serif; font-size: 12px; font-weight: 500;
          cursor: pointer; transition: .15s;
        }
        .antek-grp-btn.primary { background: #E0654A; color: #0A0A0A; }
        .antek-grp-btn.primary:hover { background: #c4543b; }
        .antek-grp-btn.primary:disabled { opacity: .5; cursor: not-allowed; }
        .antek-grp-btn.secondary {
          background: #2C2C2C; color: #E8DCC8; border: 1px solid #3a3a3a;
        }
        .antek-grp-btn.secondary:hover { border-color: #E0654A; color: #E0654A; }
        .antek-grp-spinner {
          display: inline-block; width: 10px; height: 10px;
          border: 2px solid #3a3a3a; border-top-color: #E0654A;
          border-radius: 50%; animation: antek-spin .6s linear infinite;
          margin-right: 6px; vertical-align: middle;
        }
        .antek-grp-minimized {
          width: 44px; height: 44px; background: #E0654A;
          border-radius: 50%; display: flex; align-items: center;
          justify-content: center; cursor: pointer;
          box-shadow: 0 4px 16px rgba(224,101,74,.4);
          font-weight: 700; font-size: 18px; color: #0A0A0A;
          transition: transform .15s;
        }
        .antek-grp-minimized:hover { transform: scale(1.1); }
        .antek-grp-hint {
          font-size: 10px; color: #5a5248;
          font-family: 'JetBrains Mono', monospace;
          margin-top: 6px;
        }
      </style>

      <div class="antek-grp-panel" id="antek-grp-panel">
        <div class="antek-grp-header">
          <div class="antek-grp-logo">
            <span class="antek-grp-mark">A</span> Group Scraper
          </div>
          <button class="antek-grp-close" id="antek-grp-minimize" title="Minimize">&minus;</button>
        </div>
        <div class="antek-grp-status" id="antek-grp-status">Ready. Group ID: ${getGroupIdFromUrl() || '?'}</div>
        <div class="antek-grp-input-row">
          <span>Max posts</span>
          <input type="number" id="antek-grp-max" min="10" max="500" value="100">
        </div>
        <div class="antek-grp-btns">
          <button class="antek-grp-btn primary" id="antek-grp-scrape">Scrape Group</button>
          <button class="antek-grp-btn secondary" id="antek-grp-open-popup">View</button>
        </div>
        <div class="antek-grp-hint">Results appear in the extension popup &gt; Groups tab.</div>
      </div>

      <div class="antek-grp-minimized" id="antek-grp-fab" style="display:none" title="Open Group Scraper">G</div>
    `;

    document.body.appendChild(container);

    document.getElementById('antek-grp-scrape').addEventListener('click', async () => {
      const btn = document.getElementById('antek-grp-scrape');
      const status = document.getElementById('antek-grp-status');
      const maxPosts = parseInt(document.getElementById('antek-grp-max').value) || 100;
      btn.disabled = true;
      btn.innerHTML = '<span class="antek-grp-spinner"></span> Scraping...';
      const posts = await scrapeGroupFeed(maxPosts, status);
      btn.disabled = false;
      btn.textContent = `Scrape Again (${posts.length})`;
    });

    document.getElementById('antek-grp-open-popup').addEventListener('click', () => {
      const status = document.getElementById('antek-grp-status');
      status.textContent = 'Click the toolbar icon → Groups tab to view results.';
    });

    document.getElementById('antek-grp-minimize').addEventListener('click', () => {
      document.getElementById('antek-grp-panel').style.display = 'none';
      document.getElementById('antek-grp-fab').style.display = 'flex';
    });
    document.getElementById('antek-grp-fab').addEventListener('click', () => {
      document.getElementById('antek-grp-panel').style.display = 'block';
      document.getElementById('antek-grp-fab').style.display = 'none';
    });
  }

  function removeGroupPanel() {
    const el = document.getElementById(GROUP_SCRAPER_ID);
    if (el) el.remove();
  }

  // Hook into existing checkPage SPA-watcher
  // We extend lastUrl tracking by checking both page types
  let lastGroupCheckUrl = window.location.href;
  setInterval(() => {
    if (window.location.href !== lastGroupCheckUrl) {
      lastGroupCheckUrl = window.location.href;
      if (checkIfGroupPage()) {
        setTimeout(injectGroupPanel, 1500);
      } else {
        removeGroupPanel();
      }
    }
  }, 1000);

  if (checkIfGroupPage()) {
    setTimeout(injectGroupPanel, 1500);
  }

})();
