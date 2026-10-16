"""
Zero-dependency static site generator for AI Tools Directory.
Generates fully-static, SEO-optimized HTML for GitHub Pages and custom domains.
Features:
- Dynamic relative path resolution (zero 404s on GitHub Pages project subpaths or root domains)
- Rich Markdown engine (tables, code copy, callouts, anchor headings)
- Schema.org Structured Data (WebSite, SoftwareApplication, CollectionPage, BlogPosting, BreadcrumbList, FAQPage)
- Dynamic synchronization with master database folder and mobile app
"""

import datetime
import html
import json
import os
import re
import shutil
import subprocess
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
SITE_DESCRIPTION = "The premier independent directory of verified artificial intelligence software, open-source models, and developer companions. 100% verified facts, zero sponsored bias."
CANONICAL_HOST = os.environ.get("CANONICAL_HOST", "https://nitinkanade.github.io/ai-tools-directory-website")

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

# Advanced Markdown to HTML parser (Headings, Tables, Lists, Code with copy, Callouts, Blockquotes, Links, Bold)
def parse_markdown(md_text, rel_base="."):
    lines = md_text.strip().split("\n")
    html_lines = []
    in_list = False
    in_ordered_list = False
    in_code_block = False
    code_lang = ""
    code_content = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # Code block handling
        if stripped.startswith("```"):
            if in_code_block:
                escaped_code = escape("\n".join(code_content))
                html_lines.append(f"""
                <div class="code-block-container">
                  <div class="code-block-header">
                    <span class="code-lang">{escape(code_lang or 'text')}</span>
                    <button class="copy-btn" onclick="copyCode(this)" aria-label="Copy code">Copy</button>
                  </div>
                  <pre><code class="language-{escape(code_lang)}">{escaped_code}</code></pre>
                </div>
                """)
                in_code_block = False
                code_lang = ""
                code_content = []
            else:
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_content = []
            continue

        if in_code_block:
            code_content.append(line)
            continue

        # Table handling
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_rows.append(stripped)
            continue
        elif in_table:
            # End of table, render table
            html_lines.append(render_table(table_rows, rel_base))
            in_table = False
            table_rows = []

        # Close lists if leaving list line
        if in_list and not (stripped.startswith("- ") or stripped.startswith("* ")):
            html_lines.append("</ul>")
            in_list = False

        if in_ordered_list and not re.match(r"^\d+\.\s", stripped):
            html_lines.append("</ol>")
            in_ordered_list = False

        if not stripped:
            continue

        # Headings
        if stripped.startswith("#### "):
            h_text = stripped[5:]
            h_id = re.sub(r'[^a-zA-Z0-9]+', '-', h_text.lower()).strip('-')
            html_lines.append(f'<h4 id="{h_id}">{format_inline(h_text, rel_base)}</h4>')
        elif stripped.startswith("### "):
            h_text = stripped[4:]
            h_id = re.sub(r'[^a-zA-Z0-9]+', '-', h_text.lower()).strip('-')
            html_lines.append(f'<h3 id="{h_id}">{format_inline(h_text, rel_base)}</h3>')
        elif stripped.startswith("## "):
            h_text = stripped[3:]
            h_id = re.sub(r'[^a-zA-Z0-9]+', '-', h_text.lower()).strip('-')
            html_lines.append(f'<h2 id="{h_id}">{format_inline(h_text, rel_base)}</h2>')
        elif stripped.startswith("# "):
            h_text = stripped[2:]
            h_id = re.sub(r'[^a-zA-Z0-9]+', '-', h_text.lower()).strip('-')
            html_lines.append(f'<h1 id="{h_id}">{format_inline(h_text, rel_base)}</h1>')
        # Callouts & Blockquotes
        elif stripped.startswith("> [!NOTE]"):
            html_lines.append('<div class="callout callout-note"><strong>Note:</strong> ')
        elif stripped.startswith("> [!TIP]"):
            html_lines.append('<div class="callout callout-tip"><strong>Tip:</strong> ')
        elif stripped.startswith("> [!WARNING]"):
            html_lines.append('<div class="callout callout-warning"><strong>Warning:</strong> ')
        elif stripped.startswith("> "):
            html_lines.append(f'<blockquote><p>{format_inline(stripped[2:], rel_base)}</p></blockquote>')
        # Horizontal Rule
        elif stripped in ("---", "***", "___"):
            html_lines.append("<hr style='margin: 2.5rem 0; border: none; border-top: 1px solid var(--border-color);'>")
        # Unordered list
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{format_inline(stripped[2:], rel_base)}</li>")
        # Ordered list
        elif re.match(r"^\d+\.\s", stripped):
            if not in_ordered_list:
                html_lines.append("<ol>")
                in_ordered_list = True
            content = re.sub(r"^\d+\.\s", "", stripped)
            html_lines.append(f"<li>{format_inline(content, rel_base)}</li>")
        else:
            html_lines.append(f"<p>{format_inline(stripped, rel_base)}</p>")

    if in_table and table_rows:
        html_lines.append(render_table(table_rows, rel_base))
    if in_list:
        html_lines.append("</ul>")
    if in_ordered_list:
        html_lines.append("</ol>")

    return "\n".join(html_lines)

def render_table(rows, rel_base):
    if len(rows) < 2:
        return ""
    
    header_cells = [c.strip() for c in rows[0].strip("|").split("|")]
    header_html = "".join([f"<th>{format_inline(c, rel_base)}</th>" for c in header_cells])

    body_html = []
    # Skip row 1 if it's separator |---|---|
    data_rows = rows[2:] if re.match(r"^\|?[\s\-:|]+\|?$", rows[1]) else rows[1:]

    for r in data_rows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        # Pad cells if row length differs
        while len(cells) < len(header_cells):
            cells.append("")
        row_tds = "".join([f"<td>{format_inline(cells[i], rel_base)}</td>" for i in range(len(header_cells))])
        body_html.append(f"<tr>{row_tds}</tr>")

    return f"""
    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>{header_html}</tr>
        </thead>
        <tbody>
          {"".join(body_html)}
        </tbody>
      </table>
    </div>
    """

def format_inline(text, rel_base="."):
    # Rewriting internal root links [text](/tool/xyz/) to [text]({rel_base}/tool/xyz/)
    def link_repl(match):
        label = match.group(1)
        url = match.group(2)
        if url.startswith("/") and not url.startswith("//"):
            url = f"{rel_base}{url}"
        return f'<a href="{escape(url)}">{label}</a>'

    # Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" class="article-embedded-img" loading="lazy">', text)
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link_repl, text)
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
                items = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
                meta[key] = items
            elif val.lower() == "true":
                meta[key] = True
            elif val.lower() == "false":
                meta[key] = False
            else:
                meta[key] = val.strip('"').strip("'")
    return meta, parts[2].strip()

