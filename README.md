# AI Tools Directory — Website

A fast, responsive, mobile-first static website hosted on GitHub Pages.

## Features

- **SEO Optimized**: Static HTML pre-rendered for all 40+ tool detail pages, 20 category landings, collections, and blog articles.
- **Micro-Animations & Modern Design**: Dark/light mode theme toggle, glassmorphic header, responsive grid system, and accessible typography.
- **Client-Side In-Memory Search**: Token-based debounced search with relevance scoring matching the ecosystem standard.
- **Zero Cost & GitHub Pages Ready**: Emits clean HTML with an XML sitemap and robots.txt. No paid backend or runtime needed.
- **Markdown Blog Engine**: Built-in parser for Markdown articles with YAML frontmatter.

## Development & Local Preview

```bash
# Build static site to dist/
npm run build
# Or: python scripts/build.py

# Launch local preview server (http://localhost:3000)
npm run dev
# Or: node server.js

# Run automated tests
npm test
# Or: python -m unittest discover tests
```

## Directory Structure

```
ai-tools-directory-website/
├── content/
│   └── blog/               # Markdown articles with frontmatter
├── static/
│   ├── css/styles.css      # Design system & CSS custom properties
│   └── js/app.js           # Client-side theme, search & filtering
├── scripts/
│   └── build.py            # Static site generator
├── tests/
│   └── test_website.py     # Route & HTML integrity test suite
├── server.js               # Zero-dependency Node preview server
├── package.json            # Scripts and metadata
└── dist/                   # Build output ready for GitHub Pages
```
