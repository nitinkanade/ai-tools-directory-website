/**
 * AI Tools Directory — Client-Side Application Engine
 * Fast, zero-dependency, accessible, and mobile-first:
 * - Theme management (dark/light mode persistence)
 * - Mobile navigation drawer
 * - Universal Spotlight Command Palette Modal (Ctrl+K, Cmd+K, /)
 * - Favorites & Bookmarks system (persisted in localStorage)
 * - Real-time debounced in-memory search & fuzzy scoring
 * - Multi-faceted filtering (categories, pricing, platforms, OSS, saved-only)
 * - Mobile Filter Drawer & bidirectional state synchronization
 * - Code copy & FAQ accordion
 */

(function () {
  'use strict';

  // --- Base URL Resolver ---
  function getBaseUrl() {
    return window.__SITE_BASE_URL__ !== undefined ? window.__SITE_BASE_URL__ : '.';
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- Theme Management ---
  const THEME_KEY = 'ai_tools_dir_theme';
  const htmlEl = document.documentElement;

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') {
      htmlEl.setAttribute('data-theme', saved);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      htmlEl.setAttribute('data-theme', 'dark');
    } else {
      htmlEl.setAttribute('data-theme', 'light');
    }
  }

  window.toggleTheme = function () {
    const current = htmlEl.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    htmlEl.setAttribute('data-theme', next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (e) {}
  };

  initTheme();

  // --- Mobile Navigation Drawer Toggle ---
  window.toggleMobileMenu = function () {
    const drawer = document.getElementById('mobile-drawer');
    const btn = document.getElementById('mobile-hamburger-btn');
    if (drawer) {
      const isOpen = drawer.classList.toggle('open');
      if (btn) btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      document.body.style.overflow = isOpen ? 'hidden' : '';
    }
  };

  // --- Code Copy Button ---
  window.copyCode = function (btn) {
    const container = btn.closest('.code-block-container');
    if (!container) return;
    const codeEl = container.querySelector('code');
    if (!codeEl) return;
    navigator.clipboard.writeText(codeEl.innerText).then(() => {
      const orig = btn.innerText;
      btn.innerText = 'Copied!';
      btn.style.background = '#10b981';
      setTimeout(() => {
        btn.innerText = orig;
        btn.style.background = '';
      }, 2000);
    });
  };

  // --- FAQ Accordion ---
  window.toggleFaq = function (headerEl) {
    const item = headerEl.closest('.faq-item');
    if (item) {
      item.classList.toggle('active');
    }
  };

  // --- Favorites (Bookmarks) System ---
  const FAV_KEY = 'ai_tools_dir_favorites';

  function getFavorites() {
    try {
      const data = localStorage.getItem(FAV_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  }

  function isFavorite(id) {
    return getFavorites().includes(id);
  }

  window.toggleFavorite = function (event, toolId) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const favs = getFavorites();
    const idx = favs.indexOf(toolId);
    let isNowFav = false;
    if (idx > -1) {
      favs.splice(idx, 1);
      isNowFav = false;
    } else {
      favs.push(toolId);
      isNowFav = true;
    }
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify(favs));
    } catch (e) {
      console.warn('Failed to save favorite:', e);
    }

    syncFavoritesUI();

    if (typeof window.applyDirectoryFilters === 'function') {
      window.applyDirectoryFilters();
    }
  };

  function syncFavoritesUI() {
    const favs = getFavorites();

    // 1. Update all card favorite buttons
    document.querySelectorAll('.card-fav-btn').forEach(btn => {
      const tid = btn.dataset.toolId;
      if (favs.includes(tid)) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        btn.setAttribute('title', 'Remove from saved tools');
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
        btn.setAttribute('title', 'Save tool');
      }
    });

    // 2. Update tool detail page button
    document.querySelectorAll('.fav-detail-btn').forEach(btn => {
      const tid = btn.dataset.toolId;
      const label = btn.querySelector('.fav-detail-label');
      if (favs.includes(tid)) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        if (label) label.textContent = 'Saved in Favorites';
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
        if (label) label.textContent = 'Save Tool';
      }
    });

    // 3. Update count badges
    const deskBadge = document.getElementById('saved-count-badge');
    const mobBadge = document.getElementById('mobile-saved-count-badge');
    if (deskBadge) deskBadge.textContent = favs.length;
    if (mobBadge) mobBadge.textContent = favs.length;
  }

  // --- Search Scoring Algorithm ---
  function scoreTool(tool, query) {
    if (!query) return 0;
    const q = query.toLowerCase().trim();
    const qTokens = q.split(/\s+/).filter(Boolean);

    const name = (tool.name || '').toLowerCase();
    const slug = (tool.slug || '').toLowerCase();
    const shortDesc = (tool.shortDescription || '').toLowerCase();
    const tags = (tool.tags || []).map(t => t.toLowerCase());
    const cats = (tool.categories || []).map(c => c.toLowerCase());

    let score = 0;

    // 1. Name exact match
    if (name === q) score += 100;
    else if (name.startsWith(q)) score += 60;
    else if (name.includes(q)) score += 40;

    // 2. Token matches
    for (const token of qTokens) {
      if (name.includes(token)) score += 30;
      if (slug.includes(token)) score += 15;
      if (tags.some(t => t === token)) score += 25;
      else if (tags.some(t => t.includes(token))) score += 12;
      if (cats.some(c => c.includes(token))) score += 20;
      if (shortDesc.includes(token)) score += 8;
    }

    return score;
  }

  function getToolGradientJs(tool) {
    const cats = tool.categories || [];
    if (cats.includes('coding-development')) return 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
    if (cats.includes('chatbots-assistants')) return 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)';
    if (cats.includes('image-generation')) return 'linear-gradient(135deg, #ec4899 0%, #d946ef 100%)';
    if (cats.includes('research-analysis')) return 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)';
    if (cats.includes('writing-content')) return 'linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)';
    if (cats.includes('voice-speech-audio')) return 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)';
    if (cats.includes('opensource-models-platforms')) return 'linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)';
    return 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)';
  }

  // --- Search Index Loader ---
  let cachedSearchIndex = null;

  async function loadSearchIndex() {
    if (cachedSearchIndex) return cachedSearchIndex;
    try {
      const baseUrl = getBaseUrl();
      const res = await fetch(`${baseUrl}/data/search-index.json`);
      if (!res.ok) throw new Error('Failed to load search index');
      cachedSearchIndex = await res.json();
      return cachedSearchIndex;
    } catch (e) {
      console.warn('Search index load error:', e);
      return [];
    }
  }

  // --- Universal Spotlight Command Palette Modal ---
  let spotlightActiveIndex = -1;

  window.openSpotlight = function () {
    const modal = document.getElementById('spotlight-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    const input = document.getElementById('spotlight-input');
    if (input) {
      input.focus();
      if (!input.value) {
        renderSpotlightInitial();
      }
    }
    loadSearchIndex();
  };

  window.closeSpotlight = function () {
    const modal = document.getElementById('spotlight-modal');
    if (!modal) return;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    spotlightActiveIndex = -1;
  };

  window.clearSpotlightInput = function () {
    const input = document.getElementById('spotlight-input');
    const clearBtn = document.getElementById('spotlight-clear-btn');
    if (input) {
      input.value = '';
      input.focus();
    }
    if (clearBtn) clearBtn.style.display = 'none';
    renderSpotlightInitial();
  };

  window.setSpotlightQuery = function (query) {
    const input = document.getElementById('spotlight-input');
    if (!input) return;
    input.value = query;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  };

  async function renderSpotlightInitial() {
    const resultsContainer = document.getElementById('spotlight-results');
    if (!resultsContainer) return;
    const items = await loadSearchIndex();
    const initialTools = items.slice(0, 6);
    renderSpotlightItems(initialTools, resultsContainer, 'Popular & Featured AI Tools');
  }

  function renderSpotlightItems(tools, container, headerTitle = '') {
    const baseUrl = getBaseUrl();
    spotlightActiveIndex = -1;

    if (!tools || tools.length === 0) {
      container.innerHTML = `
        <div class="spotlight-empty">
          <span class="spotlight-empty-icon">&#128269;</span>
          <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.25rem;">No matching AI tools found</div>
          <div style="font-size: 0.875rem;">Try a different keyword, category, or pricing model.</div>
        </div>
      `;
      return;
    }

    const html = tools.map((tool, idx) => {
      const initial = (tool.name || 'A')[0].toUpperCase();
      const pricing = tool.pricingModel || 'freemium';
      const badgeClass = pricing === 'open-source' ? 'badge-oss' : `badge-${pricing}`;
      const gradient = getToolGradientJs(tool);
      const isFav = isFavorite(tool.id || tool.slug);

      return `
        <a href="${baseUrl}/tool/${tool.slug}/" class="spotlight-item" data-index="${idx}">
          <div class="spotlight-item-monogram" style="background: ${gradient};">${escapeHtml(initial)}</div>
          <div class="spotlight-item-info">
            <div class="spotlight-item-header">
              <span class="spotlight-item-name">${escapeHtml(tool.name)}</span>
              ${tool.isOpenSource ? '<span class="badge badge-oss" style="font-size: 0.65rem;">OSS</span>' : ''}
              <span class="badge ${badgeClass}" style="font-size: 0.65rem;">${escapeHtml(pricing)}</span>
              ${isFav ? '<span style="color: #f59e0b; font-size: 0.85rem;" title="Saved in Favorites">&#9733;</span>' : ''}
            </div>
            <div class="spotlight-item-desc">${escapeHtml(tool.shortDescription || '')}</div>
          </div>
          <div class="spotlight-item-meta">
            <span style="font-size: 0.875rem; color: var(--text-muted);">&rarr;</span>
          </div>
        </a>
      `;
    }).join('');

    container.innerHTML = (headerTitle ? `<div style="font-size: 0.75rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); padding: 0.5rem 0.85rem 0.25rem;">${escapeHtml(headerTitle)}</div>` : '') + html;
  }

  function initSpotlightModal() {
    const input = document.getElementById('spotlight-input');
    const clearBtn = document.getElementById('spotlight-clear-btn');
    const resultsContainer = document.getElementById('spotlight-results');
    if (!input || !resultsContainer) return;

    let debounceTimer = null;

    input.addEventListener('input', () => {
      const q = input.value.trim();
      if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(async () => {
        if (!q) {
          renderSpotlightInitial();
          return;
        }

        const items = await loadSearchIndex();
        const scored = items
          .map(t => ({ tool: t, score: scoreTool(t, q) }))
          .filter(x => x.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 8);

        renderSpotlightItems(scored.map(s => s.tool), resultsContainer, `Search Results for "${q}"`);
      }, 150);
    });

    input.addEventListener('keydown', (e) => {
      const items = resultsContainer.querySelectorAll('.spotlight-item');
      if (items.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        spotlightActiveIndex = (spotlightActiveIndex + 1) % items.length;
        updateSpotlightSelection(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        spotlightActiveIndex = (spotlightActiveIndex - 1 + items.length) % items.length;
        updateSpotlightSelection(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (spotlightActiveIndex >= 0 && spotlightActiveIndex < items.length) {
          items[spotlightActiveIndex].click();
        } else if (items.length > 0) {
          items[0].click();
        }
      } else if (e.key === 'Escape') {
        closeSpotlight();
      }
    });

    function updateSpotlightSelection(items) {
      items.forEach((item, idx) => {
        if (idx === spotlightActiveIndex) {
          item.classList.add('selected');
          item.scrollIntoView({ block: 'nearest' });
        } else {
          item.classList.remove('selected');
        }
      });
    }
  }

  // --- Homepage Live Search Suggestions ---
  function initHomeSearch() {
    const searchInput = document.getElementById('home-search-input');
    const dropdown = document.getElementById('home-search-dropdown');
    const clearBtn = document.getElementById('home-search-clear');
    if (!searchInput || !dropdown) return;

    let debounceTimer = null;

    searchInput.addEventListener('input', () => {
      const query = searchInput.value.trim();
      if (clearBtn) clearBtn.style.display = query ? 'block' : 'none';

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(async () => {
        if (!query || query.length < 2) {
          dropdown.style.display = 'none';
          dropdown.innerHTML = '';
          return;
        }

        const items = await loadSearchIndex();
        const scored = items
          .map(t => ({ tool: t, score: scoreTool(t, query) }))
          .filter(x => x.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 6);

        if (scored.length === 0) {
          dropdown.innerHTML = `<div style="padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.95rem;">No matching AI tools found for "<strong>${escapeHtml(query)}</strong>"</div>`;
          dropdown.style.display = 'block';
          return;
        }

        const baseUrl = getBaseUrl();
        dropdown.innerHTML = scored.map(({ tool }) => `
          <a href="${baseUrl}/tool/${tool.slug}/" class="search-dropdown-item">
            <div>
              <div style="font-weight: 700; color: var(--text-primary); font-size: 1rem;">${escapeHtml(tool.name)}</div>
              <div style="font-size: 0.8125rem; color: var(--text-muted); margin-top: 0.15rem;">${escapeHtml((tool.shortDescription || '').substring(0, 75))}...</div>
            </div>
            <span class="badge badge-${tool.pricingModel === 'open-source' ? 'oss' : tool.pricingModel}">${tool.pricingModel}</span>
          </a>
        `).join('');
        dropdown.style.display = 'block';
      }, 150);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = searchInput.value.trim();
        const baseUrl = getBaseUrl();
        window.location.href = `${baseUrl}/tools/?q=${encodeURIComponent(q)}`;
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        dropdown.style.display = 'none';
        searchInput.focus();
      });
    }

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
      }
    });

    // Quick filter pills below search
    document.querySelectorAll('.quick-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        const filterVal = pill.dataset.filter;
        if (filterVal) {
          const baseUrl = getBaseUrl();
          window.location.href = `${baseUrl}/tools/${filterVal}`;
        }
      });
    });
  }

  // --- Keyboard Shortcuts (Ctrl+K, Cmd+K, /, Esc) ---
  function initKeyboardShortcut() {
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openSpotlight();
      } else if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        openSpotlight();
      } else if (e.key === 'Escape') {
        closeSpotlight();
        const drawer = document.getElementById('mobile-drawer');
        if (drawer && drawer.classList.contains('open')) {
          drawer.classList.remove('open');
          document.body.style.overflow = '';
        }
        const filterDrawer = document.getElementById('mobile-filter-drawer');
        if (filterDrawer && filterDrawer.style.display !== 'none') {
          filterDrawer.style.display = 'none';
          document.body.style.overflow = '';
        }
      }
    });

    const triggerBtn = document.getElementById('quick-search-trigger');
    if (triggerBtn) {
      triggerBtn.addEventListener('click', openSpotlight);
    }
  }

  // --- Directory Interactive Filtering & Sorting ---
  window.toggleMobileFilterDrawer = function () {
    const drawer = document.getElementById('mobile-filter-drawer');
    if (!drawer) return;
    const isVisible = drawer.style.display !== 'none';
    drawer.style.display = isVisible ? 'none' : 'block';
    document.body.style.overflow = isVisible ? '' : 'hidden';
  };

  window.syncDirectorySort = function (val) {
    const deskSelect = document.getElementById('directory-sort-select');
    const mobSelect = document.getElementById('mobile-directory-sort-select');
    if (deskSelect) deskSelect.value = val;
    if (mobSelect) mobSelect.value = val;
    if (typeof window.applyDirectoryFilters === 'function') {
      window.applyDirectoryFilters();
    }
  };

  window.clearDirectorySearch = function () {
    const input = document.getElementById('directory-search-input');
    const clearBtn = document.getElementById('directory-search-clear');
    if (input) {
      input.value = '';
      if (clearBtn) clearBtn.style.display = 'none';
      if (typeof window.applyDirectoryFilters === 'function') {
        window.applyDirectoryFilters();
      }
      input.focus();
    }
  };

  function initDirectoryFilters() {
    const dirContainer = document.getElementById('directory-cards-container');
    if (!dirContainer) return;

    const cards = Array.from(dirContainer.getElementsByClassName('tool-card-item'));
    const searchInput = document.getElementById('directory-search-input');
    const searchClear = document.getElementById('directory-search-clear');
    const resultCountEl = document.getElementById('directory-result-count');
    const activeChipsContainer = document.getElementById('active-filter-chips');

    const categoryChecks = Array.from(document.querySelectorAll('.filter-category-checkbox'));
    const pricingChecks = Array.from(document.querySelectorAll('.filter-pricing-checkbox'));
    const platformChecks = Array.from(document.querySelectorAll('.filter-platform-checkbox'));
    const deskOssCheck = document.getElementById('filter-oss-only');
    const mobOssCheck = document.getElementById('mobile-filter-oss-only');
    const deskSavedCheck = document.getElementById('filter-saved-only');
    const mobSavedCheck = document.getElementById('mobile-filter-saved-only');
    const deskSort = document.getElementById('directory-sort-select');

    // Parse URL query parameters if present
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('q') && searchInput) {
      searchInput.value = urlParams.get('q');
      if (searchClear) searchClear.style.display = 'block';
    }
    if (urlParams.has('category')) {
      const cat = urlParams.get('category');
      categoryChecks.forEach(c => { if (c.value === cat) c.checked = true; });
    }
    if (urlParams.has('pricing')) {
      const pr = urlParams.get('pricing');
      pricingChecks.forEach(c => { if (c.value === pr) c.checked = true; });
    }
    if (urlParams.has('oss')) {
      if (deskOssCheck) deskOssCheck.checked = true;
      if (mobOssCheck) mobOssCheck.checked = true;
    }
    if (urlParams.has('saved')) {
      if (deskSavedCheck) deskSavedCheck.checked = true;
      if (mobSavedCheck) mobSavedCheck.checked = true;
    }

    function syncCategory(val, isChecked) {
      categoryChecks.filter(c => c.value === val).forEach(c => c.checked = isChecked);
    }

    function syncPricing(val, isChecked) {
      pricingChecks.filter(c => c.value === val).forEach(c => c.checked = isChecked);
    }

    function syncPlatform(val, isChecked) {
      platformChecks.filter(c => c.value === val).forEach(c => c.checked = isChecked);
    }

    function syncOss(isChecked) {
      if (deskOssCheck) deskOssCheck.checked = isChecked;
      if (mobOssCheck) mobOssCheck.checked = isChecked;
    }

    function syncSaved(isChecked) {
      if (deskSavedCheck) deskSavedCheck.checked = isChecked;
      if (mobSavedCheck) mobSavedCheck.checked = isChecked;
    }

    function applyFilters() {
      const q = (searchInput ? searchInput.value : '').toLowerCase().trim();
      if (searchClear) searchClear.style.display = q ? 'block' : 'none';

      // Gather distinct checked values
      const selectedCats = [...new Set(categoryChecks.filter(c => c.checked).map(c => c.value))];
      const selectedPricing = [...new Set(pricingChecks.filter(c => c.checked).map(c => c.value))];
      const selectedPlatforms = [...new Set(platformChecks.filter(c => c.checked).map(c => c.value))];
      const ossOnly = Boolean((deskOssCheck && deskOssCheck.checked) || (mobOssCheck && mobOssCheck.checked));
      const savedOnly = Boolean((deskSavedCheck && deskSavedCheck.checked) || (mobSavedCheck && mobSavedCheck.checked));

      const favs = getFavorites();

      let visibleCount = 0;
      let matchedCards = [];

      cards.forEach(card => {
        const id = card.dataset.id || '';
        const name = card.dataset.name || '';
        const desc = card.dataset.desc || '';
        const cats = (card.dataset.categories || '').split(',');
        const tags = (card.dataset.tags || '').split(',');
        const pricing = card.dataset.pricing || '';
        const platforms = (card.dataset.platforms || '').split(',');
        const isOss = card.dataset.oss === 'true';

        let matchesSearch = true;
        if (q) {
          const fakeTool = { name, slug: card.dataset.slug, shortDescription: desc, categories: cats, tags };
          matchesSearch = scoreTool(fakeTool, q) > 0;
        }

        const matchesCat = selectedCats.length === 0 || selectedCats.some(c => cats.includes(c));
        const matchesPricing = selectedPricing.length === 0 || selectedPricing.includes(pricing);
        const matchesPlatform = selectedPlatforms.length === 0 || selectedPlatforms.some(p => platforms.includes(p));
        const matchesOss = !ossOnly || isOss;
        const matchesSaved = !savedOnly || favs.includes(id);

        if (matchesSearch && matchesCat && matchesPricing && matchesPlatform && matchesOss && matchesSaved) {
          card.style.display = '';
          visibleCount++;
          matchedCards.push(card);
        } else {
          card.style.display = 'none';
        }
      });

      // Apply Sorting
      const sortMode = (deskSort ? deskSort.value : 'featured');
      if (sortMode === 'name-asc') {
        matchedCards.sort((a, b) => (a.dataset.name || '').localeCompare(b.dataset.name || ''));
      } else if (sortMode === 'name-desc') {
        matchedCards.sort((a, b) => (b.dataset.name || '').localeCompare(a.dataset.name || ''));
      }
      matchedCards.forEach(c => dirContainer.appendChild(c));

      if (resultCountEl) {
        resultCountEl.innerHTML = `Showing <strong>${visibleCount}</strong> verified AI tool${visibleCount === 1 ? '' : 's'}`;
      }

      // Update mobile filter badge
      const activeFilterCount = selectedCats.length + selectedPricing.length + selectedPlatforms.length + (ossOnly ? 1 : 0) + (savedOnly ? 1 : 0);
      const mobFilterBadge = document.getElementById('mobile-filter-badge');
      if (mobFilterBadge) {
        if (activeFilterCount > 0) {
          mobFilterBadge.textContent = activeFilterCount;
          mobFilterBadge.style.display = 'inline-flex';
        } else {
          mobFilterBadge.style.display = 'none';
        }
      }

      // Empty state handler
      let emptyMsg = document.getElementById('dir-empty-state');
      if (visibleCount === 0) {
        if (!emptyMsg) {
          emptyMsg = document.createElement('div');
          emptyMsg.id = 'dir-empty-state';
          emptyMsg.style.cssText = 'grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);';
          emptyMsg.innerHTML = `
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🔍</div>
            <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem;">No AI tools match your criteria</h3>
            <p style="font-size: 0.95rem; margin-bottom: 1.5rem;">Try relaxing your filters or search keyword.</p>
            <button onclick="clearAllFilters()" class="btn btn-primary">Reset All Filters</button>
          `;
          dirContainer.appendChild(emptyMsg);
        } else {
          emptyMsg.style.display = 'block';
        }
      } else if (emptyMsg) {
        emptyMsg.style.display = 'none';
      }

      updateChips(selectedCats, selectedPricing, selectedPlatforms, ossOnly, savedOnly);
    }

    window.applyDirectoryFilters = applyFilters;

    function updateChips(selectedCats, selectedPricing, selectedPlatforms, ossOnly, savedOnly) {
      if (!activeChipsContainer) return;
      activeChipsContainer.innerHTML = '';

      if (savedOnly) {
        addChip('★ Saved Tools', () => {
          syncSaved(false);
          applyFilters();
        });
      }

      if (ossOnly) {
        addChip('Open Source Only', () => {
          syncOss(false);
          applyFilters();
        });
      }

      selectedCats.forEach(c => {
        addChip(`Category: ${c}`, () => {
          syncCategory(c, false);
          applyFilters();
        });
      });

      selectedPricing.forEach(p => {
        addChip(`Pricing: ${p}`, () => {
          syncPricing(p, false);
          applyFilters();
        });
      });

      selectedPlatforms.forEach(p => {
        addChip(`Platform: ${p}`, () => {
          syncPlatform(p, false);
          applyFilters();
        });
      });
    }

    function addChip(label, onRemove) {
      const chip = document.createElement('span');
      chip.className = 'filter-chip';
      chip.innerHTML = `${escapeHtml(label)} <button class="filter-chip-remove" aria-label="Remove filter">&times;</button>`;
      chip.querySelector('button').addEventListener('click', onRemove);
      activeChipsContainer.appendChild(chip);
    }

    if (searchInput) searchInput.addEventListener('input', applyFilters);

    categoryChecks.forEach(c => c.addEventListener('change', (e) => {
      syncCategory(c.value, e.target.checked);
      applyFilters();
    }));

    pricingChecks.forEach(c => c.addEventListener('change', (e) => {
      syncPricing(c.value, e.target.checked);
      applyFilters();
    }));

    platformChecks.forEach(c => c.addEventListener('change', (e) => {
      syncPlatform(c.value, e.target.checked);
      applyFilters();
    }));

    if (deskOssCheck) deskOssCheck.addEventListener('change', (e) => {
      syncOss(e.target.checked);
      applyFilters();
    });
    if (mobOssCheck) mobOssCheck.addEventListener('change', (e) => {
      syncOss(e.target.checked);
      applyFilters();
    });

    if (deskSavedCheck) deskSavedCheck.addEventListener('change', (e) => {
      syncSaved(e.target.checked);
      applyFilters();
    });
    if (mobSavedCheck) mobSavedCheck.addEventListener('change', (e) => {
      syncSaved(e.target.checked);
      applyFilters();
    });

    if (deskSort) deskSort.addEventListener('change', applyFilters);

    window.clearAllFilters = function () {
      if (searchInput) searchInput.value = '';
      if (searchClear) searchClear.style.display = 'none';
      categoryChecks.forEach(c => c.checked = false);
      pricingChecks.forEach(c => c.checked = false);
      platformChecks.forEach(c => c.checked = false);
      syncOss(false);
      syncSaved(false);
      applyFilters();
    };

    applyFilters();
  }

  // --- DOM Ready Bootstrap ---
  document.addEventListener('DOMContentLoaded', () => {
    syncFavoritesUI();
    initSpotlightModal();
    initHomeSearch();
    initKeyboardShortcut();
    initDirectoryFilters();
  });
})();
