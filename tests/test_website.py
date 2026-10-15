"""
Test suite for AI Tools Directory static website build, SEO metadata, and routes.
"""

import os
import re
import sys
import unittest

WEBSITE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(WEBSITE_DIR, "dist")
sys.path.insert(0, os.path.join(WEBSITE_DIR, "scripts"))

from build import build_site

class TestWebsiteBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Trigger build
        build_site()

    def test_dist_directory_exists(self):
        self.assertTrue(os.path.exists(DIST_DIR), "dist directory must exist after build")

    def test_core_pages_exist(self):
        core_files = [
            "index.html",
            "tools/index.html",
            "collections/index.html",
            "blog/index.html",
            "about/index.html",
            "contact/index.html",
            "privacy/index.html",
            "terms/index.html",
            "404.html",
            "sitemap.xml",
            "robots.txt",
            "static/css/styles.css",
            "static/js/app.js",
            "data/manifest.json",
            "data/search-index.json"
        ]
        for cf in core_files:
            fp = os.path.join(DIST_DIR, cf.replace("/", os.sep))
            self.assertTrue(os.path.exists(fp), f"Core file missing in dist: {cf}")

    def test_tool_pages_generated(self):
        tool_slugs = ["chatgpt", "claude", "cursor", "github-copilot", "ollama", "midjourney"]
        for slug in tool_slugs:
            fp = os.path.join(DIST_DIR, "tool", slug, "index.html")
            self.assertTrue(os.path.exists(fp), f"Tool page missing for {slug}")
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("<h1", content)
                self.assertIn("Verified", content)
                self.assertIn("application/ld+json", content)
                self.assertIn("SoftwareApplication", content)

    def test_category_pages_generated(self):
        cat_slugs = ["coding-development", "chatbots-assistants", "opensource-models-platforms"]
        for cat in cat_slugs:
            fp = os.path.join(DIST_DIR, "category", cat, "index.html")
            self.assertTrue(os.path.exists(fp), f"Category page missing for {cat}")

    def test_blog_articles_generated(self):
        fp = os.path.join(DIST_DIR, "blog", "top-ai-coding-assistants-2026", "index.html")
        self.assertTrue(os.path.exists(fp), "Blog article page missing")
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Cursor vs Claude Code", content)
            self.assertIn("BlogPosting", content)

    def test_sitemap_xml_contains_urls(self):
        sitemap_path = os.path.join(DIST_DIR, "sitemap.xml")
        self.assertTrue(os.path.exists(sitemap_path))
        with open(sitemap_path, "r", encoding="utf-8") as f:
            text = f.read()
            self.assertIn("<urlset", text)
            self.assertIn("/tool/chatgpt/", text)
            self.assertIn("/category/coding-development/", text)

    def test_assetlinks_json_exists_and_valid(self):
        assetlinks_path = os.path.join(DIST_DIR, ".well-known", "assetlinks.json")
        self.assertTrue(os.path.exists(assetlinks_path), "assetlinks.json must be deployed to dist/.well-known/")
        import json
        with open(assetlinks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        entry = data[0]
        self.assertIn("delegate_permission/common.handle_all_urls", entry.get("relation", []))
        self.assertEqual(entry.get("target", {}).get("namespace"), "android_app")
        self.assertEqual(entry.get("target", {}).get("package_name"), "in.ni18.aitoolsdirectory")
        self.assertGreaterEqual(len(entry.get("target", {}).get("sha256_cert_fingerprints", [])), 1)

    def test_nojekyll_exists(self):
        nojekyll_path = os.path.join(DIST_DIR, ".nojekyll")
        self.assertTrue(os.path.exists(nojekyll_path), ".nojekyll file must exist in dist to prevent Jekyll ignoring .well-known")

    def test_website_data_synced_with_database_folder(self):
        import hashlib
        def sha256(fp):
            with open(fp, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        db_public = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-database", "public", "data"))
        dist_data = os.path.join(DIST_DIR, "data")
        local_data = os.path.join(WEBSITE_DIR, "data")

        key_files = ["manifest.json", "categories.json", "collections.json", "search-index.json", os.path.join("tools", "index.json")]
        
        # Verify website dist matches website source data
        for kf in key_files:
            dist_f = os.path.join(dist_data, kf)
            local_f = os.path.join(local_data, kf)
            self.assertTrue(os.path.exists(dist_f), f"Missing in dist/data: {kf}")
            self.assertTrue(os.path.exists(local_f), f"Missing in data/: {kf}")
            self.assertEqual(sha256(dist_f), sha256(local_f), f"Hash mismatch between dist/data and data for {kf}")

        # If master database folder exists, verify exact parity with database
        if os.path.exists(db_public):
            for kf in key_files:
                db_f = os.path.join(db_public, kf)
                dist_f = os.path.join(dist_data, kf)
                self.assertTrue(os.path.exists(db_f), f"Missing in DB public/data: {kf}")
                self.assertEqual(sha256(db_f), sha256(dist_f), f"Website data not synced with database folder for {kf}")

    def test_app_data_synced_with_website_and_database(self):
        import hashlib
        def sha256(fp):
            with open(fp, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        app_assets = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-app", "assets", "data"))
        dist_data = os.path.join(DIST_DIR, "data")

        if os.path.exists(app_assets):
            key_files = ["manifest.json", "categories.json", "collections.json", "search-index.json", os.path.join("tools", "index.json")]
            for kf in key_files:
                app_f = os.path.join(app_assets, kf)
                dist_f = os.path.join(dist_data, kf)
                self.assertTrue(os.path.exists(app_f), f"Missing in app assets/data: {kf}")
                self.assertEqual(sha256(app_f), sha256(dist_f), f"App and website data not synced for {kf}")

if __name__ == "__main__":
    unittest.main()

