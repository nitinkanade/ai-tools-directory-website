"""
Zero-dependency static site generator for AI Tools Directory.
Generates fully-static, SEO-optimized HTML for GitHub Pages.
"""

import datetime
import html
import json
import os
import re
import shutil
import sys

WEBSITE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_DIR = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-database"))
APP_DIR = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-app"))
LOCAL_DATA_DIR = os.path.join(WEBSITE_DIR, "data")
DIST_DIR = os.path.join(WEBSITE_DIR, "dist")
STATIC_SRC = os.path.join(WEBSITE_DIR, "static")
CONTENT_DIR = os.path.join(WEBSITE_DIR, "content")

SITE_TITLE = "AI Tools Directory"
SITE_TAGLINE = "Discover, Compare & Master the Best AI Tools"
SITE_DESCRIPTION = "The premier independent directory of verified AI tools, open-source models, and developer assistants. Zero bias, 100% verified facts."
BASE_URL = ""  # For custom domain or root path; relative paths supported

def _copy_directory_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    count = 0
    for root, _, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target, exist_ok=True)
        for fname in files:
            shutil.copy2(os.path.join(root, fname), os.path.join(target, fname))
            count += 1
    return count

def resolve_and_sync_data():
    """
    Ensures website data is loaded directly from the database folder,
    and that website and app data are kept strictly synchronized.
    """
    db_public = os.path.join(DB_DIR, "public", "data")
    db_build_script = os.path.join(DB_DIR, "scripts", "build_indexes.py")

    # 1. If local database exists, rebuild indexes from master data/ and sync to website & app
    if os.path.exists(DB_DIR) and os.path.exists(db_build_script):
        print(f"--> [DATA SYNC] Rebuilding database indexes from {DB_DIR}/data...")
        import subprocess
        res = subprocess.run([sys.executable, db_build_script], cwd=DB_DIR, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[WARN] Failed to rebuild database indexes:\n{res.stderr}")
        else:
            print(f"    {res.stdout.strip()}")

        if os.path.exists(db_public):
            print(f"--> [DATA SYNC] Syncing database to website data folder ({LOCAL_DATA_DIR})...")
            _copy_directory_tree(db_public, LOCAL_DATA_DIR)

        # Sync to app assets if present
        app_assets = os.path.join(APP_DIR, "assets", "data")
        if os.path.exists(APP_DIR):
            print(f"--> [DATA SYNC] Syncing database to mobile app assets ({app_assets})...")
            _copy_directory_tree(db_public, app_assets)

        return LOCAL_DATA_DIR

    # 2. If website repository has its synced data snapshot, use it
    if os.path.exists(os.path.join(LOCAL_DATA_DIR, "manifest.json")):
        print(f"--> [DATA] Using local synced website data at {LOCAL_DATA_DIR}")
        return LOCAL_DATA_DIR

    # 3. Fallback: Run sync_data.py to pull from remote host
    sync_script = os.path.join(WEBSITE_DIR, "scripts", "sync_data.py")
    if os.path.exists(sync_script):
        import subprocess
        print("--> [DATA SYNC] No local data found, running website sync_data.py...")
        subprocess.run([sys.executable, sync_script], cwd=WEBSITE_DIR, check=True)
        return LOCAL_DATA_DIR

    raise FileNotFoundError("Could not locate or synchronize dataset for website build.")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def escape(text):
    if not text:
        return ""
    return html.escape(str(text))

# Simple Markdown to HTML parser (supports headings, lists, bold, italics, links, blockquotes, code)
def parse_markdown(md_text):
    lines = md_text.strip().split("\n")
    html_lines = []
    in_list = False
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                html_lines.append("<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(escape(line))
            continue

        # Close list if not in a list line
        if in_list and not (stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s", stripped)):
            html_lines.append("</ul>")
            in_list = False

        if not stripped:
            continue

        # Headings
        if stripped.startswith("### "):
            html_lines.append(f"<h3>{format_inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{format_inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{format_inline(stripped[2:])}</h1>")
        # Blockquote
        elif stripped.startswith("> "):
            html_lines.append(f"<blockquote><p>{format_inline(stripped[2:])}</p></blockquote>")
        # Horizontal Rule
        elif stripped in ("---", "***", "___"):
            html_lines.append("<hr style='margin: 2rem 0; border: none; border-top: 1px solid var(--border-color);'>")
        # Unordered list
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{format_inline(stripped[2:])}</li>")
        # Ordered list
        elif re.match(r"^\d+\.\s", stripped):
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            content = re.sub(r"^\d+\.\s", "", stripped)
            html_lines.append(f"<li>{format_inline(content)}</li>")
        else:
            html_lines.append(f"<p>{format_inline(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code_block:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)

def format_inline(text):
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Bold: **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text*
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text

def parse_frontmatter(md_content):
    if not md_content.startswith("---"):
        return {}, md_content
    parts = md_content.split("---", 2)
    if len(parts) < 3:
        return {}, md_content
    meta = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                # parse array
                items = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                meta[key] = items
            elif val.lower() == "true":
                meta[key] = True
            elif val.lower() == "false":
                meta[key] = False
            else:
                meta[key] = val.strip('"').strip("'")
    return meta, parts[2].strip()

# Layout shell generator
def render_page(title, meta_desc, content, canonical_path="", structured_data=None, current_nav=""):
    canonical_url = f"{BASE_URL}{canonical_path}"
    og_title = f"{title} | {SITE_TITLE}" if title != SITE_TITLE else f"{SITE_TITLE} — {SITE_TAGLINE}"

    sd_tag = ""
    if structured_data:
        sd_tag = f'<script type="application/ld+json">{json.dumps(structured_data, ensure_ascii=False)}</script>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(og_title)}</title>
  <meta name="description" content="{escape(meta_desc)}">
  <link rel="canonical" href="{escape(canonical_url)}">
  
  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="{escape(canonical_url)}">
  <meta property="og:title" content="{escape(og_title)}">
  <meta property="og:description" content="{escape(meta_desc)}">
  <meta property="og:site_name" content="{escape(SITE_TITLE)}">
  
  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(og_title)}">
  <meta name="twitter:description" content="{escape(meta_desc)}">

  <!-- Favicons & Brand Icons -->
  <link rel="icon" type="image/x-icon" href="{BASE_URL}/static/img/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="{BASE_URL}/static/img/favicon-32x32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="{BASE_URL}/static/img/apple-touch-icon.png">
  <meta property="og:image" content="{BASE_URL}/static/img/playstore-icon.png">
  <meta name="twitter:image" content="{BASE_URL}/static/img/playstore-icon.png">

  <!-- Fonts & Styling -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{BASE_URL}/static/css/styles.css">
  
  {sd_tag}
</head>
<body>
  <!-- Global Navigation Header -->
  <header class="site-header">
    <div class="container nav-container">
      <a href="{BASE_URL}/" class="brand-logo" aria-label="AI Tools Directory Homepage">
        <img src="{BASE_URL}/static/img/logo.png" alt="AI Tools Directory Logo" class="brand-icon-img" width="36" height="36">
        <span>AI Tools Directory</span>
      </a>

      <nav aria-label="Main navigation">
        <ul class="nav-links">
          <li><a href="{BASE_URL}/" class="nav-link {'active' if current_nav == 'home' else ''}">Home</a></li>
          <li><a href="{BASE_URL}/tools/" class="nav-link {'active' if current_nav == 'tools' else ''}">All Tools</a></li>
          <li><a href="{BASE_URL}/collections/" class="nav-link {'active' if current_nav == 'collections' else ''}">Collections</a></li>
          <li><a href="{BASE_URL}/blog/" class="nav-link {'active' if current_nav == 'blog' else ''}">Guides & Blog</a></li>
          <li><a href="{BASE_URL}/about/" class="nav-link {'active' if current_nav == 'about' else ''}">About</a></li>
        </ul>
      </nav>

      <div class="header-actions">
        <button class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle Dark / Light Theme" title="Toggle Theme">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>
      </div>
    </div>
  </header>

  <!-- Main Page Content -->
  <main id="main-content">
    {content}
  </main>

  <!-- Global Footer -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col">
          <div class="brand-logo" style="margin-bottom: 1rem;">
            <img src="{BASE_URL}/static/img/logo.png" alt="AI Tools Directory Logo" class="brand-icon-img" width="36" height="36">
            <span>AI Tools Directory</span>
          </div>
          <p style="font-size: 0.875rem; color: var(--text-muted); max-width: 320px; margin-bottom: 1.25rem;">
            The trusted, independent directory of verified AI software, open-source models, and developer companions.
          </p>
          <div style="font-size: 0.8125rem; color: var(--text-muted);">
            Zero paid endorsements. 100% verified data.
          </div>
        </div>

        <div class="footer-col">
          <h4>Explore</h4>
          <ul class="footer-links">
            <li><a href="{BASE_URL}/tools/">Directory Index</a></li>
            <li><a href="{BASE_URL}/collections/">Curated Collections</a></li>
            <li><a href="{BASE_URL}/category/coding-development/">Coding Tools</a></li>
            <li><a href="{BASE_URL}/category/chatbots-assistants/">AI Assistants</a></li>
            <li><a href="{BASE_URL}/category/opensource-models-platforms/">Open-Source AI</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Resources</h4>
          <ul class="footer-links">
            <li><a href="{BASE_URL}/blog/">Blog & Tutorials</a></li>
            <li><a href="{BASE_URL}/data/manifest.json">Data Manifest (API)</a></li>
            <li><a href="{BASE_URL}/data/tools/index.json">Static JSON Feed</a></li>
            <li><a href="{BASE_URL}/sitemap.xml">XML Sitemap</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Transparency</h4>
          <ul class="footer-links">
            <li><a href="{BASE_URL}/about/">About the Directory</a></li>
            <li><a href="{BASE_URL}/contact/">Contact & Feedback</a></li>
            <li><a href="{BASE_URL}/privacy/">Privacy Policy</a></li>
            <li><a href="{BASE_URL}/terms/">Terms of Use</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <div>&copy; {datetime.datetime.now().year} AI Tools Directory. Built with zero-cost static architecture.</div>
        <div style="display: flex; gap: 1.5rem;">
          <span>Android App: in.ni18.aitoolsdirectory</span>
          <span>Hosted on GitHub Pages</span>
        </div>
      </div>
    </div>
  </footer>

  <script>
    window.__SITE_BASE_URL__ = "{BASE_URL}";
  </script>
  <script src="{BASE_URL}/static/js/app.js"></script>
</body>
</html>"""

def render_tool_card(tool, show_full_category=True):
    pricing = tool.get("pricing", {}).get("model", "freemium")
    badge_class = "badge-oss" if pricing == "open-source" else f"badge-{pricing}"
    initial = tool["name"][0].upper()

    tags_html = "".join([f'<span class="tool-tag">#{escape(t)}</span>' for t in tool.get("tags", [])[:3]])

    return f"""
    <div class="tool-card tool-card-item" 
         data-name="{escape(tool['name'].lower())}"
         data-slug="{escape(tool['slug'])}"
         data-desc="{escape(tool['shortDescription'].lower())}"
         data-categories="{escape(','.join(tool.get('categories', [])))}"
         data-tags="{escape(','.join(tool.get('tags', [])))}"
         data-pricing="{escape(pricing)}"
         data-platforms="{escape(','.join(tool.get('platforms', [])))}"
         data-oss="{str(tool.get('isOpenSource') is True).lower()}">
      <div class="card-header">
        <div class="tool-monogram">{escape(initial)}</div>
        <div class="tool-header-content">
          <div class="tool-name-wrap">
            <a href="{BASE_URL}/tool/{tool['slug']}/" class="tool-title">{escape(tool['name'])}</a>
            <span class="verified-badge" title="Verified Factually">&#x2714;</span>
          </div>
          <span class="badge {badge_class}" style="margin-top: 0.35rem;">{escape(pricing)}</span>
        </div>
      </div>
      <p class="tool-short-desc">{escape(tool['shortDescription'])}</p>
      <div class="tool-tags">{tags_html}</div>
      <div class="card-footer">
        <span style="color: var(--text-muted); font-size: 0.75rem;">Verified {escape(tool.get('lastVerifiedAt', 'Recently'))}</span>
        <a href="{BASE_URL}/tool/{tool['slug']}/" class="view-all-link" style="font-size: 0.8125rem;">Details &rarr;</a>
      </div>
    </div>"""

def build_site(data_dir=None):
    data_source = data_dir or resolve_and_sync_data()
    print(f"--> Building static website to {DIST_DIR} using data from {data_source}...")
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    # Copy static assets
    shutil.copytree(STATIC_SRC, os.path.join(DIST_DIR, "static"))

    # Copy .well-known directory to dist root for Android App Links verification
    well_known_src = os.path.join(STATIC_SRC, ".well-known")
    if os.path.exists(well_known_src):
        shutil.copytree(well_known_src, os.path.join(DIST_DIR, ".well-known"))

    # Create .nojekyll so GitHub Pages serves dotfiles like .well-known
    with open(os.path.join(DIST_DIR, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    # Copy database public JSON data
    shutil.copytree(data_source, os.path.join(DIST_DIR, "data"))

    # Load master data
    tools = load_json(os.path.join(data_source, "tools", "index.json"))
    categories = load_json(os.path.join(data_source, "categories.json"))
    collections = load_json(os.path.join(data_source, "collections.json"))
    manifest = load_json(os.path.join(data_source, "manifest.json"))

    tool_map = {t["id"]: t for t in tools}
    category_map = {c["id"]: c for c in categories}
    sitemap_urls = []

    # 1. Homepage
    featured_tools = [t for t in tools if t.get("isFeatured")]
    recent_tools = sorted(tools, key=lambda x: x.get("createdAt", ""), reverse=True)[:6]

    home_content = f"""
    <section class="hero-section">
      <div class="container">
        <div class="hero-badge">
          <span>&starf; Single Source of Truth &bull; Zero Sponsored Bias</span>
        </div>
        <h1 class="hero-title">
          Explore the World of <br><span class="text-gradient">Verified AI Tools</span>
        </h1>
        <p class="hero-subtitle">
          Curated, benchmarked, and factually verified directory of artificial intelligence software, local runtimes, and developer assistants.
        </p>

        <!-- Live Instant Search -->
        <div class="search-container">
          <div class="search-input-wrapper">
            <span class="search-icon-prefix">&#128269;</span>
            <input type="text" id="home-search-input" class="search-input" placeholder="Search by name, category, coding, diffusion, reasoning..." autocomplete="off">
            <button id="home-search-clear" class="search-clear-btn" aria-label="Clear Search">&times;</button>
          </div>
          <div id="home-search-dropdown" class="search-dropdown"></div>
        </div>

        <!-- Live Stats Ribbon -->
        <div class="stats-ribbon">
          <div class="stat-item">
            <span class="stat-number">{len(tools)}+</span>
            <span class="stat-label">Verified Tools</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">{len(categories)}</span>
            <span class="stat-label">Taxonomy Categories</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">{len(collections)}</span>
            <span class="stat-label">Curated Collections</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">100%</span>
            <span class="stat-label">Zero Cost Hosting</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Featured AI Tools -->
    <section class="section">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Editor's Featured Selections</h2>
            <p class="section-desc">Hand-picked AI tools setting industry standards for performance and utility.</p>
          </div>
          <a href="{BASE_URL}/tools/" class="view-all-link">Browse all {len(tools)} tools &rarr;</a>
        </div>
        <div class="grid-tools">
          {"".join([render_tool_card(t) for t in featured_tools[:6]])}
        </div>
      </div>
    </section>

    <!-- Browse By Category -->
    <section class="section" style="background: var(--bg-secondary); border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Browse by Category</h2>
            <p class="section-desc">Find specialized solutions tailored to your industry and technical stack.</p>
          </div>
        </div>
        <div class="grid-categories">
          {"".join([f'''
          <a href="{BASE_URL}/category/{c['slug']}/" class="category-card">
            <div class="category-card-icon">&#9670;</div>
            <div class="category-card-title">{escape(c['name'])}</div>
            <p style="font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.75rem; flex: 1;">
              {escape(c['shortDescription'])}
            </p>
            <div class="category-card-count">Explore &rarr;</div>
          </a>''' for c in categories])}
        </div>
      </div>
    </section>

    <!-- Curated Collections -->
    <section class="section">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Curated Collections</h2>
            <p class="section-desc">Focused toolsets grouped for specific workflows and use cases.</p>
          </div>
          <a href="{BASE_URL}/collections/" class="view-all-link">View all collections &rarr;</a>
        </div>
        <div class="grid-collections">
          {"".join([f'''
          <a href="{BASE_URL}/collection/{col['slug']}/" class="collection-card">
            <div style="color: var(--brand-primary); font-size: 1.5rem; margin-bottom: 0.75rem;">&#9733;</div>
            <div class="collection-card-title">{escape(col['title'])}</div>
            <p class="collection-card-desc">{escape(col['description'])}</p>
            <div style="font-size: 0.8125rem; color: var(--text-muted); font-weight: 600;">
              {len(col['toolIds'])} Curated Tools &rarr;
            </div>
          </a>''' for col in collections[:3]])}
        </div>
      </div>
    </section>

    <!-- Recently Added Tools -->
    <section class="section" style="background: var(--bg-secondary); border-top: 1px solid var(--border-color);">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Recently Added to Directory</h2>
            <p class="section-desc">The latest verified tools added by our editorial maintainers.</p>
          </div>
          <a href="{BASE_URL}/tools/" class="view-all-link">See full directory &rarr;</a>
        </div>
        <div class="grid-tools">
          {"".join([render_tool_card(t) for t in recent_tools])}
        </div>
      </div>
    </section>
    """

    home_sd = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_TITLE,
        "description": SITE_DESCRIPTION,
        "url": BASE_URL or "https://in-ni18.github.io/ai-tools-directory",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{BASE_URL}/tools/?q={{search_term_string}}",
            "query-input": "required name=search_term_string"
        }
    }

    write_page("index.html", render_page(SITE_TITLE, SITE_DESCRIPTION, home_content, "/", home_sd, "home"))
    sitemap_urls.append(("/", "1.0", "daily"))

    # 2. Directory Page (/tools/index.html)
    dir_content = f"""
    <div class="container" style="padding: 2.5rem 1.5rem 4rem;">
      <div style="margin-bottom: 2rem;">
        <h1 class="section-title" style="font-size: 2.25rem;">Complete AI Tools Directory</h1>
        <p class="section-desc">Search, filter, and compare {len(tools)} verified artificial intelligence tools across categories and pricing tiers.</p>
      </div>

      <div class="directory-layout">
        <!-- Interactive Filter Sidebar -->
        <aside class="filter-sidebar">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
            <span style="font-weight: 700; font-size: 1.05rem;">Filters</span>
            <button onclick="clearAllFilters()" style="background: none; border: none; color: var(--brand-primary); font-size: 0.8125rem; font-weight: 600; cursor: pointer;">Reset All</button>
          </div>

          <!-- Open Source Switch -->
          <div class="filter-group">
            <label class="filter-label" style="font-weight: 600; color: var(--text-primary);">
              <input type="checkbox" id="filter-oss-only">
              <span>Open Source Only</span>
            </label>
          </div>

          <!-- Pricing Models -->
          <div class="filter-group">
            <div class="filter-title">Pricing Model</div>
            <div class="filter-options">
              <label class="filter-label"><input type="checkbox" class="filter-pricing-checkbox" value="free"> Free</label>
              <label class="filter-label"><input type="checkbox" class="filter-pricing-checkbox" value="freemium"> Freemium</label>
              <label class="filter-label"><input type="checkbox" class="filter-pricing-checkbox" value="paid"> Paid</label>
              <label class="filter-label"><input type="checkbox" class="filter-pricing-checkbox" value="open-source"> Open Source</label>
            </div>
          </div>

          <!-- Platforms -->
          <div class="filter-group">
            <div class="filter-title">Platform</div>
            <div class="filter-options">
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="web"> Web Browser</label>
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="windows"> Windows</label>
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="macos"> macOS</label>
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="linux"> Linux</label>
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="android"> Android</label>
              <label class="filter-label"><input type="checkbox" class="filter-platform-checkbox" value="ios"> iOS</label>
            </div>
          </div>

          <!-- Categories -->
          <div class="filter-group">
            <div class="filter-title">Category</div>
            <div class="filter-options" style="max-height: 280px; overflow-y: auto; padding-right: 0.25rem;">
              {"".join([f'<label class="filter-label"><input type="checkbox" class="filter-category-checkbox" value="{c["id"]}"> {escape(c["name"])}</label>' for c in categories])}
            </div>
          </div>
        </aside>

        <!-- Main Directory Listing -->
        <section>
          <!-- Search input bar -->
          <div style="margin-bottom: 1.5rem;">
            <div class="search-input-wrapper">
              <span class="search-icon-prefix">&#128269;</span>
              <input type="text" id="directory-search-input" class="search-input" placeholder="Filter tools by keyword, feature, or platform..." style="height: 3.25rem; font-size: 0.95rem;">
            </div>
          </div>

          <!-- Active Filter Chips -->
          <div id="active-filter-chips" class="active-filter-chips"></div>

          <!-- Results Header -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <span id="directory-result-count" style="font-size: 0.9375rem; color: var(--text-muted); font-weight: 500;">
              Showing all {len(tools)} tools
            </span>
          </div>

          <!-- Directory Cards Grid -->
          <div id="directory-cards-container" class="grid-tools">
            {"".join([render_tool_card(t) for t in tools])}
          </div>
        </section>
      </div>
    </div>
    """
    write_page("tools/index.html", render_page("AI Tools Directory Index", "Browse, search, and filter verified artificial intelligence tools.", dir_content, "/tools/", current_nav="tools"))
    sitemap_urls.append(("/tools/", "0.9", "daily"))

    # 3. Individual Tool Detail Pages (/tool/<slug>/index.html)
    full_tools_dir = os.path.join(data_source, "tools")
    for tool_entry in tools:
        slug = tool_entry["slug"]
        tool_file = os.path.join(full_tools_dir, f"{slug}.json")
        tool = load_json(tool_file)

        initial = tool["name"][0].upper()
        pricing = tool.get("pricing", {}).get("model", "freemium")
        pricing_details = tool.get("pricing", {}).get("details", "")
        badge_class = "badge-oss" if pricing == "open-source" else f"badge-{pricing}"

        primary_cat_id = tool["categories"][0]
        primary_cat = category_map.get(primary_cat_id, {"name": primary_cat_id, "slug": primary_cat_id})

        features_html = "".join([f'<li class="feature-list-item"><span class="check-icon">&#x2714;</span><span>{escape(feat)}</span></li>' for feat in tool.get("features", [])])
        use_cases_html = "".join([f'<li class="feature-list-item"><span class="check-icon">&#9670;</span><span>{escape(uc)}</span></li>' for uc in tool.get("useCases", [])])
        limitations_html = "".join([f'<li class="feature-list-item"><span style="color: #ef4444; flex-shrink: 0;">&bull;</span><span>{escape(lim)}</span></li>' for lim in tool.get("limitations", [])])

        alternatives_html = ""
        for alt_id in tool.get("alternatives", []):
            alt_tool = tool_map.get(alt_id)
            if alt_tool:
                alternatives_html += f'<a href="{BASE_URL}/tool/{alt_tool["slug"]}/" class="filter-chip" style="margin-right: 0.5rem; margin-bottom: 0.5rem;">{escape(alt_tool["name"])} &rarr;</a>'

        related_html = ""
        for rel_id in tool.get("relatedTools", []):
            rel_tool = tool_map.get(rel_id)
            if rel_tool:
                related_html += f'<a href="{BASE_URL}/tool/{rel_tool["slug"]}/" class="filter-chip" style="margin-right: 0.5rem; margin-bottom: 0.5rem;">{escape(rel_tool["name"])} &rarr;</a>'

        platforms_html = "".join([f'<span class="tool-tag" style="text-transform: capitalize;">{escape(p)}</span>' for p in tool.get("platforms", [])])

        tool_content = f"""
        <div class="detail-header">
          <div class="container">
            <nav class="breadcrumbs" aria-label="Breadcrumb">
              <a href="{BASE_URL}/">Home</a> &rsaquo;
              <a href="{BASE_URL}/tools/">Tools</a> &rsaquo;
              <a href="{BASE_URL}/category/{primary_cat['slug']}/">{escape(primary_cat['name'])}</a> &rsaquo;
              <span>{escape(tool['name'])}</span>
            </nav>

            <div style="display: flex; align-items: flex-start; gap: 1.5rem; flex-wrap: wrap;">
              <div class="tool-monogram" style="width: 4.5rem; height: 4.5rem; font-size: 2rem;">{escape(initial)}</div>
              <div style="flex: 1; min-width: 280px;">
                <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                  <h1 style="font-size: 2.25rem; font-weight: 800; letter-spacing: -0.02em;">{escape(tool['name'])}</h1>
                  <span class="verified-badge" style="font-size: 1.25rem;" title="Factually Verified">&#x2714; Verified</span>
                  <span class="badge {badge_class}" style="font-size: 0.875rem;">{escape(pricing)}</span>
                  {f'<span class="badge badge-oss">Open Source</span>' if tool.get('isOpenSource') else ''}
                </div>
                <p style="font-size: 1.15rem; color: var(--text-secondary); margin-top: 0.5rem; max-width: 800px;">
                  {escape(tool['shortDescription'])}
                </p>
              </div>
              <div style="display: flex; gap: 0.75rem; align-items: center;">
                <a href="{escape(tool['websiteUrl'])}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                  Visit Official Website &UpperRightArrow;
                </a>
              </div>
            </div>
          </div>
        </div>

        <div class="container" style="padding-bottom: 4rem;">
          <div class="detail-main-layout">
            <!-- Left Main Column -->
            <div>
              <div class="detail-content-box">
                <h2>About {escape(tool['name'])}</h2>
                <p style="font-size: 1.05rem; line-height: 1.7; color: var(--text-secondary); margin-bottom: 1.5rem;">
                  {escape(tool['description'])}
                </p>

                {f'''<h3 style="font-size: 1.1rem; margin: 1.5rem 0 0.75rem;">Key Capabilities & Features</h3>
                <ul class="feature-list" style="margin-bottom: 1.75rem;">
                  {features_html}
                </ul>''' if features_html else ''}

                {f'''<h3 style="font-size: 1.1rem; margin: 1.5rem 0 0.75rem;">Recommended Use Cases</h3>
                <ul class="feature-list" style="margin-bottom: 1.75rem;">
                  {use_cases_html}
                </ul>''' if use_cases_html else ''}

                {f'''<h3 style="font-size: 1.1rem; margin: 1.5rem 0 0.75rem; color: #ef4444;">Known Limitations</h3>
                <ul class="feature-list">
                  {limitations_html}
                </ul>''' if limitations_html else ''}
              </div>

              <!-- Alternatives & Related Tools -->
              <div class="detail-content-box">
                <h2>Alternatives & Related Tools</h2>
                <div style="margin-bottom: 1.25rem;">
                  <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.5rem;">Direct Alternatives</div>
                  <div style="display: flex; flex-wrap: wrap;">{alternatives_html or '<span style="color: var(--text-muted);">No direct alternatives listed.</span>'}</div>
                </div>
                <div>
                  <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.5rem;">Complementary Tools</div>
                  <div style="display: flex; flex-wrap: wrap;">{related_html or '<span style="color: var(--text-muted);">No complementary tools listed.</span>'}</div>
                </div>
              </div>
            </div>

            <!-- Right Sidebar Meta -->
            <aside>
              <div class="sidebar-card">
                <h3 style="font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem;">Pricing & Model</h3>
                <div style="margin-bottom: 1rem;">
                  <span class="badge {badge_class}" style="font-size: 0.9rem; padding: 0.35rem 0.75rem;">{escape(pricing)}</span>
                </div>
                {f'<p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1rem;">{escape(pricing_details)}</p>' if pricing_details else ''}
                <div style="font-size: 0.8125rem; color: var(--text-muted);">
                  Verified: {escape(tool.get('lastVerifiedAt', 'Recently'))}
                </div>
              </div>

              <div class="sidebar-card">
                <h3 style="font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem;">Platforms Supported</h3>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem;">
                  {platforms_html}
                </div>

                <h3 style="font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">Account Requirement</h3>
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
                  {'Account Required' if tool.get('accountRequired') is True else ('No Account Required' if tool.get('accountRequired') is False else 'Unspecified')}
                </div>

                {f'''<a href="{escape(tool.get('sourceCodeUrl'))}" target="_blank" rel="noopener noreferrer" class="btn" style="background: var(--bg-tertiary); width: 100%; border: 1px solid var(--border-color); font-size: 0.875rem; margin-bottom: 1rem;">
                  View Source Code &UpperRightArrow;
                </a>''' if tool.get('sourceCodeUrl') else ''}

                <a href="{escape(tool['websiteUrl'])}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-block">
                  Open Official Site &UpperRightArrow;
                </a>
              </div>
            </aside>
          </div>
        </div>
        """

        tool_sd = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": tool["name"],
            "description": tool["shortDescription"],
            "url": tool["websiteUrl"],
            "applicationCategory": primary_cat["name"],
            "operatingSystem": ", ".join(tool.get("platforms", [])),
            "offers": {
                "@type": "Offer",
                "price": "0" if pricing in ("free", "open-source") else None,
                "priceCurrency": "USD",
                "category": pricing
            }
        }

        page_title = tool.get("seo", {}).get("title") or f"{tool['name']} — AI Tool Review, Features & Pricing"
        page_desc = tool.get("seo", {}).get("description") or tool["shortDescription"]
        write_page(f"tool/{slug}/index.html", render_page(page_title, page_desc, tool_content, f"/tool/{slug}/", tool_sd))
        sitemap_urls.append((f"/tool/{slug}/", "0.8", "weekly"))

    # 4. Category Pages (/category/<slug>/index.html)
    for cat in categories:
        cat_id = cat["id"]
        cat_tools = [t for t in tools if cat_id in t.get("categories", [])]
        
        subcats_html = ""
        if cat.get("subcategories"):
            subcats_html = f"""
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1.25rem;">
              {"".join([f'<span class="filter-chip">{escape(s["name"])}</span>' for s in cat["subcategories"]])}
            </div>"""

        cat_content = f"""
        <div class="container" style="padding: 3rem 1.5rem 4rem;">
          <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="{BASE_URL}/">Home</a> &rsaquo;
            <a href="{BASE_URL}/tools/">Categories</a> &rsaquo;
            <span>{escape(cat['name'])}</span>
          </nav>

          <div style="margin-bottom: 2.5rem; max-width: 840px;">
            <h1 class="section-title" style="font-size: 2.25rem; margin-bottom: 0.75rem;">{escape(cat['name'])}</h1>
            <p style="font-size: 1.15rem; color: var(--text-secondary); line-height: 1.6;">
              {escape(cat['description'])}
            </p>
            {subcats_html}
          </div>

          <div style="font-size: 0.9375rem; color: var(--text-muted); margin-bottom: 1.5rem; font-weight: 600;">
            {len(cat_tools)} verified AI tools in this category
          </div>

          <div class="grid-tools">
            {"".join([render_tool_card(t) for t in cat_tools])}
          </div>
        </div>
        """

        cat_sd = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{cat['name']} — AI Tools",
            "description": cat["shortDescription"],
            "url": f"{BASE_URL}/category/{cat['slug']}/"
        }

        write_page(f"category/{cat['slug']}/index.html", render_page(f"{cat['name']} AI Tools", cat["shortDescription"], cat_content, f"/category/{cat['slug']}/", cat_sd))
        sitemap_urls.append((f"/category/{cat['slug']}/", "0.8", "weekly"))

    # 5. Collections Pages (/collections/index.html & /collection/<slug>/index.html)
    cols_index_content = f"""
    <div class="container" style="padding: 3rem 1.5rem 4rem;">
      <div style="margin-bottom: 2.5rem;">
        <h1 class="section-title" style="font-size: 2.25rem;">Curated AI Collections</h1>
        <p class="section-desc">Hand-crafted toolsets assembled by our editorial team for specific goals and technical environments.</p>
      </div>
      <div class="grid-collections">
        {"".join([f'''
        <a href="{BASE_URL}/collection/{col['slug']}/" class="collection-card">
          <div style="color: var(--brand-primary); font-size: 1.75rem; margin-bottom: 0.75rem;">&#9733;</div>
          <div class="collection-card-title">{escape(col['title'])}</div>
          <p class="collection-card-desc">{escape(col['description'])}</p>
          <div style="font-size: 0.8125rem; color: var(--brand-primary); font-weight: 600;">
            View {len(col['toolIds'])} Curated Tools &rarr;
          </div>
        </a>''' for col in collections])}
      </div>
    </div>
    """
    write_page("collections/index.html", render_page("Curated AI Tool Collections", "Explore expert-curated collections of AI tools.", cols_index_content, "/collections/", current_nav="collections"))
    sitemap_urls.append(("/collections/", "0.8", "weekly"))

    for col in collections:
        col_tools = [tool_map[tid] for tid in col["toolIds"] if tid in tool_map]
        col_detail_content = f"""
        <div class="container" style="padding: 3rem 1.5rem 4rem;">
          <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="{BASE_URL}/">Home</a> &rsaquo;
            <a href="{BASE_URL}/collections/">Collections</a> &rsaquo;
            <span>{escape(col['title'])}</span>
          </nav>

          <div style="margin-bottom: 2.5rem; max-width: 800px;">
            <h1 class="section-title" style="font-size: 2.25rem; margin-bottom: 0.75rem;">{escape(col['title'])}</h1>
            <p style="font-size: 1.15rem; color: var(--text-secondary); line-height: 1.6; margin-bottom: 1.5rem;">
              {escape(col['description'])}
            </p>
            <div style="background: var(--bg-card); border-left: 4px solid var(--brand-primary); padding: 1.25rem; border-radius: var(--radius-sm); font-size: 0.95rem; color: var(--text-secondary);">
              <strong>Curator Note:</strong> {escape(col['curatorNotes'])}
            </div>
          </div>

          <div class="grid-tools">
            {"".join([render_tool_card(t) for t in col_tools])}
          </div>
        </div>
        """
        write_page(f"collection/{col['slug']}/index.html", render_page(col["title"], col["description"], col_detail_content, f"/collection/{col['slug']}/"))
        sitemap_urls.append((f"/collection/{col['slug']}/", "0.7", "weekly"))

    # 6. Blog & Markdown Articles (/blog/index.html & /blog/<slug>/index.html)
    blog_dir = os.path.join(CONTENT_DIR, "blog")
    articles = []
    if os.path.exists(blog_dir):
        for fname in os.listdir(blog_dir):
            if fname.endswith(".md"):
                with open(os.path.join(blog_dir, fname), "r", encoding="utf-8") as bf:
                    raw = bf.read()
                meta, body = parse_frontmatter(raw)
                meta["body"] = body
                meta["filename"] = fname
                articles.append(meta)

    # Sort articles newest first
    articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    blog_index_cards = "".join([f"""
    <article class="collection-card" style="padding: 2rem;">
      <div style="font-size: 0.8125rem; color: var(--text-muted); margin-bottom: 0.5rem;">{escape(a.get('publishedAt', '2026-10-15'))} &bull; {escape(a.get('author', 'Editorial Staff'))}</div>
      <h2 style="font-size: 1.35rem; font-weight: 700; margin-bottom: 0.75rem;">
        <a href="{BASE_URL}/blog/{a['slug']}/" style="color: var(--text-primary);">{escape(a['title'])}</a>
      </h2>
      <p style="font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 1.25rem; line-height: 1.6; flex: 1;">
        {escape(a.get('description', ''))}
      </p>
      <a href="{BASE_URL}/blog/{a['slug']}/" class="view-all-link">Read Full Guide &rarr;</a>
    </article>""" for a in articles])

    blog_index_content = f"""
    <div class="container" style="padding: 3rem 1.5rem 4rem;">
      <div style="margin-bottom: 2.5rem;">
        <h1 class="section-title" style="font-size: 2.25rem;">AI Guides, Benchmarks & Tutorials</h1>
        <p class="section-desc">Practical workflows, tool comparisons, and guides for developers and knowledge workers.</p>
      </div>
      <div class="grid-collections">
        {blog_index_cards}
      </div>
    </div>
    """
    write_page("blog/index.html", render_page("AI Guides & Tutorials", "Read practical guides and benchmarks on artificial intelligence tools.", blog_index_content, "/blog/", current_nav="blog"))
    sitemap_urls.append(("/blog/", "0.8", "weekly"))

    for a in articles:
        html_body = parse_markdown(a["body"])
        article_content = f"""
        <article class="article-container">
          <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="{BASE_URL}/">Home</a> &rsaquo;
            <a href="{BASE_URL}/blog/">Blog</a> &rsaquo;
            <span>{escape(a['title'])}</span>
          </nav>

          <header class="article-header">
            <div class="article-meta">
              <span>Published {escape(a.get('publishedAt', ''))}</span>
              <span>&bull;</span>
              <span>By {escape(a.get('author', 'Editorial Staff'))}</span>
            </div>
          </header>

          <div class="prose">
            {html_body}
          </div>
        </article>
        """
        article_sd = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": a["title"],
            "description": a.get("description", ""),
            "author": {"@type": "Organization", "name": a.get("author", "AI Tools Directory")},
            "datePublished": a.get("publishedAt", ""),
            "dateModified": a.get("updatedAt", a.get("publishedAt", ""))
        }
        write_page(f"blog/{a['slug']}/index.html", render_page(a["title"], a.get("description", ""), article_content, f"/blog/{a['slug']}/", article_sd, "blog"))
        sitemap_urls.append((f"/blog/{a['slug']}/", "0.7", "monthly"))

    # 7. Static Pages: About, Contact, Privacy, Terms, 404
    about_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">About AI Tools Directory</h1>
      <div class="prose">
        <p>The <strong>AI Tools Directory</strong> is a free, transparent, and independent directory created to help developers, designers, students, and businesses discover and compare artificial intelligence tools.</p>
        
        <h2>Zero Infrastructure Cost & Open Architecture</h2>
        <p>Unlike commercial directories that charge developers thousands of dollars for "sponsored placement" or hide tools behind paywalls, AI Tools Directory runs on a <strong>100% free, static architecture</strong>:</p>
        <ul>
          <li><strong>Single Source of Truth</strong>: Version-controlled JSON files with automated schema validation.</li>
          <li><strong>GitHub Pages Hosting</strong>: Free static HTML and JSON distribution with global CDN caching.</li>
          <li><strong>Client-Side Autonomy</strong>: Full search and discovery runs in-memory without expensive backend servers or tracking cookies.</li>
        </ul>

        <h2>Fact Verification Standard</h2>
        <p>Every tool listing in our catalog is verified by an editor. We verify official pricing, open-source repository licenses, and platform availability directly from primary sources before publishing.</p>
      </div>
    </div>
    """
    write_page("about/index.html", render_page("About AI Tools Directory", "Learn about the mission and zero-cost static architecture of AI Tools Directory.", about_content, "/about/", current_nav="about"))
    sitemap_urls.append(("/about/", "0.5", "monthly"))

    contact_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Contact & Feedback</h1>
      <div class="prose">
        <p>We welcome submissions, bug reports, and corrections from the community.</p>

        <h2>Submitting a New AI Tool</h2>
        <p>To request a listing for your tool or report outdated pricing:</p>
        <ol>
          <li>Ensure your tool satisfies our <a href="{BASE_URL}/about/">editorial guidelines</a>.</li>
          <li>Submit a pull request to the open-source database repository.</li>
          <li>Our automated test suite will validate the schema and referential integrity before review.</li>
        </ol>

        <h2>Reporting Inaccuracies</h2>
        <p>AI pricing and terms change quickly. If you discover a discrepancy in any record, please file an issue with the link to the official pricing page.</p>
      </div>
    </div>
    """
    write_page("contact/index.html", render_page("Contact & Feedback", "Submit AI tools or contact the directory maintainers.", contact_content, "/contact/"))
    sitemap_urls.append(("/contact/", "0.5", "monthly"))

    privacy_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Privacy Policy</h1>
      <div class="prose">
        <p>Last updated: October 15, 2026</p>
        <h2>Zero Tracking & Data Sovereignty</h2>
        <p>AI Tools Directory is committed to maximum user privacy:</p>
        <ul>
          <li><strong>No Tracking Cookies</strong>: We do not use third-party advertising cookies or trackers.</li>
          <li><strong>Local Browser Storage</strong>: The only data stored in your browser is your dark/light theme preference (<code>ai_tools_dir_theme</code>) in <code>localStorage</code>.</li>
          <li><strong>Client-Side Search</strong>: Search queries remain 100% in your browser and are never transmitted to external query logging endpoints.</li>
        </ul>
      </div>
    </div>
    """
    write_page("privacy/index.html", render_page("Privacy Policy", "AI Tools Directory privacy statement. Zero tracking cookies.", privacy_content, "/privacy/"))
    sitemap_urls.append(("/privacy/", "0.3", "yearly"))

    terms_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Terms of Use</h1>
      <div class="prose">
        <p>Last updated: October 15, 2026</p>
        <h2>Directory Information Disclaimer</h2>
        <p>The information provided on AI Tools Directory is for general educational and discovery purposes only. Product names, logos, and brands are property of their respective owners. Listing does not imply affiliation or endorsement.</p>
        <h2>External Links</h2>
        <p>Our website and mobile app contain links to external third-party websites. We have no control over the privacy practices or contents of those external sites.</p>
      </div>
    </div>
    """
    write_page("terms/index.html", render_page("Terms of Use", "AI Tools Directory terms of use and editorial disclaimer.", terms_content, "/terms/"))
    sitemap_urls.append(("/terms/", "0.3", "yearly"))

    error_content = f"""
    <div class="article-container" style="text-align: center; padding: 5rem 1.5rem;">
      <h1 style="font-size: 5rem; font-weight: 800; color: var(--brand-primary); margin-bottom: 0.5rem;">404</h1>
      <h2 style="font-size: 1.75rem; margin-bottom: 1rem;">Page Not Found</h2>
      <p style="color: var(--text-secondary); max-width: 500px; margin: 0 auto 2rem;">
        The requested page could not be located. It may have been moved or updated.
      </p>
      <a href="{BASE_URL}/" class="btn btn-primary">Return to Directory Homepage</a>
    </div>
    """
    write_page("404.html", render_page("Page Not Found (404)", "The requested page was not found.", error_content, "/404.html"))

    # 8. Sitemap and Robots
    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    for path, priority, freq in sitemap_urls:
        full_url = f"https://in-ni18.github.io/ai-tools-directory{path}"
        sitemap_xml.append(f"""  <url>
    <loc>{full_url}</loc>
    <lastmod>{today_str}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>""")
    sitemap_xml.append('</urlset>')

    with open(os.path.join(DIST_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_xml))

    with open(os.path.join(DIST_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: https://in-ni18.github.io/ai-tools-directory/sitemap.xml\n")

    print(f"[SUCCESS] Website build complete at {DIST_DIR}!")
    print(f"  Indexed routes generated: {len(sitemap_urls)}")

def write_page(rel_path, html_str):
    out_path = os.path.join(DIST_DIR, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)

if __name__ == "__main__":
    build_site()