# Base layout shell generator with dynamic relative base resolution
def render_page(title, meta_desc, content, canonical_path="", structured_data=None, current_nav="", rel_base="."):
    canonical_url = f"{CANONICAL_HOST}{canonical_path}"
    og_title = f"{title} | {SITE_TITLE}" if title != SITE_TITLE else f"{SITE_TITLE} — {SITE_TAGLINE}"

    sd_tag = ""
    if structured_data:
        sd_tag = f'<script type="application/ld+json">{json.dumps(structured_data, ensure_ascii=False)}</script>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(og_title)}</title>
  <meta name="description" content="{escape(meta_desc)}">
  <link rel="canonical" href="{escape(canonical_url)}">
  <meta name="robots" content="index, follow">
  
  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="{escape(canonical_url)}">
  <meta property="og:title" content="{escape(og_title)}">
  <meta property="og:description" content="{escape(meta_desc)}">
  <meta property="og:site_name" content="{escape(SITE_TITLE)}">
  <meta property="og:image" content="{CANONICAL_HOST}/static/img/playstore-icon.png">
  
  <!-- Twitter Cards -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:url" content="{escape(canonical_url)}">
  <meta name="twitter:title" content="{escape(og_title)}">
  <meta name="twitter:description" content="{escape(meta_desc)}">
  <meta name="twitter:image" content="{CANONICAL_HOST}/static/img/playstore-icon.png">

  <!-- Favicons & Brand Icons -->
  <link rel="icon" type="image/x-icon" href="{rel_base}/static/img/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="{rel_base}/static/img/favicon-32x32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="{rel_base}/static/img/apple-touch-icon.png">

  <!-- Fonts & Styling -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{rel_base}/static/css/styles.css">
  
  <!-- Schema.org Structured Data -->
  {sd_tag}

  <script>
    // Zero-flicker theme initialization
    (function() {{
      const saved = localStorage.getItem('ai_tools_dir_theme');
      if (saved) {{
        document.documentElement.setAttribute('data-theme', saved);
      }}
    }})();
  </script>
</head>
<body>
  <!-- Global Navigation Header -->
  <header class="site-header">
    <div class="container nav-container">
      <a href="{rel_base}/" class="brand-logo" aria-label="AI Tools Directory Homepage">
        <img src="{rel_base}/static/img/logo.png" alt="AI Tools Directory Logo" class="brand-icon-img" width="38" height="38">
        <span class="brand-title">AI Tools Directory</span>
        <span class="brand-badge">v1.0 Verified</span>
      </a>

      <nav aria-label="Main navigation" class="desktop-nav">
        <ul class="nav-links">
          <li><a href="{rel_base}/" class="nav-link {'active' if current_nav == 'home' else ''}">Home</a></li>
          <li><a href="{rel_base}/tools/" class="nav-link {'active' if current_nav == 'tools' else ''}">Directory</a></li>
          <li><a href="{rel_base}/collections/" class="nav-link {'active' if current_nav == 'collections' else ''}">Collections</a></li>
          <li><a href="{rel_base}/blog/" class="nav-link {'active' if current_nav == 'blog' else ''}">Guides & Blog</a></li>
          <li><a href="{rel_base}/about/" class="nav-link {'active' if current_nav == 'about' else ''}">About</a></li>
        </ul>
      </nav>

      <div class="header-actions">
        <!-- Universal Spotlight Trigger -->
        <button id="quick-search-trigger" class="quick-search-trigger" onclick="openSpotlight()" aria-label="Quick Search" title="Search all tools (Ctrl+K)">
          <svg class="search-btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <span class="search-trigger-text">Search...</span>
          <span class="kbd-shortcut">Ctrl+K</span>
        </button>

        <button class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle Theme" title="Toggle Dark/Light Mode">
          <svg class="theme-moon-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>

        <button id="mobile-hamburger-btn" class="mobile-menu-btn" onclick="toggleMobileMenu()" aria-label="Open navigation menu" aria-expanded="false">
          <span class="hamburger-bar"></span>
          <span class="hamburger-bar"></span>
          <span class="hamburger-bar"></span>
        </button>
      </div>
    </div>
  </header>

  <!-- Mobile Drawer -->
  <div id="mobile-drawer" class="mobile-drawer" role="dialog" aria-modal="true" aria-label="Mobile Navigation">
    <div class="mobile-drawer-backdrop" onclick="toggleMobileMenu()"></div>
    <div class="mobile-drawer-content">
      <div class="mobile-search-banner">
        <button class="mobile-search-btn" onclick="toggleMobileMenu(); openSpotlight();">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <span>Search 40+ AI tools...</span>
          <span class="kbd-shortcut">Ctrl+K</span>
        </button>
      </div>

      <ul class="mobile-nav-links">
        <li>
          <a href="{rel_base}/" class="mobile-nav-link {'active' if current_nav == 'home' else ''}" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#127968;</span>
            <span>Home</span>
          </a>
        </li>
        <li>
          <a href="{rel_base}/tools/" class="mobile-nav-link {'active' if current_nav == 'tools' else ''}" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#9889;</span>
            <span>All AI Tools</span>
            <span class="mobile-count-pill">40+</span>
          </a>
        </li>
        <li>
          <a href="{rel_base}/collections/" class="mobile-nav-link {'active' if current_nav == 'collections' else ''}" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#10024;</span>
            <span>Curated Collections</span>
          </a>
        </li>
        <li>
          <a href="{rel_base}/blog/" class="mobile-nav-link {'active' if current_nav == 'blog' else ''}" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#128218;</span>
            <span>Guides & Tutorials</span>
          </a>
        </li>
        <li>
          <a href="{rel_base}/about/" class="mobile-nav-link {'active' if current_nav == 'about' else ''}" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#8505;&#65039;</span>
            <span>About & Methodology</span>
          </a>
        </li>
        <li>
          <a href="{rel_base}/contact/" class="mobile-nav-link" onclick="toggleMobileMenu()">
            <span class="mobile-nav-icon">&#10133;</span>
            <span>Submit a Tool</span>
          </a>
        </li>
      </ul>

      <div class="mobile-drawer-categories">
        <div class="mobile-drawer-cat-title">Popular Categories</div>
        <div class="mobile-drawer-cat-pills">
          <a href="{rel_base}/category/coding-development/" class="cat-pill" onclick="toggleMobileMenu()">Coding & IDEs</a>
          <a href="{rel_base}/category/chatbots-assistants/" class="cat-pill" onclick="toggleMobileMenu()">Conversational LLMs</a>
          <a href="{rel_base}/category/image-generation/" class="cat-pill" onclick="toggleMobileMenu()">Image & Creative</a>
          <a href="{rel_base}/category/opensource-models-platforms/" class="cat-pill" onclick="toggleMobileMenu()">Open-Source AI</a>
        </div>
      </div>
    </div>
  </div>

  <!-- Universal Spotlight Search Modal -->
  <div id="spotlight-modal" class="spotlight-modal" style="display: none;" role="dialog" aria-modal="true" aria-label="Search AI Tools">
    <div class="spotlight-backdrop" onclick="closeSpotlight()"></div>
    <div class="spotlight-panel">
      <div class="spotlight-input-wrap">
        <svg class="spotlight-search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" id="spotlight-input" class="spotlight-input" placeholder="Type a tool name, coding, reasoning, pricing, or tag..." autocomplete="off">
        <button id="spotlight-clear-btn" class="spotlight-clear-btn" aria-label="Clear Search" onclick="clearSpotlightInput()">&times;</button>
        <button class="spotlight-close-btn" onclick="closeSpotlight()" aria-label="Close search">Esc</button>
      </div>

      <div id="spotlight-suggestions" class="spotlight-quick-tags">
        <span class="quick-tags-label">Quick:</span>
        <button class="spotlight-tag" onclick="setSpotlightQuery('coding')">Coding</button>
        <button class="spotlight-tag" onclick="setSpotlightQuery('chat')">Chatbots</button>
        <button class="spotlight-tag" onclick="setSpotlightQuery('image')">Image</button>
        <button class="spotlight-tag" onclick="setSpotlightQuery('open-source')">Open Source</button>
        <button class="spotlight-tag" onclick="setSpotlightQuery('free')">Free Tier</button>
      </div>

      <div id="spotlight-results" class="spotlight-results">
        <!-- Rendered dynamically by JS -->
      </div>

      <div class="spotlight-footer">
        <div class="spotlight-footer-shortcuts">
          <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> Navigate</span>
          <span><kbd>&crarr;</kbd> Select</span>
          <span><kbd>Esc</kbd> Close</span>
        </div>
        <a href="{rel_base}/tools/" class="spotlight-view-all">All Tools &rarr;</a>
      </div>
    </div>
  </div>

  <!-- Main Page Content -->
  <main id="main-content">
    {content}
  </main>

  <!-- Global Footer -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col">
          <div class="brand-logo" style="margin-bottom: 1.25rem;">
            <img src="{rel_base}/static/img/logo.png" alt="AI Tools Directory Logo" class="brand-icon-img" width="40" height="40">
            <span>AI Tools Directory</span>
          </div>
          <p style="font-size: 0.9375rem; color: var(--text-secondary); max-width: 320px; margin-bottom: 1.25rem; line-height: 1.6;">
            The premier independent, fact-checked directory of verified AI software, open models, and developer assistants.
          </p>
          <div style="font-size: 0.8125rem; color: var(--text-muted);">
            Zero sponsored bias. 100% verified facts.
          </div>
        </div>

        <div class="footer-col">
          <h4>Directory Index</h4>
          <ul class="footer-links">
            <li><a href="{rel_base}/tools/">Complete Directory</a></li>
            <li><a href="{rel_base}/collections/">Curated Collections</a></li>
            <li><a href="{rel_base}/category/coding-development/">Coding & Dev Tools</a></li>
            <li><a href="{rel_base}/category/chatbots-assistants/">Conversational LLMs</a></li>
            <li><a href="{rel_base}/category/opensource-models-platforms/">Open-Source AI</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Editorial & Guides</h4>
          <ul class="footer-links">
            <li><a href="{rel_base}/blog/">Guides & Tutorials</a></li>
            <li><a href="{rel_base}/blog/top-ai-coding-assistants-2026/">Top Coding Assistants 2026</a></li>
            <li><a href="{rel_base}/blog/running-open-source-llms-locally-with-ollama/">Running Local LLMs</a></li>
            <li><a href="{rel_base}/data/manifest.json">Static API Manifest</a></li>
            <li><a href="{rel_base}/sitemap.xml">XML Sitemap</a></li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Transparency</h4>
          <ul class="footer-links">
            <li><a href="{rel_base}/about/">About the Directory</a></li>
            <li><a href="{rel_base}/contact/">Submit a Tool</a></li>
            <li><a href="{rel_base}/privacy/">Privacy Policy</a></li>
            <li><a href="{rel_base}/terms/">Terms of Use</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <div>&copy; {datetime.datetime.now().year} AI Tools Directory. Built with zero-cost static architecture.</div>
        <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
          <span>Android App: <code>in.ni18.aitoolsdirectory</code></span>
          <span>Hosted on GitHub Pages</span>
        </div>
      </div>
    </div>
  </footer>

  <script>
    window.__SITE_BASE_URL__ = "{rel_base}";
  </script>
  <script src="{rel_base}/static/js/app.js"></script>
