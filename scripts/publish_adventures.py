#!/usr/bin/env python3
"""
TaleWeaver Adventure Publisher CLI.

Publishes adventure bundles (``.adz``/``.adv``) as GitHub release assets in the
distribution repository and maintains the machine-readable ``catalog.json``
(schema 1) on its default branch.

Spec: docs/specs/adventure_distribution.md (D1-D3, D5, D9, sections 4, 6, 7).

Design:

* ``plan``     — scan + validate bundles, classify each against existing release
                 tags (new / unchanged / update / conflict), report cover
                 presence, and ensure exactly one tracking issue per adventure.
                 Never writes releases or the catalog.
* ``publish``  — create/update release, upload assets, re-verify by reading the
                 release back, and only then merge ``catalog.json``. ``--dry-run``
                 is the default; real publishing requires ``--yes``.

Idempotency keys: release tag ``adv/<slug>/v<version>`` and the hidden issue
marker ``<!-- adventure-id:<origin_id> -->``. The script is re-runnable at any
point without side effects.

Security (CWE-22 + ruleset):

* every resolved path must stay under ``--source``;
* zip members are addressed by normalized in-archive path only — no absolute
  paths, no ``..``, never ``extractall``;
* asset names match ``[a-z0-9.-]+`` (slug regex);
* subprocess args are passed as a list (no shell interpolation);
* no secret/token is ever logged.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

__version__ = "1.1.0"
VERSION_STRING = f"publish_adventures.py {__version__}"

# --- Constants ---------------------------------------------------------------

DEFAULT_REPO = "jschm42/taleweaver-adventures"
DEFAULT_REPO_ENV = "ADVENTURE_CATALOG_REPO"
DEFAULT_SOURCE_ENV = "TALEWEAVER_ADVENTURE_SOURCE"
DEFAULT_SOURCE = "/home/jean/taleweaver-adventures/incoming"
DEFAULT_MIN_APP_VERSION = "0.7.0"
DEFAULT_BRANCH = "main"

CATALOG_FILENAME = "catalog.json"
ISSUE_LABEL = "adventure"
ISSUE_MARKER_PREFIX = "<!-- adventure-id:"
ISSUE_MARKER_SUFFIX = " -->"
MAX_ASSET_BYTES = 100 * 1024 * 1024  # 100 MiB GitHub release asset limit
MAX_COVER_BYTES = 2 * 1024 * 1024    # 2 MiB source image cap (D9)
MAX_COVER_EDGE = 1600               # px, longest edge after re-encode (D9)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SUPPORTED_FORMATS = {"TaleWeaver", "taleweaver.adz"}

# PNG magic + JPEG SOF markers (for dimension sniffing without PIL)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


# --- Small helpers -----------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(title: str) -> str:
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:128]


def sha256_file(path: "Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_within(source: "Path", candidate: "Path") -> "Path":
    """Resolve a candidate path and enforce it stays under ``source`` (CWE-22)."""
    src = source.resolve()
    cand = candidate.resolve()
    try:
        cand.relative_to(src)
    except ValueError:
        raise ValueError(f"path escapes source directory: {candidate}")
    return cand


def normalize_archive_relpath(raw: str) -> Optional[str]:
    """Normalize an in-archive relative path; return None if unsafe.

    Rejects absolute paths, drive letters, '..', empty segments after
    normalization. Returns a POSIX relative path safe to use with ZipFile.read.
    """
    if not raw or not isinstance(raw, str):
        return None
    norm = raw.replace("\\", "/").strip()
    if norm.startswith("/") or re.match(r"^[a-zA-Z]:", norm):
        return None
    p = PurePosixPath(norm)
    if any(part == ".." for part in p.parts):
        return None
    parts = [part for part in p.parts if part not in ("", ".", "..")]
    if not parts:
        return None
    return "/".join(parts)


# --- gh bridge ---------------------------------------------------------------

def run_gh(args: list[str], *, check: bool = True) -> str:
    """Run ``gh`` with args passed as a list (no shell interpolation)."""
    cmd = ["gh"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args)} failed (rc={proc.returncode}):\n{proc.stderr.strip()}"
        )
    return proc.stdout


def gh_json(args: list[str]) -> Any:
    out = run_gh(args)
    if not out.strip():
        return None
    return json.loads(out)


def repo_args(repo: str) -> list[str]:
    return ["--repo", repo]


# --- Bundle scanning & validation ---------------------------------------------

class ValidationError(Exception):
    pass


class Bundle:
    """A validated adventure bundle discovered under ``--source``."""

    def __init__(self, path: "Path", manifest: dict[str, Any], adv: dict[str, Any]):
        self.path = path
        self.basename = path.name
        self.manifest = manifest
        self.adv = adv

        self.title = str(adv.get("title") or "").strip()
        self.origin_id = str(adv.get("origin_id") or "").strip()
        self.adv_version = str(adv.get("version") or "").strip()
        self.format_version = str(manifest.get("version") or "").strip()
        self.slug = slugify(self.title)
        self.creator = str(adv.get("creator") or "").strip()
        self.license = str(adv.get("license") or "").strip()
        self.language = str(adv.get("language") or "").strip()
        self.teaser = str(adv.get("teaser") or "").strip()
        self.image_url = str(adv.get("image_url") or "").strip()

        self.size_bytes = 0
        self.sha256 = ""
        self.cover_bytes: Optional[bytes] = None
        self.cover_sha256 = ""
        self.cover_warning: Optional[str] = None

    @property
    def tag(self) -> str:
        return f"adv/{self.slug}/v{self.adv_version}"

    @property
    def asset_name(self) -> str:
        return f"{self.slug}-{self.adv_version}.adz"

    @property
    def has_cover(self) -> bool:
        return self.cover_bytes is not None


def _validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("manifest is not a JSON object")
    fmt = payload.get("format")
    if fmt not in SUPPORTED_FORMATS:
        raise ValidationError(
            f"unsupported format {fmt!r}; expected one of {sorted(SUPPORTED_FORMATS)}"
        )
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValidationError("missing top-level version (format version)")
    return payload


def _sniff_png_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    if not data.startswith(_PNG_MAGIC) or len(data) < 24:
        return None
    w, h = struct.unpack(">II", data[16:24])
    return (w, h) if w > 0 and h > 0 and w <= (1 << 20) and h <= (1 << 20) else None


def _sniff_jpeg_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    if not data.startswith(_JPEG_MAGIC):
        return None
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xD8:  # SOI
            i += 2
            continue
        if marker == 0xD9 or marker == 0xDA:  # EOI / SOS
            break
        if i + 4 > n:
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if seg_len < 2:
            break
        if marker in _JPEG_SOF:
            if i + 9 > n:
                return None
            h = struct.unpack(">H", data[i + 5:i + 7])[0]
            w = struct.unpack(">H", data[i + 7:i + 9])[0]
            return (w, h) if w > 0 and h > 0 else None
        i += 2 + seg_len
    return None


def _make_png_from_jpeg(data: bytes) -> Optional[bytes]:
    """Re-encode a JPEG cover as PNG, downscaling to <= MAX_COVER_EDGE.

    Uses Pillow if available; otherwise skips re-encode (cover dropped with a
    warning). Returns PNG bytes or None.
    """
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        img = img.convert("RGB")
        w, h = img.size
        longest = max(w, h)
        if longest > MAX_COVER_EDGE:
            scale = MAX_COVER_EDGE / longest
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                             Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _extract_cover(bundle: Bundle, zf: zipfile.ZipFile) -> None:
    """Extract + validate the bundled cover per D9.

    Reads ``adventure.image_url`` from the manifest and resolves it as an
    in-archive relative member (no extractall, no absolute paths, no '..').
    Caps: 2 MiB source size, 1600 px longest edge after re-encode. Fails soft:
    warnings are recorded, publish continues, entry gets no cover pair.
    """
    if not bundle.image_url:
        bundle.cover_warning = "no adventure.image_url in manifest"
        return
    arcname = normalize_archive_relpath(bundle.image_url)
    if arcname is None:
        bundle.cover_warning = f"unsafe cover path in manifest: {bundle.image_url!r}"
        return
    try:
        info = zf.getinfo(arcname)
    except KeyError:
        bundle.cover_warning = f"cover member {arcname!r} not found inside bundle"
        return
    if info.file_size > MAX_COVER_BYTES:
        bundle.cover_warning = (
            f"cover member {arcname!r} is {info.file_size} bytes "
            f"(> {MAX_COVER_BYTES} cap)"
        )
        return
    raw = zf.read(info)
    if not raw:
        bundle.cover_warning = f"cover member {arcname!r} is empty"
        return

    png_dims = _sniff_png_dimensions(raw)
    if png_dims:
        w, h = png_dims
        if max(w, h) > MAX_COVER_EDGE:
            bundle.cover_warning = f"cover {arcname!r} is {w}x{h} (longest edge > {MAX_COVER_EDGE})"
            return
        bundle.cover_bytes = raw
        bundle.cover_sha256 = sha256_bytes(raw)
        return

    jpeg_dims = _sniff_jpeg_dimensions(raw)
    if jpeg_dims:
        w, h = jpeg_dims
        png = _make_png_from_jpeg(raw)
        if png is None:
            bundle.cover_warning = (
                f"cover {arcname!r} is JPEG; Pillow unavailable for PNG re-encode"
            )
            return
        w2, h2 = _sniff_png_dimensions(png) or (0, 0)
        if w2 and h2 and max(w2, h2) > MAX_COVER_EDGE:
            bundle.cover_warning = f"cover after re-encode exceeds {MAX_COVER_EDGE}px"
            return
        bundle.cover_bytes = png
        bundle.cover_sha256 = sha256_bytes(png)
        return

    bundle.cover_warning = (
        f"cover member {arcname!r} is neither PNG nor JPEG (unknown image format)"
    )


def scan_bundle(path: "Path") -> Bundle:
    with zipfile.ZipFile(path) as zf:
        try:
            raw = zf.read("adventure.adv")
        except KeyError:
            raise ValidationError(f"{path.name}: missing adventure.adv inside bundle")
        try:
            manifest = json.loads(raw)
        except ValueError as exc:
            raise ValidationError(f"{path.name}: adventure.adv is not valid JSON ({exc})")

    manifest = _validate_manifest(manifest)
    adv = manifest.get("adventure")
    if not isinstance(adv, dict):
        raise ValidationError(f"{path.name}: manifest has no 'adventure' section")

    bundle = Bundle(path, manifest, adv)
    bundle.size_bytes = path.stat().st_size
    bundle.sha256 = sha256_file(path)

    if not UUID_RE.match(bundle.origin_id):
        raise ValidationError(f"{path.name}: missing/invalid adventure.origin_id (need UUID)")
    if not bundle.title:
        raise ValidationError(f"{path.name}: missing adventure.title")
    if not bundle.adv_version:
        raise ValidationError(f"{path.name}: missing adventure.version")
    if not SLUG_RE.match(bundle.slug):
        raise ValidationError(f"{path.name}: title does not produce a valid slug {bundle.slug!r}")
    if bundle.size_bytes > MAX_ASSET_BYTES:
        raise ValidationError(
            f"{path.name}: {bundle.size_bytes} bytes exceeds 100 MiB asset limit"
        )

    with zipfile.ZipFile(path) as zf:
        _extract_cover(bundle, zf)
    return bundle


def scan_source(source: "Path") -> tuple[list[Bundle], list[str]]:
    """Recursively scan ``--source`` for adventure bundles (CWE-22 guarded)."""
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")

    bundles: list[Bundle] = []
    errors: list[str] = []
    seen: dict[str, str] = {}
    for root, _dirs, files in os.walk(source):
        base = Path(root)
        for name in sorted(files):
            if not (name.endswith(".adz") or name.endswith(".adv")):
                continue
            cand = resolve_within(source, base / name)
            if not cand.is_file():
                continue
            if name in seen:
                errors.append(f"{cand}: duplicate filename {name!r} also at {seen[name]}; skip")
                continue
            seen[name] = str(cand)
            try:
                bundles.append(scan_bundle(cand))
            except ValidationError as exc:
                errors.append(str(exc))
            except (zipfile.BadZipFile, OSError) as exc:
                errors.append(f"{cand}: cannot open bundle ({exc})")
    return bundles, errors


# --- Release classification -----------------------------------------------------

def load_releases(repo: str) -> dict[str, dict[str, Any]]:
    try:
        data = gh_json(
            ["release", "list"] + repo_args(repo)
            + ["--limit", "300", "--json", "tagName,assets"]
        )
    except RuntimeError:
        data = None

    if data is None:
        # Fallback to gh api: real gh CLI release list does not support --json assets
        try:
            api_data = gh_json(["api", f"/repos/{repo}/releases?per_page=100"])
            if isinstance(api_data, list):
                out: dict[str, dict[str, Any]] = {}
                for rel in api_data:
                    assets = {a.get("name"): a for a in (rel.get("assets") or [])}
                    tag = rel.get("tag_name") or rel.get("tagName")
                    if tag:
                        out[tag] = {"tag": tag, "assets": assets}
                return out
        except RuntimeError:
            data = []

    out: dict[str, dict[str, Any]] = {}
    for rel in data or []:
        assets = {a.get("name"): a for a in (rel.get("assets") or [])}
        out[rel.get("tagName")] = {"tag": rel.get("tagName"), "assets": assets}
    return out


def classify_bundle(bundle: Bundle, releases: dict[str, dict[str, Any]]) -> str:
    """Classify against existing release tags: new / unchanged / conflict.

    ``update`` is used when an older version of the same slug is published and
    this bundle is a newer version (a different tag).
    """
    tag = bundle.tag
    rel = releases.get(tag)
    if rel is None:
        for t in releases:
            if t.startswith(f"adv/{bundle.slug}/v"):
                return "update"
        return "new"
    asset = rel.get("assets", {}).get(bundle.asset_name)
    if not asset:
        return "new"  # tag exists but asset missing -> refill (idempotent)
    published_size = asset.get("size")
    if published_size == bundle.size_bytes:
        return "unchanged"
    return "conflict"


# --- Tracking issues -------------------------------------------------------------

def load_issues(repo: str) -> list[dict[str, Any]]:
    data = gh_json(
        ["issue", "list"] + repo_args(repo)
        + ["--label", ISSUE_LABEL, "--state", "all", "--json", "number,title,body,labels,state"]
    )
    return data or []


def build_issue_body(bundle: Bundle) -> str:
    marker = f"{ISSUE_MARKER_PREFIX}{bundle.origin_id}{ISSUE_MARKER_SUFFIX}"
    cov = "ja" if bundle.has_cover else f"nein ({bundle.cover_warning or 'kein Cover deklariert'})"
    return (
        f"{marker}\n\n"
        f"## {bundle.title}\n\n"
        f"- **origin_id**: `{bundle.origin_id}`\n"
        f"- **slug**: `{bundle.slug}`\n"
        f"- **version**: `{bundle.adv_version}`\n"
        f"- **format**: `{bundle.format_version}`\n"
        f"- **creator**: {bundle.creator or '-'}\n"
        f"- **license**: {bundle.license or '-'}\n"
        f"- **cover**: {cov}\n\n"
        f"### Release checklist\n\n"
        f"- [ ] Release `{bundle.tag}` erstellt\n"
        f"- [ ] Assets hochgeladen und verifiziert (sha256/size)\n"
        f"- [ ] `catalog.json` gemergt und committet\n"
        f"- [ ] Download/Import in der Anwendung geprüft\n"
    )


def find_issue_by_origin(issues: list[dict[str, Any]], origin_id: str) -> Optional[dict[str, Any]]:
    target = f"{ISSUE_MARKER_PREFIX}{origin_id}{ISSUE_MARKER_SUFFIX}"
    for issue in issues:
        if target in (issue.get("body") or ""):
            return issue
    return None


def ensure_issue(bundle: Bundle, repo: str, existing: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    issue = find_issue_by_origin(existing, bundle.origin_id)
    if issue is not None:
        return {"plan": "kept", "number": issue.get("number"), "title": issue.get("title")}
    if dry_run:
        return {"plan": "would_create", "title": f"Adventure: {bundle.title}"}
    created = gh_json(
        ["issue", "create"] + repo_args(repo)
        + ["--title", f"Adventure: {bundle.title}", "--body", build_issue_body(bundle)]
    )
    run_gh(["issue", "edit"] + repo_args(repo)
           + [str(created.get("number")), "--add-label", ISSUE_LABEL])
    return {"plan": "created", "number": created.get("number"), "title": created.get("title")}


# --- Catalog ---------------------------------------------------------------------

def load_catalog(repo: str, branch: str) -> dict[str, Any]:
    """Fetch catalog.json from the repo via gh api, or return a fresh catalog."""
    try:
        meta = gh_json(["api", f"/repos/{repo}/contents/{CATALOG_FILENAME}"])
    except RuntimeError:
        meta = None
    if not meta or not isinstance(meta, dict) or not meta.get("content"):
        return {"schema": 1, "generated_at": utc_now(), "generator": VERSION_STRING, "adventures": []}
    try:
        raw = base64.b64decode(meta["content"])
        return json.loads(raw)
    except Exception:
        return {"schema": 1, "generated_at": utc_now(), "generator": VERSION_STRING, "adventures": []}


def build_catalog_entry(bundle: Bundle, args: argparse.Namespace) -> dict[str, Any]:
    release_base = (
        f"https://github.com/{args.repo}/releases/download/"
        f"adv/{bundle.slug}/v{bundle.adv_version}"
    )
    entry: dict[str, Any] = {
        "id": bundle.origin_id,
        "slug": bundle.slug,
        "title": bundle.title,
        "teaser": (bundle.teaser[:300] if bundle.teaser else ""),
        "description": "",
        "version": bundle.adv_version,
        "format_version": bundle.format_version,
        "released_at": utc_now(),
        "min_app_version": args.min_app_version,
        "size_bytes": bundle.size_bytes,
        "sha256": bundle.sha256,
        "download_url": f"{release_base}/{bundle.asset_name}",
        "tags": [],
        "author": bundle.creator,
        "license": bundle.license,
        "language": bundle.language,
    }
    if bundle.has_cover:
        entry["cover_url"] = f"{release_base}/cover.png"
        entry["cover_sha256"] = bundle.cover_sha256
    return entry


def validate_catalog_entry(entry: dict[str, Any]) -> list[str]:
    """Check mandatory fields + all-or-nothing cover pair (schema 1 rules)."""
    problems: list[str] = []
    required = ("id", "slug", "version", "sha256", "size_bytes", "download_url")
    for field in required:
        if field not in entry or entry[field] in (None, ""):
            problems.append(f"missing mandatory field {field!r}")
    if entry.get("download_url") and not entry["download_url"].startswith("https://"):
        problems.append("download_url must be https")
    has_cover_url = bool("cover_url" in entry and entry["cover_url"])
    has_cover_sha = bool("cover_sha256" in entry and entry["cover_sha256"])
    if has_cover_url != has_cover_sha:
        problems.append("cover_url and cover_sha256 must be set or omitted together")
    if isinstance(entry.get("size_bytes"), int) and entry["size_bytes"] > MAX_ASSET_BYTES:
        problems.append("size_bytes exceeds 100 MiB")
    return problems


# --- Commit -----------------------------------------------------------------------

def commit_file(*, repo: str, branch: str, path: str, content: str, message: str) -> None:
    """Create or update a file on the default branch via gh api."""
    blob = base64.b64encode(content.encode("utf-8")).decode("ascii")
    body = {"message": message, "content": blob, "branch": branch}
    try:
        meta = gh_json(["api", f"/repos/{repo}/contents/{path}"])
        if meta and isinstance(meta, dict) and meta.get("sha"):
            body["sha"] = meta["sha"]
    except RuntimeError:
        pass  # file missing -> create

    proc = subprocess.run(
        ["gh", "api", "-X", "PUT", f"/repos/{repo}/contents/{path}", "--input", "-"],
        input=json.dumps(body),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"catalog commit failed:\n{proc.stderr.strip()}")


# --- Plan -------------------------------------------------------------------------

def run_plan(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    try:
        bundles, errors = scan_source(source)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    releases: dict[str, dict[str, Any]] = {}
    if not args.skip_release_check:
        try:
            releases = load_releases(args.repo)
        except RuntimeError as exc:
            print(f"WARNING: could not read releases ({exc})", file=sys.stderr)

    issues: list[dict[str, Any]] = []
    if not args.skip_issues and not args.dry_run:
        issues = load_issues(args.repo)

    has_conflict = False
    timeline = []
    for bundle in bundles:
        state = classify_bundle(bundle, releases)
        if state == "conflict":
            has_conflict = True
        timeline.append(
            {
                "origin_id": bundle.origin_id,
                "slug": bundle.slug,
                "title": bundle.title,
                "version": bundle.adv_version,
                "format_version": bundle.format_version,
                "size_bytes": bundle.size_bytes,
                "sha256": bundle.sha256,
                "tag": bundle.tag,
                "asset": bundle.asset_name,
                "state": state,
                "has_cover": bundle.has_cover,
                "cover_warning": bundle.cover_warning,
            }
        )

    issue_rows = []
    for bundle in bundles:
        if args.dry_run:
            issue_rows.append({"origin_id": bundle.origin_id, "plan": "dry-run"})
        else:
            issue_rows.append(
                {"origin_id": bundle.origin_id, "issue": ensure_issue(bundle, args.repo, issues, dry_run=False)}
            )

    plan = {
        "generator": VERSION_STRING,
        "generated_at": utc_now(),
        "repo": args.repo,
        "source": str(source),
        "bundles": timeline,
        "errors": errors,
        "issues": issue_rows,
        "dry_run": bool(args.dry_run),
    }

    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        print(f"scanned={len(bundles)} valid, {len(errors)} error(s)"
              + (", CONFLICT PRESENT" if has_conflict else ""))
        for b in timeline:
            cov = "ja" if b["has_cover"] else f"NEIN ({b['cover_warning'] or 'kein Cover'})"
            print(f"  [{b['state']:>9}] {b['slug']} v{b['version']} cover={cov}"
                  f"  ({b['size_bytes']} B, sha256 {b['sha256'][:12]}…)")
        if args.dry_run:
            print("(dry-run: keine Schreibvorgänge, keine Issues)")

    return 1 if (has_conflict or errors) else 0


# --- Publish ----------------------------------------------------------------------

def publish_bundle(bundle: Bundle, catalog_entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    notes = (
        f"Adventure **{bundle.title}** v{bundle.adv_version}\n\n"
        f"- origin_id: `{bundle.origin_id}`\n"
        f"- slug: `{bundle.slug}`\n"
        f"- sha256: `{catalog_entry['sha256']}`\n"
        f"- size: {bundle.size_bytes} bytes\n"
        f"- cover: {'ja' if bundle.has_cover else 'nein'}"
    )
    try:
        run_gh(
            ["release", "create", bundle.tag] + repo_args(args.repo)
            + ["--target", args.branch, "--title", f"{bundle.slug} v{bundle.adv_version}",
               "--notes", notes, "--latest=false"]
            + (["--prerelease"] if args.allow_prerelease else [])
            + (["--draft"] if args.draft else [])
        )
        release_created = True
    except RuntimeError as exc:
        if "already exists" in str(exc).lower():
            release_created = False
        else:
            raise

    with tempfile.TemporaryDirectory(prefix="adz-publish-") as tmp:
        tmpd = Path(tmp)
        adz = tmpd / bundle.asset_name
        shutil.copy2(bundle.path, adz)
        uploadable = [adz]
        if bundle.has_cover:
            cover = tmpd / "cover.png"
            cover.write_bytes(bundle.cover_bytes)
            uploadable.append(cover)
        entry = tmpd / "catalog-entry.json"
        entry.write_text(json.dumps(catalog_entry, indent=2))
        uploadable.append(entry)

        base = ["release", "upload", bundle.tag] + repo_args(args.repo)
        if args.force:
            base.append("--clobber")
        for a in uploadable:
            run_gh(base + [str(a)])

    # Re-verify by reading the release back.
    published = gh_json(
        ["release", "view", bundle.tag] + repo_args(args.repo)
        + ["--json", "assets,url"]
    )
    assets = {a["name"]: a for a in (published.get("assets") or [])}

    verified: dict[str, bool] = {}
    expect = {bundle.asset_name: bundle.size_bytes}
    if bundle.has_cover:
        expect["cover.png"] = len(bundle.cover_bytes)
    expect["catalog-entry.json"] = len(json.dumps(catalog_entry, indent=2).encode())

    for name, size in expect.items():
        asset = assets.get(name)
        if not asset:
            raise RuntimeError(f"{bundle.tag}: asset {name} missing after upload")
        if int(asset.get("size", -1)) != size:
            raise RuntimeError(
                f"{bundle.tag}: {name} size mismatch published={asset.get('size')} expected={size}"
            )
        verified[name] = True

    # Hash verification: re-download the .adz and compare sha256.
    with tempfile.TemporaryDirectory(prefix="adz-verify-") as vtmp:
        run_gh(["release", "download", bundle.tag] + repo_args(args.repo)
               + ["--pattern", bundle.asset_name, "--dir", vtmp])
        dl = Path(vtmp) / bundle.asset_name
        if not dl.exists():
            raise RuntimeError(f"{bundle.tag}: could not re-download {bundle.asset_name}")
        if sha256_file(dl) != bundle.sha256:
            raise RuntimeError(f"{bundle.tag}: sha256 mismatch after upload")

    return {"tag": bundle.tag, "created": release_created, "verified": sorted(verified)}


def run_publish(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    try:
        bundles, errors = scan_source(source)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("Validierungsfehler blockieren das Publizieren:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    if not args.yes:
        print("Trockenlauf: kein Release, keine Uploads, kein Katalog-Commit "
              "(echtes Publizieren braucht --yes).", file=sys.stderr)
        for b in bundles:
            entry = build_catalog_entry(b, args)
            problems = validate_catalog_entry(entry)
            status = "OK" if not problems else "; ".join(problems)
            print(f"  - {b.slug} v{b.adv_version}: {status} cover={'ja' if b.has_cover else 'nein'}")
        return 2

    catalog = load_catalog(args.repo, args.branch)
    by_id = {e.get("id"): e for e in catalog.get("adventures", [])}

    published_ids: list[str] = []
    reports: list[dict[str, Any]] = []
    for bundle in bundles:
        entry = build_catalog_entry(bundle, args)
        problems = validate_catalog_entry(entry)
        if problems:
            print(f"Katalog-Eintrag {bundle.slug} ungültig: {'; '.join(problems)}", file=sys.stderr)
            return 2
        report = publish_bundle(bundle, entry, args)
        reports.append(report)
        by_id[bundle.origin_id] = entry
        published_ids.append(bundle.origin_id)

    if args.prune:
        drop = [eid for eid in by_id if eid not in published_ids]
        if drop:
            for d in drop:
                print(f"--prune: entferne {d} ({by_id[d].get('slug')})")
            for d in drop:
                del by_id[d]

    catalog["schema"] = 1
    catalog["generated_at"] = utc_now()
    catalog["generator"] = VERSION_STRING
    catalog["adventures"] = sorted(by_id.values(), key=lambda e: e.get("slug", ""))

    commit_file(
        repo=args.repo,
        branch=args.branch,
        path=CATALOG_FILENAME,
        content=json.dumps(catalog, indent=2),
        message=f"chore(catalog): publish {len(published_ids)} adventure(s)",
    )

    print(f"publiziert {len(published_ids)} adventure(s); catalog.json updated auf {args.branch}")
    for r in reports:
        print(f"  ✔ {r['tag']} (created={r['created']}, verified={r['verified']})")
    return 0


# --- CLI -------------------------------------------------------------------------

def _default_repo() -> str:
    return os.environ.get(DEFAULT_REPO_ENV, DEFAULT_REPO)


def _default_source() -> str:
    return os.environ.get(DEFAULT_SOURCE_ENV, DEFAULT_SOURCE)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="publish_adventures.py",
        description="TaleWeaver adventure publisher (releases + catalog.json).",
    )
    p.add_argument("--version", action="version", version=VERSION_STRING)

    # Shared options available on every subcommand (spec: --source / --repo).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--source", default=_default_source(),
                        help=f"source bundle directory (default: {DEFAULT_SOURCE})")
    common.add_argument("--repo", default=_default_repo(),
                        help=f"distribution repository (default: ${DEFAULT_REPO_ENV} -> {DEFAULT_REPO})")
    common.add_argument("--branch", default=DEFAULT_BRANCH,
                        help=f"default branch (default: {DEFAULT_BRANCH})")
    common.add_argument("--min-app-version", default=DEFAULT_MIN_APP_VERSION,
                        help=f"min_app_version for published entries (default: {DEFAULT_MIN_APP_VERSION})")

    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("plan", parents=[common],
                        help="validate + classify + ensure tracking issues")
    pp.add_argument("--dry-run", action="store_true",
                    help="report only; no gh writes at all (issues/releases untouched)")
    pp.add_argument("--json", action="store_true", help="emit machine-readable plan")
    pp.add_argument("--skip-release-check", action="store_true",
                    help="do not query existing releases (classify everything as new/update)")
    pp.add_argument("--skip-issues", action="store_true", help="do not touch tracking issues")
    pp.set_defaults(func=run_plan)

    pub = sub.add_parser("publish", parents=[common],
                         help="create/update releases + merge catalog.json")
    pub.add_argument("--yes", action="store_true", help="really publish (required)")
    pub.add_argument("--force", action="store_true",
                     help="allow clobbering of existing release assets (--clobber)")
    pub.add_argument("--prune", action="store_true",
                     help="delete catalog entries not present in source")
    pub.add_argument("--allow-prerelease", action="store_true")
    pub.add_argument("--draft", action="store_true")
    pub.set_defaults(func=run_publish)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
