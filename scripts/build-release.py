#!/usr/bin/env python3
"""Build a minimal, reproducible LaterOn extension ZIP from an explicit allowlist.

用法：
    python scripts/build-release.py                      # Chrome 版 → dist/LaterOn-<v>.zip
    python scripts/build-release.py --target firefox     # Firefox 直装版（min 115）→ dist/LaterOn-<v>-firefox.zip
    python scripts/build-release.py --target firefox --amo   # AMO 签名版（dcp + min 140）→ dist/LaterOn-<v>-firefox-amo.zip
"""

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

# AMO（addons.mozilla.org）提交要求：2025-11-03 起，提交到 AMO 的新扩展必须在
# browser_specific_settings.gecko 里声明 data_collection_permissions，否则会被直接拒绝；
# 该键只有 Firefox 140+ 认识，所以 AMO 目标同时把 strict_min_version 抬到 140，
# 避免出现"声明了、但对声明范围内的旧版本其实无效"的清单。
# LaterOn 不上传任何数据 → required: ["none"]。
AMO_MIN_VERSION = "140.0"
DATA_COLLECTION_PERMISSIONS = {"required": ["none"]}

# Only extension runtime files and the required license notice belong in a release
# package. Keep this list explicit: adding a test, screenshot, design draft or
# document to the repository must never make it into a user's extension by accident.
# LICENSE 自上游 a1a5313 起必须随包分发（MIT 要求分发时保留版权声明与协议全文）。
RUNTIME_FILES = (
    "LICENSE",
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


def load_manifest(target: str, amo: bool = False) -> tuple[dict, bytes]:
    """返回（解析后的 manifest 字典, 写进归档的字节）。

    amo=True 时不动磁盘上的源文件，只在内存里补 AMO 要求的两个键 ——
    这样"给 GitHub 直装用的 115 版"和"给 AMO 签名用的 140 版"
    永远来自同一份 manifest.firefox.json，不会互相漂移。
    """
    source = MANIFEST_SOURCE[target]
    if not source.is_file():
        raise RuntimeError(f"Missing manifest for target {target}: {source.name}")

    manifest = json.loads(source.read_text(encoding="utf-8"))
    if not amo:
        return manifest, source.read_bytes()
    if target != "firefox":
        raise RuntimeError("--amo is only valid together with --target firefox")

    gecko = manifest.setdefault("browser_specific_settings", {}).setdefault("gecko", {})
    gecko["data_collection_permissions"] = DATA_COLLECTION_PERMISSIONS
    gecko["strict_min_version"] = AMO_MIN_VERSION
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return manifest, payload.encode("utf-8")


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(value).split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts) or (0,)


def validate_manifest(
    files: list[Path],
    target: str,
    manifest: dict,
    source_name: str,
    amo: bool = False,
) -> str:
    version = str(manifest.get("version", "")).strip()
    if not version:
        raise RuntimeError(f"{source_name} has no version")

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
        minimum = gecko.get("strict_min_version")
        if not minimum:
            raise RuntimeError(
                "Firefox manifest must declare browser_specific_settings.gecko.strict_min_version"
            )
        if amo:
            # AMO 专用的两道闸门：缺 dcp 会被拒签；min 版本低于 140 会让 dcp 变成空头声明。
            if not (gecko.get("data_collection_permissions") or {}).get("required"):
                raise RuntimeError(
                    "AMO target must declare browser_specific_settings.gecko.data_collection_permissions.required"
                )
            if _version_tuple(minimum) < _version_tuple(AMO_MIN_VERSION):
                raise RuntimeError(
                    f"AMO target requires strict_min_version >= {AMO_MIN_VERSION}, got {minimum}"
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


def build(target: str = "chrome", amo: bool = False) -> Path:
    files = release_files()
    manifest, manifest_bytes = load_manifest(target, amo)
    version = validate_manifest(files, target, manifest, MANIFEST_SOURCE[target].name, amo)
    DIST.mkdir(exist_ok=True)
    if target == "chrome":
        archive = DIST / f"LaterOn-{version}.zip"
    elif amo:
        archive = DIST / f"LaterOn-{version}-firefox-amo.zip"
    else:
        archive = DIST / f"LaterOn-{version}-firefox.zip"
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
    parser.add_argument(
        "--amo",
        action="store_true",
        help=(
            "AMO submission variant: patch gecko in memory with data_collection_permissions "
            f"and raise strict_min_version to {AMO_MIN_VERSION} (source manifest untouched); "
            "output is LaterOn-<version>-firefox-amo.zip; firefox target only"
        ),
    )
    arguments = parser.parse_args()

    try:
        archive = build(arguments.target, arguments.amo)
    except Exception as error:
        print(f"Release build failed: {error}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(archive) as package:
        count = len(package.namelist())
        manifest = json.loads(package.read("manifest.json").decode("utf-8"))
    size_kb = archive.stat().st_size / 1024
    label = arguments.target + (" + amo-ready" if arguments.amo else "")
    gecko = manifest.get("browser_specific_settings", {}).get("gecko", {})
    print(f"Built {archive.relative_to(ROOT)} ({count} files, {size_kb:.1f} KB) [{label} target]")
    print(
        "manifest.json: gecko.id={id} strict_min_version={min}{dcp}".format(
            id=gecko.get("id"),
            min=gecko.get("strict_min_version"),
            dcp=(
                " data_collection_permissions="
                + json.dumps(gecko.get("data_collection_permissions"), ensure_ascii=False)
                if "data_collection_permissions" in gecko
                else " data_collection_permissions=<not declared>"
            ),
        )
    )
    print("Verified: no tests, design drafts, previews, documentation, .DS_Store or icon.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
