#!/usr/bin/env python3
"""Build a minimal, reproducible LaterOn extension ZIP from an explicit allowlist."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# 每个构建目标对应的 manifest 源文件。
# 归档里它一律叫 manifest.json —— 浏览器只认这个文件名，两个目标靠"内容不同"区分。
MANIFEST_SOURCE = {
    "chrome": ROOT / "manifest.json",
    "firefox": ROOT / "manifest.firefox.json",
}

# Only files required by the installed extension belong in a release package.
# Keep this list explicit: adding a test, screenshot, design draft or document to
# the repository must never make it into a user's extension by accident.
RUNTIME_FILES = (
    "manifest.json",
    "article-cover-placeholder.png",
    "background.js",
    "boot.js",
    "content-folder-picker.js",
    "content-metadata.js",
    "content-translation.js",
    "dialog.css",
    "dialog.js",
    "ff-sidebar.js",
    "i18n.js",
    "icon16.png",
    "icon32.png",
    "icon48.png",
    "icon128.png",
    "library.css",
    "library.html",
    "library.js",
    "onboarding.css",
    "onboarding.js",
    "picker-ui.js",
    "reading-position-background.js",
    "content-reading-position.js",
    "settings.css",
    "settings.html",
    "settings.js",
    "sidepanel.css",
    "sidepanel.html",
    "sidepanel.js",
    "tab-navigation.js",
    "theme-vars.css",
    "theme.js",
    "translation.css",
    "url-utils.js",
)
RUNTIME_DIRS = ("_locales",)

FORBIDDEN_PREFIXES = ("tests/", "design/", "scripts/", "dist/", ".git/")
FORBIDDEN_NAMES = {
    ".DS_Store",
    ".gitignore",
    "README.md",
    "CHANGELOG.md",
    "icon.svg",
    "popup.css",
    "popup.html",
    "popup.js",
    # 第二层保险：即使有人误把它加进 RUNTIME_FILES，这一条也会让打包失败。
    # 归档里只能有一个 manifest.json，它必须是按目标选出来的那一份。
    "manifest.firefox.json",
}


def relative_name(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def release_files() -> list[Path]:
    files = [ROOT / name for name in RUNTIME_FILES]
    for directory in RUNTIME_DIRS:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())

    missing = [relative_name(path) for path in files if not path.is_file()]
    if missing:
        raise RuntimeError("Missing required release files: " + ", ".join(missing))

    duplicates = [name for name in {relative_name(path) for path in files} if sum(relative_name(item) == name for item in files) > 1]
    if duplicates:
        raise RuntimeError("Duplicate release entries: " + ", ".join(sorted(duplicates)))

    return sorted(files, key=relative_name)


def validate_manifest(files: list[Path], target: str = "chrome") -> str:
    source = MANIFEST_SOURCE[target]
    if not source.is_file():
        raise RuntimeError(f"Missing manifest for target {target}: {source.name}")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()
    if not version:
        raise RuntimeError(f"{source.name} has no version")

    names = {relative_name(path) for path in files}

    if target == "firefox":
        # Firefox 独有的硬校验：漏掉任何一个引用的文件都会在运行时 404，必须在这里拦住。
        referenced = set(manifest.get("background", {}).get("scripts", []))
        sidebar = manifest.get("sidebar_action", {})
        referenced.add(sidebar.get("default_panel"))
        referenced.add(manifest.get("options_ui", {}).get("page"))
        referenced.update(sidebar.get("default_icon", {}).values())

        # 反向校验：Chrome 专有键一个都不许留在 Firefox manifest 里。
        # 这是防止"改着改着又抄回 Chrome 键"的自动闸门。
        chrome_only = sorted(
            key for key in ("side_panel", "options_page", "minimum_chrome_version") if key in manifest
        )
        if chrome_only:
            raise RuntimeError(
                "Firefox manifest must not contain Chrome-only keys: " + ", ".join(chrome_only)
            )

        gecko = manifest.get("browser_specific_settings", {}).get("gecko", {})
        if not gecko.get("id"):
            raise RuntimeError("Firefox manifest must declare browser_specific_settings.gecko.id")
        if not gecko.get("strict_min_version"):
            raise RuntimeError(
                "Firefox manifest must declare browser_specific_settings.gecko.strict_min_version"
            )
    else:
        referenced = {
            manifest.get("background", {}).get("service_worker"),
            manifest.get("side_panel", {}).get("default_path"),
            manifest.get("options_page"),
        }

    referenced.update(manifest.get("icons", {}).values())
    referenced.update(manifest.get("action", {}).get("default_icon", {}).values())
    for group in manifest.get("web_accessible_resources", []):
        referenced.update(group.get("resources", []))

    missing = sorted(path for path in referenced if path and path not in names)
    if missing:
        raise RuntimeError("Manifest references files outside the release allowlist: " + ", ".join(missing))
    return version


def validate_archive(archive: Path, expected: set[str]) -> None:
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Release ZIP contains duplicate entries")
        if set(names) != expected:
            missing = sorted(expected - set(names))
            extra = sorted(set(names) - expected)
            raise RuntimeError(f"Release ZIP contents differ from allowlist; missing={missing}, extra={extra}")
        for name in names:
            if name in FORBIDDEN_NAMES or name.endswith(".md") or name.startswith(FORBIDDEN_PREFIXES):
                raise RuntimeError(f"Development-only file leaked into release ZIP: {name}")
        json.loads(package.read("manifest.json").decode("utf-8"))


def build(target: str = "chrome") -> Path:
    files = release_files()
    version = validate_manifest(files, target)
    # manifest.json 的字节来自目标对应的那一份源文件；其余文件原样读取。
    manifest_bytes = MANIFEST_SOURCE[target].read_bytes()
    DIST.mkdir(exist_ok=True)
    archive = DIST / (
        f"LaterOn-{version}.zip" if target == "chrome" else f"LaterOn-{version}-{target}.zip"
    )
    temporary = archive.with_suffix(".zip.tmp")

    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
            for path in files:
                name = relative_name(path)
                # A fixed timestamp makes identical source trees produce identical archives.
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                payload = manifest_bytes if name == "manifest.json" else path.read_bytes()
                package.writestr(entry, payload, compresslevel=9)
        validate_archive(temporary, {relative_name(path) for path in files})
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)

    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a LaterOn release ZIP from an explicit allowlist.")
    parser.add_argument(
        "--target",
        choices=sorted(MANIFEST_SOURCE),
        default="chrome",
        help="chrome（默认，用 manifest.json）或 firefox（用 manifest.firefox.json）",
    )
    arguments = parser.parse_args()

    try:
        archive = build(arguments.target)
    except Exception as error:
        print(f"Release build failed: {error}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(archive) as package:
        count = len(package.namelist())
    size_kb = archive.stat().st_size / 1024
    print(f"Built {archive.relative_to(ROOT)} ({count} files, {size_kb:.1f} KB) [{arguments.target} target]")
    print("Verified: no tests, design drafts, previews, documentation, .DS_Store or icon.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
