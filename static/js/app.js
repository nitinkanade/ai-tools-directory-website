/**
 * AI Tools Directory — Client-Side Application Engine
 * Fast, zero-dependency, accessible interactions:
 * - Theme management (dark/light mode)
 * - Mobile navigation drawer
 * - Keyboard shortcuts (Ctrl+K / Cmd+K search focus)
 * - In-memory debounced live search & autocomplete
 * - Directory multi-faceted filtering & sorting
 * - Code copy & FAQ accordion
 */

(function () {
  'use strict';

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
    localStorage.setItem(THEME_KEY, next);
  };

  initTheme();

  // --- Mobile Drawer Toggle ---
  window.toggleMobileMenu = function () {
    const drawer = document.getElementById('mobile-drawer');
    if (drawer) {
      drawer.classList.toggle('open');
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

  // --- Base URL Resolver ---
  function getBaseUrl() {
    return window.__SITE_BASE_URL__ !== undefined ? window.__SITE_BASE_URL__ : '.';
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

  // --- Homepage Live Search Suggestions ---
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
              <div style="font-size: 0.8125rem; color: var(--text-muted); margin-top: 0.15rem;">${escapeHtml(tool.shortDescription.substring(0, 75))}...</div>
            </div>
            <span class="badge badge-${tool.pricingModel === 'open-source' ? 'oss' : tool.pricingModel}">${tool.pricingModel}</span>
          </a>
        `).join('');
        dropdown.style.display = 'block';
      }, 200);
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

  // --- Keyboard Shortcut (Ctrl+K or /) ---
  function initKeyboardShortcut() {
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        focusSearch();
      } else if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        focusSearch();
      }
    });

    const triggerBtn = document.getElementById('quick-search-trigger');
    if (triggerBtn) {
      triggerBtn.addEventListener('click', focusSearch);
    }
  }

  function focusSearch() {
    const homeSearch = document.getElementById('home-search-input');
    const dirSearch = document.getElementById('directory-search-input');
    if (homeSearch) {
      homeSearch.focus();
      homeSearch.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else if (dirSearch) {
      dirSearch.focus();
      dirSearch.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      const baseUrl = getBaseUrl();
      window.location.href = `${baseUrl}/tools/`;
    }
  }

  // --- Directory Interactive Filtering & Sorting ---
  function initDirectoryFilters() {
    const dirContainer = document.getElementById('directory-cards-container');
    if (!dirContainer) return;

    const cards = Array.from(dirContainer.getElementsByClassName('tool-card-item'));
    const searchInput = document.getElementById('directory-search-input');
    const resultCountEl = document.getElementById('directory-result-count');
    const activeChipsContainer = document.getElementById('active-filter-chips');

    const categoryChecks = Array.from(document.querySelectorAll('.filter-category-checkbox'));
    const pricingChecks = Array.from(document.querySelectorAll('.filter-pricing-checkbox'));
    const platformChecks = Array.from(document.querySelectorAll('.filter-platform-checkbox'));
    const ossOnlyCheck = document.getElementById('filter-oss-only');
    const sortSelect = document.getElementById('directory-sort-select');

    // Parse URL query parameters if present (e.g. ?category=coding-development&pricing=free)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('q') && searchInput) {
      searchInput.value = urlParams.get('q');
    }
    if (urlParams.has('category')) {
      const cat = urlParams.get('category');
      categoryChecks.forEach(c => { if (c.value === cat) c.checked = true; });
    }
    if (urlParams.has('pricing')) {
      const pr = urlParams.get('pricing');
      pricingChecks.forEach(c => { if (c.value === pr) c.checked = true; });
    }
    if (urlParams.has('oss') && ossOnlyCheck) {
      ossOnlyCheck.checked = true;
    }

    function applyFilters() {
      const q = (searchInput ? searchInput.value : '').toLowerCase().trim();
      const selectedCats = categoryChecks.filter(c => c.checked).map(c => c.value);
      const selectedPricing = pricingChecks.filter(c => c.checked).map(c => c.value);
      const selectedPlatforms = platformChecks.filter(c => c.checked).map(c => c.value);
      const ossOnly = ossOnlyCheck ? ossOnlyCheck.checked : false;

      let visibleCount = 0;
      let matchedCards = [];

      cards.forEach(card => {
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

        if (matchesSearch && matchesCat && matchesPricing && matchesPlatform && matchesOss) {
          card.style.display = '';
          visibleCount++;
          matchedCards.push(card);
        } else {
          card.style.display = 'none';
        }
      });

      // Apply Sorting
      if (sortSelect) {
        const sortMode = sortSelect.value;
        if (sortMode === 'name-asc') {
          matchedCards.sort((a, b) => (a.dataset.name || '').localeCompare(b.dataset.name || ''));
        } else if (sortMode === 'name-desc') {
          matchedCards.sort((a, b) => (b.dataset.name || '').localeCompare(a.dataset.name || ''));
        }
        matchedCards.forEach(c => dirContainer.appendChild(c));
      }

      if (resultCountEl) {
        resultCountEl.innerHTML = `Showing <strong>${visibleCount}</strong> verified AI tool${visibleCount === 1 ? '' : 's'}`;
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

      updateChips(selectedCats, selectedPricing, selectedPlatforms, ossOnly);
    }

    function updateChips(selectedCats, selectedPricing, selectedPlatforms, ossOnly) {
      if (!activeChipsContainer) return;
      activeChipsContainer.innerHTML = '';

      selectedCats.forEach(c => {
        addChip(`Category: ${c}`, () => {
          const chk = categoryChecks.find(x => x.value === c);
          if (chk) { chk.checked = false; applyFilters(); }
        });
      });

      selectedPricing.forEach(p => {
        addChip(`Pricing: ${p}`, () => {
          const chk = pricingChecks.find(x => x.value === p);
          if (chk) { chk.checked = false; applyFilters(); }
        });
      });

      selectedPlatforms.forEach(p => {
        addChip(`Platform: ${p}`, () => {
          const chk = platformChecks.find(x => x.value === p);
          if (chk) { chk.checked = false; applyFilters(); }
        });
      });

      if (ossOnly) {
        addChip('Open Source Only', () => {
          if (ossOnlyCheck) { ossOnlyCheck.checked = false; applyFilters(); }
        });
      }
    }

    function addChip(label, onRemove) {
      const chip = document.createElement('span');
      chip.className = 'filter-chip';
      chip.innerHTML = `${escapeHtml(label)} <button class="filter-chip-remove" aria-label="Remove filter">&times;</button>`;
      chip.querySelector('button').addEventListener('click', onRemove);
      activeChipsContainer.appendChild(chip);
    }

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    categoryChecks.forEach(c => c.addEventListener('change', applyFilters));
    pricingChecks.forEach(c => c.addEventListener('change', applyFilters));
    platformChecks.forEach(c => c.addEventListener('change', applyFilters));
    if (ossOnlyCheck) ossOnlyCheck.addEventListener('change', applyFilters);
    if (sortSelect) sortSelect.addEventListener('change', applyFilters);

    window.clearAllFilters = function () {
      if (searchInput) searchInput.value = '';
      categoryChecks.forEach(c => c.checked = false);
      pricingChecks.forEach(c => c.checked = false);
      platformChecks.forEach(c => c.checked = false);
      if (ossOnlyCheck) ossOnlyCheck.checked = false;
      applyFilters();
    };

    // Run initial filter check for query params
    applyFilters();
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- DOM Ready Bootstrap ---
  document.addEventListener('DOMContentLoaded', () => {
    initHomeSearch();
    initKeyboardShortcut();
    initDirectoryFilters();
  });
})();
