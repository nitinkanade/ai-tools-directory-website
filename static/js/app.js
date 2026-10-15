/**
 * AI Tools Directory — Client-Side Application Logic
 * Dark/Light Theme Switching, Debounced In-Memory Search, and Directory Filtering
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

  // --- Search Scoring Algorithm ---
  // Mirrors documentation in ARCHITECTURE.md
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
    // 2. Name starts with query
    else if (name.startsWith(q)) score += 60;
    // 3. Name contains query
    else if (name.includes(q)) score += 40;

    // 4. Token matches
    for (const token of qTokens) {
      if (name.includes(token)) score += 30;
      if (slug.includes(token)) score += 15;
      if (tags.some(t => t === token)) score += 25;
      else if (tags.some(t => t.includes(token))) score += 12;
      if (cats.some(c => c.includes(token))) score += 20;
      if (shortDesc.includes(token)) score += 5;
    }

    return score;
  }

  // --- Homepage Live Search Suggestions ---
  let cachedSearchIndex = null;

  async function loadSearchIndex() {
    if (cachedSearchIndex) return cachedSearchIndex;
    try {
      const baseUrl = window.__SITE_BASE_URL__ || '';
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
          dropdown.innerHTML = `<div style="padding: 1rem; text-align: center; color: var(--text-muted); font-size: 0.9rem;">No matching AI tools found for "<strong>${escapeHtml(query)}</strong>"</div>`;
          dropdown.style.display = 'block';
          return;
        }

        const baseUrl = window.__SITE_BASE_URL__ || '';
        dropdown.innerHTML = scored.map(({ tool }) => `
          <a href="${baseUrl}/tool/${tool.slug}/" class="search-dropdown-item">
            <div>
              <div style="font-weight: 700; color: var(--text-primary);">${escapeHtml(tool.name)}</div>
              <div style="font-size: 0.8125rem; color: var(--text-muted);">${escapeHtml(tool.shortDescription.substring(0, 60))}...</div>
            </div>
            <span class="badge badge-${tool.pricingModel === 'open-source' ? 'oss' : tool.pricingModel}">${tool.pricingModel}</span>
          </a>
        `).join('');
        dropdown.style.display = 'block';
      }, 250);
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
  }

  // --- Directory Interactive Filtering & Search ---
  function initDirectoryFilters() {
    const dirContainer = document.getElementById('directory-cards-container');
    if (!dirContainer) return;

    const cards = Array.from(dirContainer.getElementsByClassName('tool-card-item'));
    const searchInput = document.getElementById('directory-search-input');
    const resultCountEl = document.getElementById('directory-result-count');
    const activeChipsContainer = document.getElementById('active-filter-chips');

    // Filter checkboxes / selects
    const categoryChecks = Array.from(document.querySelectorAll('.filter-category-checkbox'));
    const pricingChecks = Array.from(document.querySelectorAll('.filter-pricing-checkbox'));
    const platformChecks = Array.from(document.querySelectorAll('.filter-platform-checkbox'));
    const ossOnlyCheck = document.getElementById('filter-oss-only');
    const sortSelect = document.getElementById('directory-sort-select');

    function applyFilters() {
      const q = (searchInput ? searchInput.value : '').toLowerCase().trim();
      const selectedCats = categoryChecks.filter(c => c.checked).map(c => c.value);
      const selectedPricing = pricingChecks.filter(c => c.checked).map(c => c.value);
      const selectedPlatforms = platformChecks.filter(c => c.checked).map(c => c.value);
      const ossOnly = ossOnlyCheck ? ossOnlyCheck.checked : false;

      let visibleCount = 0;

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
        } else {
          card.style.display = 'none';
        }
      });

      if (resultCountEl) {
        resultCountEl.textContent = `${visibleCount} AI tool${visibleCount === 1 ? '' : 's'} available`;
      }

      // Update active chips UI
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

    if (searchInput) {
      searchInput.addEventListener('input', applyFilters);
    }
    categoryChecks.forEach(c => c.addEventListener('change', applyFilters));
    pricingChecks.forEach(c => c.addEventListener('change', applyFilters));
    platformChecks.forEach(c => c.addEventListener('change', applyFilters));
    if (ossOnlyCheck) ossOnlyCheck.addEventListener('change', applyFilters));

    window.clearAllFilters = function() {
      if (searchInput) searchInput.value = '';
      categoryChecks.forEach(c => c.checked = false);
      pricingChecks.forEach(c => c.checked = false);
      platformChecks.forEach(c => c.checked = false);
      if (ossOnlyCheck) ossOnlyCheck.checked = false;
      applyFilters();
    };
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- Document Ready ---
  document.addEventListener('DOMContentLoaded', () => {
    initHomeSearch();
    initDirectoryFilters();
  });
})();