</body>
</html>"""

def get_tool_gradient(tool):
    cats = tool.get("categories", [])
    if "coding-development" in cats:
        return "linear-gradient(135deg, #0284c7 0%, #2563eb 100%)"
    if "chatbots-assistants" in cats:
        return "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)"
    if "image-generation" in cats or "design-ui-ux" in cats:
        return "linear-gradient(135deg, #db2777 0%, #e11d48 100%)"
    if "opensource-models-platforms" in cats:
        return "linear-gradient(135deg, #059669 0%, #0d9488 100%)"
    if "audio-music" in cats or "video-generation" in cats:
        return "linear-gradient(135deg, #d97706 0%, #ea580c 100%)"
    if "research-knowledge" in cats or "education-learning" in cats:
        return "linear-gradient(135deg, #4f46e5 0%, #0284c7 100%)"
    return "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)"

def render_tool_card(tool, rel_base="."):
    pricing = tool.get("pricing", {}).get("model", "freemium")
    badge_class = "badge-oss" if pricing == "open-source" else f"badge-{pricing}"
    initial = tool["name"][0].upper()
    gradient = get_tool_gradient(tool)

    tags_html = "".join([f'<span class="tool-tag">#{escape(t)}</span>' for t in tool.get("tags", [])[:3]])

    platforms_str = ", ".join([p.capitalize() for p in tool.get("platforms", [])[:3]])

    return f"""
    <div class="tool-card tool-card-item" 
         data-id="{escape(tool['id'])}"
         data-name="{escape(tool['name'].lower())}"
         data-slug="{escape(tool['slug'])}"
         data-desc="{escape(tool['shortDescription'].lower())}"
         data-categories="{escape(','.join(tool.get('categories', [])))}"
         data-tags="{escape(','.join(tool.get('tags', [])))}"
         data-pricing="{escape(pricing)}"
         data-platforms="{escape(','.join(tool.get('platforms', [])))}"
         data-oss="{str(tool.get('isOpenSource') is True).lower()}">
      <button class="card-fav-btn" data-tool-id="{escape(tool['id'])}" onclick="toggleFavorite(event, '{escape(tool['id'])}')" aria-label="Bookmark {escape(tool['name'])}" title="Save tool">
        <svg class="star-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>
      </button>
      <div class="card-header">
        <div class="tool-monogram" style="background: {gradient}; color: #ffffff;">{escape(initial)}</div>
        <div class="tool-header-content">
          <div class="tool-name-wrap">
            <a href="{rel_base}/tool/{tool['slug']}/" class="tool-title">{escape(tool['name'])}</a>
            <span class="verified-badge" title="Factually Verified by Editors">&#x2714;</span>
          </div>
          <div style="display: flex; gap: 0.4rem; align-items: center; margin-top: 0.35rem; flex-wrap: wrap;">
            <span class="badge {badge_class}">{escape(pricing)}</span>
            <span style="font-size: 0.75rem; color: var(--text-muted);">&bull; {escape(platforms_str)}</span>
          </div>
        </div>
      </div>
      <p class="tool-short-desc">{escape(tool['shortDescription'])}</p>
      <div class="tool-tags">{tags_html}</div>
      <div class="card-footer">
        <a href="{escape(tool['websiteUrl'])}" target="_blank" rel="noopener noreferrer" class="tool-visit-link" title="Visit official site for {escape(tool['name'])}">
          Visit &UpperRightArrow;
        </a>
        <a href="{rel_base}/tool/{tool['slug']}/" class="view-all-link" style="font-size: 0.8125rem;">Explore Tool &rarr;</a>
      </div>
    </div>"""

def generate_tool_faqs(tool, primary_cat_name):
    name = tool["name"]
    pricing = tool.get("pricing", {}).get("model", "freemium")
    details = tool.get("pricing", {}).get("details", "")
    platforms = ", ".join(tool.get("platforms", ["Web"]))
    is_oss = tool.get("isOpenSource", False)

    faqs = [
        {
            "question": f"Is {name} free or paid?",
            "answer": f"{name} uses a {pricing} model. {details if details else f'Please check the official {name} website for the latest pricing plans.'}"
        },
        {
            "question": f"What platforms does {name} support?",
            "answer": f"{name} is currently available on: {platforms}."
        },
        {
            "question": f"Is {name} open-source?",
            "answer": f"{'Yes, ' + name + ' is open-source. You can inspect its source code in its public repository.' if is_oss else 'No, ' + name + ' is proprietary software.'}"
        },
        {
            "question": f"What are the best alternatives to {name}?",
            "answer": f"Top alternatives in the {primary_cat_name} category include {', '.join(tool.get('alternatives', ['other curated tools in this directory']))}."
        }
    ]
    return faqs

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

    # 1. Homepage (rel_base = ".")
    featured_tools = [t for t in tools if t.get("isFeatured")]
    recent_tools = sorted(tools, key=lambda x: x.get("createdAt", ""), reverse=True)[:6]

    home_content = f"""
    <section class="hero-section">
      <div class="hero-glow-blob"></div>
      <div class="container hero-content-wrap">
        <div class="hero-badge">
          <span>&starf; 100% Independent &bull; 40+ Fact-Checked Tools &bull; Zero Sponsored Bias</span>
        </div>
        <h1 class="hero-title">
          Discover, Compare & Master <br><span class="text-gradient">the World's Best AI Tools</span>
        </h1>
        <p class="hero-subtitle">
          Curated, benchmarked, and fact-verified directory of artificial intelligence software, local runtimes, and developer assistants. Zero paywalls, zero sponsored rankings.
        </p>

        <!-- Live Instant Search -->
        <div class="search-container">
          <div class="search-input-wrapper">
            <span class="search-icon-prefix">&#128269;</span>
            <input type="text" id="home-search-input" class="search-input" placeholder="Search by name, category, coding, diffusion, reasoning, or tag..." autocomplete="off">
            <div class="search-right-actions">
              <button id="home-search-clear" class="search-clear-btn" aria-label="Clear Search">&times;</button>
              <span class="kbd-shortcut">Ctrl+K</span>
            </div>
          </div>
          <div id="home-search-dropdown" class="search-dropdown"></div>

          <!-- Quick category filter pills -->
          <div class="quick-pills-row">
            <button class="quick-pill" data-filter="">&bull; All Tools</button>
            <button class="quick-pill" data-filter="?category=coding-development">&#128187; Coding & IDEs</button>
            <button class="quick-pill" data-filter="?category=chatbots-assistants">&#128172; Conversational LLMs</button>
            <button class="quick-pill" data-filter="?category=image-generation">&#127912; Image & Creative</button>
            <button class="quick-pill" data-filter="?oss=true">&#128275; Open Source</button>
            <button class="quick-pill" data-filter="?pricing=free">&#127873; Free Tier</button>
            <button class="quick-pill" data-filter="?saved=true">&#9733; Saved Tools</button>
          </div>
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
            <span class="stat-label">Zero Sponsored Bias</span>
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
            <p class="section-desc">Hand-picked AI tools setting industry standards for performance, utility, and innovation.</p>
          </div>
          <a href="./tools/" class="view-all-link">Browse all {len(tools)} tools &rarr;</a>
        </div>
        <div class="grid-tools">
          {"".join([render_tool_card(t, rel_base=".") for t in featured_tools[:6]])}
        </div>
      </div>
    </section>

    <!-- Browse By Category -->
    <section class="section section-alt">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Explore by Category</h2>
            <p class="section-desc">Find specialized solutions tailored to your industry, engineering stack, or creative workflow.</p>
          </div>
        </div>
        <div class="grid-categories">
          {"".join([f'''
          <a href="./category/{c['slug']}/" class="category-card">
            <div class="category-card-icon">&#9670;</div>
            <div class="category-card-title">{escape(c['name'])}</div>
            <p style="font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.75rem; flex: 1; line-height: 1.5;">
              {escape(c['shortDescription'])}
            </p>
            <div class="category-card-count">Explore Category &rarr;</div>
          </a>''' for c in categories])}
        </div>
      </div>
    </section>

    <!-- Curated Collections -->
    <section class="section">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Curated Workflows & Collections</h2>
            <p class="section-desc">Focused toolsets grouped together for specific engineering goals and business operations.</p>
          </div>
          <a href="./collections/" class="view-all-link">View all collections &rarr;</a>
        </div>
        <div class="grid-collections">
          {"".join([f'''
          <a href="./collection/{col['slug']}/" class="collection-card">
            <div style="color: var(--brand-primary); font-size: 1.75rem; margin-bottom: 0.75rem;">&#9733;</div>
            <div class="collection-card-title">{escape(col['title'])}</div>
            <p class="collection-card-desc">{escape(col['description'])}</p>
            <div style="font-size: 0.875rem; color: var(--brand-primary); font-weight: 700;">
              {len(col['toolIds'])} Curated Tools &rarr;
            </div>
          </a>''' for col in collections[:3]])}
        </div>
      </div>
    </section>

    <!-- Recently Verified Tools -->
    <section class="section section-alt">
      <div class="container">
        <div class="section-header">
          <div>
            <h2 class="section-title">Recently Verified Additions</h2>
            <p class="section-desc">The latest verified tools added to the catalog by our editorial maintainers.</p>
          </div>
          <a href="./tools/" class="view-all-link">See full directory &rarr;</a>
        </div>
        <div class="grid-tools">
          {"".join([render_tool_card(t, rel_base=".") for t in recent_tools])}
        </div>
      </div>
    </section>

    <!-- Community Callout -->
    <section class="section" style="padding: 4rem 0;">
      <div class="container">
        <div style="background: var(--brand-gradient-subtle); border: 1px solid var(--border-color); border-radius: var(--radius-xl); padding: 3rem; text-align: center; max-width: 900px; margin: 0 auto;">
          <h2 style="font-size: 1.75rem; font-weight: 800; margin-bottom: 0.75rem;">Are You Building an AI Tool?</h2>
          <p style="color: var(--text-secondary); max-width: 600px; margin: 0 auto 1.5rem; line-height: 1.6;">
            We maintain an open-source, community-driven database. Submit your AI tool via a GitHub pull request. Zero listing fees, zero paid sponsorship bias.
          </p>
          <a href="./contact/" class="btn btn-primary">Submit Your Tool For Review &UpperRightArrow;</a>
        </div>
      </div>
    </section>
    """

    home_sd = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_TITLE,
        "description": SITE_DESCRIPTION,
        "url": CANONICAL_HOST,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{CANONICAL_HOST}/tools/?q={{search_term_string}}",
            "query-input": "required name=search_term_string"
        }
    }

    write_page("index.html", render_page(SITE_TITLE, SITE_DESCRIPTION, home_content, "/", home_sd, "home", rel_base="."))
    sitemap_urls.append(("/", "1.0", "daily"))

    # 2. Directory Page (/tools/index.html - rel_base = "..")
    dir_content = f"""
    <div class="container" style="padding: 3rem 1.5rem 5rem;">
      <div style="margin-bottom: 2.5rem;">
        <h1 class="section-title" style="font-size: 2.5rem;">Complete AI Tools Directory</h1>
        <p class="section-desc">Search, filter, and compare {len(tools)} factually verified artificial intelligence tools across categories and pricing models.</p>
      </div>

      <div class="directory-layout">
        <!-- Interactive Filter Sidebar (Desktop) -->
        <aside class="filter-sidebar">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <span style="font-weight: 800; font-size: 1.1rem; font-family: var(--font-display);">Filter Tools</span>
            <button onclick="clearAllFilters()" style="background: none; border: none; color: var(--brand-primary); font-size: 0.8125rem; font-weight: 700; cursor: pointer;">Reset All</button>
          </div>

          <!-- Saved Tools Switch -->
          <div class="filter-group">
            <label class="filter-label" style="font-weight: 700; color: var(--text-primary);">
              <span class="filter-label-inner">
                <input type="checkbox" id="filter-saved-only" class="filter-saved-checkbox">
                <span>&#9733; Saved Tools Only</span>
              </span>
              <span id="saved-count-badge" class="filter-count-badge">0</span>
            </label>
          </div>

          <!-- Open Source Switch -->
          <div class="filter-group">
            <label class="filter-label" style="font-weight: 700; color: var(--text-primary);">
              <span class="filter-label-inner">
                <input type="checkbox" id="filter-oss-only" class="filter-oss-checkbox">
                <span>Open Source Only</span>
              </span>
              <span class="badge badge-oss">OSS</span>
            </label>
          </div>

          <!-- Pricing Models -->
          <div class="filter-group">
            <div class="filter-title">Pricing Model</div>
            <div class="filter-options">
              <label class="filter-label">
                <span class="filter-label-inner">
                  <input type="checkbox" class="filter-pricing-checkbox" value="free"> Free
                </span>
                <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'free'])}</span>
              </label>
              <label class="filter-label">
                <span class="filter-label-inner">
                  <input type="checkbox" class="filter-pricing-checkbox" value="freemium"> Freemium
                </span>
                <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'freemium'])}</span>
              </label>
              <label class="filter-label">
                <span class="filter-label-inner">
                  <input type="checkbox" class="filter-pricing-checkbox" value="paid"> Paid
                </span>
                <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'paid'])}</span>
              </label>
              <label class="filter-label">
                <span class="filter-label-inner">
                  <input type="checkbox" class="filter-pricing-checkbox" value="open-source"> Open Source
                </span>
                <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'open-source'])}</span>
              </label>
            </div>
          </div>

          <!-- Platforms -->
          <div class="filter-group">
            <div class="filter-title">Platform Support</div>
            <div class="filter-options">
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="web"> Web Browser</span></label>
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="windows"> Windows</span></label>
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="macos"> macOS</span></label>
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="linux"> Linux</span></label>
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="android"> Android</span></label>
              <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="ios"> iOS</span></label>
            </div>
          </div>

          <!-- Categories -->
          <div class="filter-group">
            <div class="filter-title">Categories ({len(categories)})</div>
            <div class="filter-options" style="max-height: 280px; overflow-y: auto; padding-right: 0.35rem;">
              {"".join([f'<label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-category-checkbox" value="{c["id"]}"> {escape(c["name"])}</span></label>' for c in categories])}
            </div>
          </div>
        </aside>

        <!-- Main Directory Listing -->
        <section style="min-width: 0;">
          <!-- Mobile Controls Bar (< 992px) -->
          <div class="mobile-directory-controls">
            <button id="mobile-filter-trigger" class="mobile-filter-btn" onclick="toggleMobileFilterDrawer()" aria-label="Open Filter Drawer">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
              </svg>
              <span>Filter Tools</span>
              <span id="mobile-filter-badge" class="filter-count-badge" style="display: none;">0</span>
            </button>
            <div class="mobile-sort-wrap">
              <select id="mobile-directory-sort-select" onchange="syncDirectorySort(this.value)" class="sort-select">
                <option value="featured">Featured First</option>
                <option value="name-asc">Alphabetical (A-Z)</option>
                <option value="name-desc">Alphabetical (Z-A)</option>
              </select>
            </div>
          </div>

          <!-- Search input bar & Desktop Sort dropdown -->
          <div class="directory-search-bar-wrap">
            <div class="search-input-wrapper" style="flex: 1; min-width: 240px;">
              <span class="search-icon-prefix">&#128269;</span>
              <input type="text" id="directory-search-input" class="search-input" placeholder="Search by name, feature, category, or task..." style="height: 3.5rem; font-size: 1rem;">
              <button id="directory-search-clear" class="search-clear-btn" aria-label="Clear Search" onclick="clearDirectorySearch()">&times;</button>
            </div>
            <div class="desktop-sort-wrap" style="display: flex; align-items: center; gap: 0.5rem;">
              <label for="directory-sort-select" style="font-size: 0.875rem; font-weight: 600; color: var(--text-muted); white-space: nowrap;">Sort by:</label>
              <select id="directory-sort-select" onchange="syncDirectorySort(this.value)" class="sort-select">
                <option value="featured">Featured First</option>
                <option value="name-asc">Alphabetical (A-Z)</option>
                <option value="name-desc">Alphabetical (Z-A)</option>
              </select>
            </div>
          </div>

          <!-- Active Filter Chips -->
          <div id="active-filter-chips" class="active-filter-chips"></div>

          <!-- Results Header -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 0.5rem;">
            <span id="directory-result-count" style="font-size: 0.9375rem; color: var(--text-muted); font-weight: 600;">
              Showing all {len(tools)} tools
            </span>
          </div>

          <!-- Directory Cards Grid -->
          <div id="directory-cards-container" class="grid-tools">
            {"".join([render_tool_card(t, rel_base="..") for t in tools])}
          </div>
        </section>
      </div>

      <!-- Mobile Filter Drawer Modal (< 992px) -->
      <div id="mobile-filter-drawer" class="mobile-filter-drawer" style="display: none;" role="dialog" aria-modal="true" aria-label="Filter Options">
        <div class="mobile-filter-backdrop" onclick="toggleMobileFilterDrawer()"></div>
        <div class="mobile-filter-panel">
          <div class="mobile-filter-header">
            <h3>Filter AI Tools</h3>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
              <button onclick="clearAllFilters()" class="text-btn">Reset All</button>
              <button class="filter-close-btn" onclick="toggleMobileFilterDrawer()" aria-label="Close filters">&times;</button>
            </div>
          </div>
          <div class="mobile-filter-body">
            <!-- Saved Tools Switch -->
            <div class="filter-group">
              <label class="filter-label" style="font-weight: 700; color: var(--text-primary);">
                <span class="filter-label-inner">
                  <input type="checkbox" id="mobile-filter-saved-only" class="filter-saved-checkbox">
                  <span>&#9733; Saved Tools Only</span>
                </span>
                <span id="mobile-saved-count-badge" class="filter-count-badge">0</span>
              </label>
            </div>

            <!-- Open Source Switch -->
            <div class="filter-group">
              <label class="filter-label" style="font-weight: 700; color: var(--text-primary);">
                <span class="filter-label-inner">
                  <input type="checkbox" id="mobile-filter-oss-only" class="filter-oss-checkbox">
                  <span>Open Source Only</span>
                </span>
                <span class="badge badge-oss">OSS</span>
              </label>
            </div>

            <!-- Pricing Models -->
            <div class="filter-group">
              <div class="filter-title">Pricing Model</div>
              <div class="filter-options">
                <label class="filter-label">
                  <span class="filter-label-inner"><input type="checkbox" class="filter-pricing-checkbox" value="free"> Free</span>
                  <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'free'])}</span>
                </label>
                <label class="filter-label">
                  <span class="filter-label-inner"><input type="checkbox" class="filter-pricing-checkbox" value="freemium"> Freemium</span>
                  <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'freemium'])}</span>
                </label>
                <label class="filter-label">
                  <span class="filter-label-inner"><input type="checkbox" class="filter-pricing-checkbox" value="paid"> Paid</span>
                  <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'paid'])}</span>
                </label>
                <label class="filter-label">
                  <span class="filter-label-inner"><input type="checkbox" class="filter-pricing-checkbox" value="open-source"> Open Source</span>
                  <span class="filter-count-badge">{len([t for t in tools if t.get('pricing', {}).get('model') == 'open-source'])}</span>
                </label>
              </div>
            </div>

            <!-- Platforms -->
            <div class="filter-group">
              <div class="filter-title">Platform Support</div>
              <div class="filter-options">
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="web"> Web Browser</span></label>
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="windows"> Windows</span></label>
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="macos"> macOS</span></label>
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="linux"> Linux</span></label>
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="android"> Android</span></label>
                <label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-platform-checkbox" value="ios"> iOS</span></label>
              </div>
            </div>

            <!-- Categories -->
            <div class="filter-group">
              <div class="filter-title">Categories ({len(categories)})</div>
              <div class="filter-options" style="max-height: 220px; overflow-y: auto;">
                {"".join([f'<label class="filter-label"><span class="filter-label-inner"><input type="checkbox" class="filter-category-checkbox" value="{c["id"]}"> {escape(c["name"])}</span></label>' for c in categories])}
              </div>
            </div>
          </div>
          <div class="mobile-filter-footer">
            <button class="btn btn-primary btn-block" onclick="toggleMobileFilterDrawer()">Show Matching Tools</button>
          </div>
        </div>
      </div>
    </div>
    """
    write_page("tools/index.html", render_page("AI Tools Directory Index", "Browse, search, and filter verified artificial intelligence tools.", dir_content, "/tools/", current_nav="tools", rel_base=".."))
    sitemap_urls.append(("/tools/", "0.9", "daily"))

    # 3. Individual Tool Detail Pages (/tool/<slug>/index.html - rel_base = "../..")
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
        limitations_html = "".join([f'<li class="feature-list-item"><span class="caution-icon">&bull;</span><span>{escape(lim)}</span></li>' for lim in tool.get("limitations", [])])

        alternatives_html = ""
        for alt_id in tool.get("alternatives", []):
            alt_tool = tool_map.get(alt_id)
            if alt_tool:
                alternatives_html += f'<a href="../../tool/{alt_tool["slug"]}/" class="filter-chip" style="margin-right: 0.5rem; margin-bottom: 0.5rem;">{escape(alt_tool["name"])} &rarr;</a>'

        related_html = ""
        for rel_id in tool.get("relatedTools", []):
            rel_tool = tool_map.get(rel_id)
            if rel_tool:
                related_html += f'<a href="../../tool/{rel_tool["slug"]}/" class="filter-chip" style="margin-right: 0.5rem; margin-bottom: 0.5rem;">{escape(rel_tool["name"])} &rarr;</a>'

        platforms_html = "".join([f'<span class="tool-tag" style="text-transform: capitalize;">{escape(p)}</span>' for p in tool.get("platforms", [])])

        faqs = generate_tool_faqs(tool, primary_cat["name"])
        faqs_html = "".join([f'''
        <div class="faq-item">
          <button class="faq-question" onclick="toggleFaq(this)">
            <span>{escape(q["question"])}</span>
            <span class="faq-icon">+</span>
          </button>
          <div class="faq-answer">
            <p>{escape(q["answer"])}</p>
          </div>
        </div>''' for q in faqs])

        tool_content = f"""
        <div class="detail-header">
          <div class="container">
            <nav class="breadcrumbs" aria-label="Breadcrumb">
              <a href="../../">Home</a> &rsaquo;
              <a href="../../tools/">Tools</a> &rsaquo;
              <a href="../../category/{primary_cat['slug']}/">{escape(primary_cat['name'])}</a> &rsaquo;
              <span>{escape(tool['name'])}</span>
            </nav>

            <div style="display: flex; align-items: flex-start; gap: 2rem; flex-wrap: wrap;">
              <div class="tool-monogram" style="width: 5rem; height: 5rem; font-size: 2.25rem; background: {get_tool_gradient(tool)}; color: #ffffff;">{escape(initial)}</div>
              <div style="flex: 1; min-width: 280px;">
                <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                  <h1 style="font-size: 2.5rem; font-weight: 800; letter-spacing: -0.03em;">{escape(tool['name'])}</h1>
                  <span class="verified-badge" style="font-size: 1.15rem;" title="Factually Verified by Editors">&#x2714; Verified</span>
                  <span class="badge {badge_class}" style="font-size: 0.875rem;">{escape(pricing)}</span>
                  {f'<span class="badge badge-oss">Open Source</span>' if tool.get('isOpenSource') else ''}
                </div>
                <p style="font-size: 1.2rem; color: var(--text-secondary); margin-top: 0.5rem; max-width: 800px; line-height: 1.5;">
                  {escape(tool['shortDescription'])}
                </p>
              </div>
              <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
                <button class="btn btn-outline fav-detail-btn" data-tool-id="{tool['id']}" onclick="toggleFavorite(event, '{tool['id']}')" aria-label="Save {escape(tool['name'])}">
                  <svg class="star-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                  </svg>
                  <span class="fav-detail-label">Save Tool</span>
                </button>
                <a href="{escape(tool['websiteUrl'])}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                  Visit Official Website &UpperRightArrow;
                </a>
              </div>
            </div>
          </div>
        </div>

        <div class="container" style="padding-bottom: 5rem;">
          <div class="detail-main-layout">
            <!-- Left Main Column -->
            <div>
              <div class="detail-content-box">
                <h2>About {escape(tool['name'])}</h2>
                <p style="font-size: 1.05rem; line-height: 1.7; color: var(--text-secondary); margin-bottom: 1.5rem;">
                  {escape(tool['description'])}
                </p>

                {f'''<h3 style="font-size: 1.15rem; margin: 2rem 0 0.85rem;">Key Capabilities & Features</h3>
                <ul class="feature-list" style="margin-bottom: 2rem;">
                  {features_html}
                </ul>''' if features_html else ''}

                {f'''<h3 style="font-size: 1.15rem; margin: 2rem 0 0.85rem;">Recommended Use Cases</h3>
                <ul class="feature-list" style="margin-bottom: 2rem;">
                  {use_cases_html}
                </ul>''' if use_cases_html else ''}

                {f'''<h3 style="font-size: 1.15rem; margin: 2rem 0 0.85rem; color: #ef4444;">Known Limitations & Trade-offs</h3>
                <ul class="feature-list">
                  {limitations_html}
                </ul>''' if limitations_html else ''}
              </div>

              <!-- Frequently Asked Questions -->
              <div class="detail-content-box">
                <h2>Frequently Asked Questions</h2>
                <div class="faq-section">
                  {faqs_html}
                </div>
              </div>

              <!-- Alternatives & Related Tools -->
              <div class="detail-content-box">
                <h2>Alternatives & Related Tools</h2>
                <div style="margin-bottom: 1.5rem;">
                  <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.65rem;">Direct Competitors</div>
                  <div style="display: flex; flex-wrap: wrap;">{alternatives_html or '<span style="color: var(--text-muted);">No direct alternatives listed.</span>'}</div>
                </div>
                <div>
                  <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.65rem;">Complementary Tools</div>
                  <div style="display: flex; flex-wrap: wrap;">{related_html or '<span style="color: var(--text-muted);">No complementary tools listed.</span>'}</div>
                </div>
              </div>
            </div>

            <!-- Right Sidebar Meta -->
            <aside>
              <div class="sidebar-card">
                <h3 style="font-size: 0.95rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 1rem;">Pricing & Model</h3>
                <div style="margin-bottom: 1rem;">
                  <span class="badge {badge_class}" style="font-size: 0.95rem; padding: 0.4rem 0.85rem;">{escape(pricing)}</span>
                </div>
                {f'<p style="font-size: 0.9rem; color: var(--text-secondary); line-height: 1.55; margin-bottom: 1.25rem;">{escape(pricing_details)}</p>' if pricing_details else ''}
                <div style="font-size: 0.8125rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 0.85rem;">
                  Fact-Checked: {escape(tool.get('lastVerifiedAt', 'Recently'))}
                </div>
              </div>

              <div class="sidebar-card">
                <h3 style="font-size: 0.95rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 1rem;">Platform Availability</h3>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem;">
                  {platforms_html}
                </div>

                <h3 style="font-size: 0.95rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.75rem;">Account Requirement</h3>
                <div style="font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
                  {'Account Required' if tool.get('accountRequired') is True else ('No Account Required' if tool.get('accountRequired') is False else 'Unspecified')}
                </div>

                {f'''<a href="{escape(tool.get('sourceCodeUrl'))}" target="_blank" rel="noopener noreferrer" class="btn btn-outline" style="width: 100%; margin-bottom: 1rem;">
                  View Source Code &UpperRightArrow;
                </a>''' if tool.get('sourceCodeUrl') else ''}

                <a href="{escape(tool['websiteUrl'])}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-block">
                  Visit {escape(tool['name'])} &UpperRightArrow;
                </a>
              </div>
            </aside>
          </div>
        </div>
        """

        tool_sd = [
            {
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
            },
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q["question"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": q["answer"]
                        }
                    } for q in faqs
                ]
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{CANONICAL_HOST}/"},
                    {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{CANONICAL_HOST}/tools/"},
                    {"@type": "ListItem", "position": 3, "name": primary_cat["name"], "item": f"{CANONICAL_HOST}/category/{primary_cat['slug']}/"},
                    {"@type": "ListItem", "position": 4, "name": tool["name"], "item": f"{CANONICAL_HOST}/tool/{slug}/"}
                ]
            }
        ]

        page_title = tool.get("seo", {}).get("title") or f"{tool['name']} — AI Tool Review, Features & Pricing"
        page_desc = tool.get("seo", {}).get("description") or tool["shortDescription"]
        write_page(f"tool/{slug}/index.html", render_page(page_title, page_desc, tool_content, f"/tool/{slug}/", tool_sd, rel_base="../.."))
        sitemap_urls.append((f"/tool/{slug}/", "0.8", "weekly"))

    # 4. Category Pages (/category/<slug>/index.html - rel_base = "../..")
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
        <div class="container" style="padding: 3.5rem 1.5rem 5rem;">
          <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="../../">Home</a> &rsaquo;
            <a href="../../tools/">Categories</a> &rsaquo;
            <span>{escape(cat['name'])}</span>
          </nav>

          <div style="margin-bottom: 3rem; max-width: 860px;">
            <h1 class="section-title" style="font-size: 2.5rem; margin-bottom: 0.85rem;">{escape(cat['name'])}</h1>
            <p style="font-size: 1.2rem; color: var(--text-secondary); line-height: 1.6;">
              {escape(cat['description'])}
            </p>
            {subcats_html}
          </div>

          <div style="font-size: 0.95rem; color: var(--text-muted); margin-bottom: 1.75rem; font-weight: 700;">
            {len(cat_tools)} verified AI tools in this category
          </div>

          <div class="grid-tools">
            {"".join([render_tool_card(t, rel_base="../..") for t in cat_tools])}
          </div>
        </div>
        """

        cat_sd = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{cat['name']} — AI Tools",
            "description": cat["shortDescription"],
            "url": f"{CANONICAL_HOST}/category/{cat['slug']}/"
        }

        write_page(f"category/{cat['slug']}/index.html", render_page(f"{cat['name']} AI Tools", cat["shortDescription"], cat_content, f"/category/{cat['slug']}/", cat_sd, rel_base="../.."))
        sitemap_urls.append((f"/category/{cat['slug']}/", "0.8", "weekly"))

    # 5. Collections Pages (/collections/index.html & /collection/<slug>/index.html)
    cols_index_content = f"""
    <div class="container" style="padding: 3.5rem 1.5rem 5rem;">
      <div style="margin-bottom: 3rem;">
        <h1 class="section-title" style="font-size: 2.5rem;">Curated AI Collections</h1>
        <p class="section-desc">Hand-crafted toolsets assembled by our editorial team for specific goals, technical environments, and industry workflows.</p>
      </div>

      <div class="grid-collections">
        {"".join([f'''
        <a href="../collection/{col['slug']}/" class="collection-card">
          <div style="color: var(--brand-primary); font-size: 1.85rem; margin-bottom: 0.85rem;">&#9733;</div>
          <div class="collection-card-title">{escape(col['title'])}</div>
          <p class="collection-card-desc">{escape(col['description'])}</p>
          <div style="font-size: 0.875rem; color: var(--brand-primary); font-weight: 700;">
            View {len(col['toolIds'])} Curated Tools &rarr;
          </div>
        </a>''' for col in collections])}
      </div>
    </div>
    """
    write_page("collections/index.html", render_page("Curated AI Tool Collections", "Explore expert-curated collections of AI tools.", cols_index_content, "/collections/", current_nav="collections", rel_base=".."))
    sitemap_urls.append(("/collections/", "0.8", "weekly"))

    for col in collections:
        col_tools = [tool_map[tid] for tid in col["toolIds"] if tid in tool_map]
        col_detail_content = f"""
        <div class="container" style="padding: 3.5rem 1.5rem 5rem;">
          <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="../../">Home</a> &rsaquo;
            <a href="../../collections/">Collections</a> &rsaquo;
            <span>{escape(col['title'])}</span>
          </nav>

          <div style="margin-bottom: 3rem; max-width: 820px;">
            <h1 class="section-title" style="font-size: 2.5rem; margin-bottom: 0.85rem;">{escape(col['title'])}</h1>
            <p style="font-size: 1.2rem; color: var(--text-secondary); line-height: 1.6; margin-bottom: 1.75rem;">
              {escape(col['description'])}
            </p>
            <div style="background: var(--bg-card); border-left: 4px solid var(--brand-primary); padding: 1.5rem; border-radius: var(--radius-md); font-size: 0.95rem; color: var(--text-secondary); line-height: 1.6;">
              <strong style="color: var(--text-primary);">Curator Note:</strong> {escape(col['curatorNotes'])}
            </div>
          </div>

          <div class="grid-tools">
            {"".join([render_tool_card(t, rel_base="../..") for t in col_tools])}
          </div>
        </div>
        """
        write_page(f"collection/{col['slug']}/index.html", render_page(col["title"], col["description"], col_detail_content, f"/collection/{col['slug']}/", rel_base="../.."))
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
                # Estimate read time (approx 200 words per min)
                word_count = len(body.split())
                meta["readTime"] = max(2, round(word_count / 200))
                articles.append(meta)

    # Sort articles newest first
    articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    blog_index_cards = "".join([f"""
    <article class="collection-card" style="padding: 2.25rem;">
      <div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.8125rem; color: var(--text-muted); margin-bottom: 0.85rem;">
        <span>{escape(a.get('publishedAt', '2026-10-15'))}</span>
        <span>&bull;</span>
        <span>{a.get('readTime', 3)} min read</span>
      </div>
      <h2 style="font-size: 1.45rem; font-weight: 700; margin-bottom: 0.85rem; line-height: 1.3;">
        <a href="../blog/{a['slug']}/" style="color: var(--text-primary);">{escape(a['title'])}</a>
      </h2>
      <p style="font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 1.5rem; line-height: 1.6; flex: 1;">
        {escape(a.get('description', ''))}
      </p>
      <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 1.25rem;">
        <span style="font-size: 0.8125rem; color: var(--text-muted);">By {escape(a.get('author', 'Editorial Staff'))}</span>
        <a href="../blog/{a['slug']}/" class="view-all-link">Read Full Guide &rarr;</a>
      </div>
    </article>""" for a in articles])

    blog_index_content = f"""
    <div class="container" style="padding: 3.5rem 1.5rem 5rem;">
      <div style="margin-bottom: 3rem;">
        <h1 class="section-title" style="font-size: 2.5rem;">AI Guides, Benchmarks & Tutorials</h1>
        <p class="section-desc">Practical workflows, tool comparison matrices, and step-by-step guides for developers and knowledge workers.</p>
      </div>
      <div class="grid-collections">
        {blog_index_cards}
      </div>
    </div>
    """
    write_page("blog/index.html", render_page("AI Guides & Tutorials", "Read practical guides and benchmarks on artificial intelligence tools.", blog_index_content, "/blog/", current_nav="blog", rel_base=".."))
    sitemap_urls.append(("/blog/", "0.8", "weekly"))

    for a in articles:
        html_body = parse_markdown(a["body"], rel_base="../..")
        article_content = f"""
        <article class="article-container">
          <nav class="breadcrumbs" aria-label="Breadcrumb" style="justify-content: center;">
            <a href="../../">Home</a> &rsaquo;
            <a href="../../blog/">Blog</a> &rsaquo;
            <span>{escape(a['title'])}</span>
          </nav>

          <header class="article-header">
            <h1 class="article-title">{escape(a['title'])}</h1>
            <div class="article-meta">
              <span>Published {escape(a.get('publishedAt', ''))}</span>
              <span>&bull;</span>
              <span>By {escape(a.get('author', 'Editorial Staff'))}</span>
              <span>&bull;</span>
              <span>{a.get('readTime', 3)} min read</span>
            </div>
          </header>

          <div class="prose">
            {html_body}
          </div>

          <div style="margin-top: 4rem; padding-top: 2rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <a href="../../blog/" class="view-all-link">&larr; Back to all guides</a>
            <a href="../../tools/" class="btn btn-primary">Browse AI Directory &UpperRightArrow;</a>
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
            "dateModified": a.get("updatedAt", a.get("publishedAt", "")),
            "mainEntityOfPage": f"{CANONICAL_HOST}/blog/{a['slug']}/"
        }
        write_page(f"blog/{a['slug']}/index.html", render_page(a["title"], a.get("description", ""), article_content, f"/blog/{a['slug']}/", article_sd, "blog", rel_base="../.."))
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
    write_page("about/index.html", render_page("About AI Tools Directory", "Learn about the mission and zero-cost static architecture of AI Tools Directory.", about_content, "/about/", current_nav="about", rel_base=".."))
    sitemap_urls.append(("/about/", "0.5", "monthly"))

    contact_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Contact & Tool Submission</h1>
      <div class="prose">
        <p>We welcome submissions, bug reports, and corrections from the community.</p>

        <h2>Submitting a New AI Tool</h2>
        <p>To request a listing for your tool or report outdated pricing:</p>
        <ol>
          <li>Ensure your tool satisfies our <a href="../about/">editorial guidelines</a>.</li>
          <li>Submit a pull request to the open-source database repository.</li>
          <li>Our automated test suite will validate the schema and referential integrity before review.</li>
        </ol>

        <h2>Reporting Inaccuracies</h2>
        <p>AI pricing and terms change quickly. If you discover a discrepancy in any record, please file an issue with the link to the official pricing page.</p>
      </div>
    </div>
    """
    write_page("contact/index.html", render_page("Contact & Feedback", "Submit AI tools or contact the directory maintainers.", contact_content, "/contact/", rel_base=".."))
    sitemap_urls.append(("/contact/", "0.5", "monthly"))

    privacy_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Privacy Policy</h1>
      <div class="prose">
        <p>Last updated: October 16, 2026</p>
        <h2>Zero Tracking & Data Sovereignty</h2>
        <p>AI Tools Directory is committed to maximum user privacy:</p>
        <ul>
          <li><strong>No Tracking Cookies</strong>: We do not use third-party advertising cookies or tracking pixels.</li>
          <li><strong>Local Browser Storage</strong>: The only data stored in your browser is your dark/light theme preference in <code>localStorage</code>.</li>
          <li><strong>Client-Side Search</strong>: Search queries remain 100% in your browser and are never transmitted to external query logging endpoints.</li>
        </ul>
      </div>
    </div>
    """
    write_page("privacy/index.html", render_page("Privacy Policy", "AI Tools Directory privacy statement. Zero tracking cookies.", privacy_content, "/privacy/", rel_base=".."))
    sitemap_urls.append(("/privacy/", "0.3", "yearly"))

    terms_content = f"""
    <div class="article-container">
      <h1 class="article-title" style="text-align: left; margin-bottom: 1.5rem;">Terms of Use</h1>
      <div class="prose">
        <p>Last updated: October 16, 2026</p>
        <h2>Directory Information Disclaimer</h2>
        <p>The information provided on AI Tools Directory is for general educational and discovery purposes only. Product names, logos, and brands are property of their respective owners. Listing does not imply affiliation or endorsement.</p>
        <h2>External Links</h2>
        <p>Our website and mobile app contain links to external third-party websites. We have no control over the privacy practices or contents of those external sites.</p>
      </div>
    </div>
    """
    write_page("terms/index.html", render_page("Terms of Use", "AI Tools Directory terms of use and editorial disclaimer.", terms_content, "/terms/", rel_base=".."))
    sitemap_urls.append(("/terms/", "0.3", "yearly"))

    error_content = f"""
    <div class="article-container" style="text-align: center; padding: 6rem 1.5rem;">
      <h1 style="font-size: 6rem; font-weight: 800; color: var(--brand-primary); margin-bottom: 0.5rem; font-family: var(--font-display);">404</h1>
      <h2 style="font-size: 2rem; margin-bottom: 1rem;">Page Not Found</h2>
      <p style="color: var(--text-secondary); max-width: 520px; margin: 0 auto 2.5rem; line-height: 1.6;">
        The requested page could not be located. It may have been updated, moved, or temporarily unavailable.
      </p>
      <a href="./" class="btn btn-primary">Return to Directory Homepage</a>
    </div>
    """
    write_page("404.html", render_page("Page Not Found (404)", "The requested page was not found.", error_content, "/404.html", rel_base="."))

    # 8. Sitemap and Robots
    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    for path, priority, freq in sitemap_urls:
        full_url = f"{CANONICAL_HOST}{path}"
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
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {CANONICAL_HOST}/sitemap.xml\n")

    print(f"[SUCCESS] Website build complete at {DIST_DIR}!")
    print(f"  Indexed routes generated: {len(sitemap_urls)}")

def write_page(rel_path, html_str):
    out_path = os.path.join(DIST_DIR, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)

if __name__ == "__main__":
    build_site()
