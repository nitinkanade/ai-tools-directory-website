#!/usr/bin/env python3
"""
Website Data Synchronization Script.
Ensures that the static website data directory (`ai-tools-directory-website/data`)
is strictly synchronized with the master database (`ai-tools-directory-database`).
Supports both local monorepo synchronization and fallback HTTPS remote sync.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

WEBSITE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_DB_DIR = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-database"))
LOCAL_DB_PUBLIC = os.path.join(LOCAL_DB_DIR, "public", "data")
LOCAL_DATA_DIR = os.path.join(WEBSITE_DIR, "data")

APP_DIR = os.path.abspath(os.path.join(WEBSITE_DIR, "..", "ai-tools-directory-app"))
APP_DATA_DIR = os.path.join(APP_DIR, "assets", "data")

REMOTE_BASE_URL = os.environ.get(
    "REMOTE_DATABASE_URL",
    "https://nitinkanade.github.io/ai-tools-directory-database/public/data"
)

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def sync_from_local_database():
    print("============================================================")
    print("AI Tools Directory — Website & App Synchronization")
    print(f"Master Database: {LOCAL_DB_DIR}")
    print("============================================================")
    
    # 1. Rebuild indexes in database
    build_script = os.path.join(LOCAL_DB_DIR, "scripts", "build_indexes.py")
    if os.path.exists(build_script):
        print("--> [1/3] Compiling master database indexes...")
        subprocess.run([sys.executable, build_script], cwd=LOCAL_DB_DIR, check=True)

    if not os.path.exists(LOCAL_DB_PUBLIC):
        raise FileNotFoundError(f"Local database public data not found at {LOCAL_DB_PUBLIC}")

    # 2. Copy to website data/
    os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
    count = 0
    for root, _, files in os.walk(LOCAL_DB_PUBLIC):
        rel = os.path.relpath(root, LOCAL_DB_PUBLIC)
        target = os.path.join(LOCAL_DATA_DIR, rel) if rel != "." else LOCAL_DATA_DIR
        os.makedirs(target, exist_ok=True)
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(target, fname)
            shutil.copy2(src, dst)
            count += 1
    print(f"--> [2/3] Copied {count} files to website data directory: {LOCAL_DATA_DIR}")

    # 3. Copy to app assets/data/
    if os.path.exists(APP_DIR):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        app_count = 0
        for root, _, files in os.walk(LOCAL_DB_PUBLIC):
            rel = os.path.relpath(root, LOCAL_DB_PUBLIC)
            target = os.path.join(APP_DATA_DIR, rel) if rel != "." else APP_DATA_DIR
            os.makedirs(target, exist_ok=True)
            for fname in files:
                src = os.path.join(root, fname)
                dst = os.path.join(target, fname)
                shutil.copy2(src, dst)
                app_count += 1
        print(f"--> [3/3] Copied {app_count} files to app bundled assets: {APP_DATA_DIR}")

    # 4. Verify Checksums
    key_files = ["manifest.json", "categories.json", "collections.json", "search-index.json", os.path.join("tools", "index.json")]
    print("\n--> Verifying Checksum Parity between Database, Website, and App...")
    all_match = True
    for kf in key_files:
        db_f = os.path.join(LOCAL_DB_PUBLIC, kf)
        web_f = os.path.join(LOCAL_DATA_DIR, kf)
        db_h = sha256_file(db_f)
        web_h = sha256_file(web_f)
        
        app_match = True
        if os.path.exists(APP_DIR):
            app_f = os.path.join(APP_DATA_DIR, kf)
            app_h = sha256_file(app_f)
            app_match = (db_h == app_h)

        if db_h == web_h and app_match:
            print(f"  [PARITY MATCH] {kf:25s} -> {db_h[:16]}...")
        else:
            print(f"  [ERROR] Parity mismatch for {kf}!")
            all_match = False

    if not all_match:
        raise ValueError("Data parity check failed across ecosystem!")
    print("\n[SUCCESS] Website and App data are 100% synchronized with the database folder!\n")

def sync_from_remote(remote_url=REMOTE_BASE_URL):
    print(f"--> Syncing from remote database endpoint: {remote_url}...")
    manifest_url = f"{remote_url}/manifest.json"
    req = urllib.request.Request(manifest_url, headers={"User-Agent": "AI-Tools-Website-Sync/1.0"})
    with urllib.request.urlopen(req) as resp:
        manifest = json.loads(resp.read().decode("utf-8"))

    os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
    with open(os.path.join(LOCAL_DATA_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    files_map = manifest.get("files", {})
    print(f"--> Manifest specifies {len(files_map)} files to download...")

    for rel_path in files_map:
        clean_path = rel_path.lstrip("/").replace("data/", "", 1)
        file_url = f"{remote_url}/{clean_path}"
        dest_file = os.path.join(LOCAL_DATA_DIR, clean_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)

        try:
            req_file = urllib.request.Request(file_url, headers={"User-Agent": "AI-Tools-Website-Sync/1.0"})
            with urllib.request.urlopen(req_file) as file_resp:
                content = file_resp.read()
            with open(dest_file, "wb") as f:
                f.write(content)
            print(f"  [OK] {clean_path}")
        except Exception as e:
            print(f"  [WARN] Failed to fetch {file_url}: {e}")

    print(f"[SUCCESS] Downloaded remote database files into {LOCAL_DATA_DIR}.")

def main():
    if os.path.exists(LOCAL_DB_PUBLIC):
        sync_from_local_database()
    else:
        sync_from_remote()

if __name__ == "__main__":
    main()
