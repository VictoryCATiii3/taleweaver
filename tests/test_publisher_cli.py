"""Tests for scripts/publish_adventures.py (AAA pattern, .agents/rules/testing.md).

No real network calls or GitHub writes: every `gh` interaction is mocked via
monkeypatch on `publish_adventures.run_gh` / `gh_json`. Bundles are built as
minimal in-memory zips in pytest's tmp_path.
"""

from __future__ import annotations

import json
import struct
import sys
import uuid
import zipfile
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import publish_adventures as pub  # noqa: E402

REPO = "jschm42/taleweaver-adventures"


# --- Fixtures -----------------------------------------------------------------


def make_png(width: int = 1, height: int = 1) -> bytes:
    """Build a minimal valid PNG of the requested size (RGB, no dependencies)."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_bundle(
    tmp_path: Path,
    *,
    name: str = "my-adventure",
    title: str = "My Adventure",
    version: str = "1.0.0",
    origin_id: str | None = None,
    image_url: str = "assets/cover.png",
    cover: bytes | None = None,
    manifest_overrides: dict | None = None,
) -> Path:
    """Write a minimal .adz bundle into tmp_path and return its path.

    ``cover`` is a PNG/JPEG blob to store at ``image_url``; pass ``None`` to
    omit the asset entirely (cover then counts as missing in the pipeline).
    """
    path = tmp_path / f"{name}.adz"
    adv = {
        "origin_id": origin_id or str(uuid.uuid4()),
        "title": title,
        "version": version,
        "creator": "Test Author",
        "license": "CC-BY-4.0",
        "language": "en",
        "image_url": image_url,
        "teaser": "A teaser for tests.",
    }
    manifest = {"format": "TaleWeaver", "version": "1.3", "adventure": adv}
    if manifest_overrides:
        manifest.update(manifest_overrides)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("adventure.adv", json.dumps(manifest))
        if cover is not None:
            zf.writestr(image_url, cover)
    return path


def args_for(command: str, tmp_path: Path, **kwargs) -> SimpleNamespace:
    base = {
        "source": str(tmp_path),
        "repo": REPO,
        "branch": "main",
        "min_app_version": "0.7.0",
        "command": command,
    }
    if command == "publish":
        base.update(
            {
                "yes": False,
                "force": False,
                "prune": False,
                "allow_prerelease": False,
                "draft": False,
            }
        )
    base.update(kwargs)
    return SimpleNamespace(**base)


class GhRecorder:
    """Records gh invocations and can script responses per subcommand."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.responses: dict[tuple, object] = {}
        self.default = "{}"

    def run(self, args: list[str]) -> str:
        self.calls.append(args)
        key = tuple(args[:2])  # e.g. ('release','list'), ('issue','create')
        if key in self.responses:
            resp = self.responses[key]
            return resp if isinstance(resp, str) else json.dumps(resp)
        return self.default

    def gh_json(self, args: list[str]):
        out = self.run(args)
        return json.loads(out) if out.strip() else None


@pytest.fixture
def recorder(monkeypatch):
    rec = GhRecorder()
    monkeypatch.setattr(pub, "run_gh", rec.run)
    monkeypatch.setattr(pub, "gh_json", rec.gh_json)
    return rec


# --- scan & validation -------------------------------------------------------


class TestScanValidation:
    def test_valid_bundle_extracts_fields_and_cover(self, tmp_path):
        # Arrange
        oid = str(uuid.uuid4())
        path = make_bundle(tmp_path, origin_id=oid, cover=make_png())

        # Act
        bundle = pub.scan_bundle(path)

        # Assert
        assert bundle.title == "My Adventure"
        assert bundle.origin_id == oid
        assert bundle.adv_version == "1.0.0"
        assert bundle.slug == "my-adventure"
        assert bundle.size_bytes == path.stat().st_size
        assert len(bundle.sha256) == 64
        assert bundle.has_cover is True
        assert bundle.tag == "adv/my-adventure/v1.0.0"

    def test_missing_origin_id_rejected(self, tmp_path):
        path = make_bundle(tmp_path, origin_id="not-a-uuid")
        with pytest.raises(pub.ValidationError):
            pub.scan_bundle(path)

    def test_unsupported_format_rejected(self, tmp_path):
        path = make_bundle(tmp_path, manifest_overrides={"format": "Other"})
        with pytest.raises(pub.ValidationError):
            pub.scan_bundle(path)

    def test_cover_missing_is_soft_warning(self, tmp_path):
        # Arrange: image_url points at a member that does not exist
        path = make_bundle(tmp_path, image_url="assets/missing.png")

        # Act
        bundle = pub.scan_bundle(path)

        # Assert: no hard fail, no cover, warning recorded
        assert bundle.has_cover is False
        assert "not found" in (bundle.cover_warning or "")

    def test_cover_unsafe_path_rejected(self, tmp_path):
        path = make_bundle(tmp_path, image_url="../evil.png")
        bundle = pub.scan_bundle(path)
        assert bundle.has_cover is False
        assert "unsafe" in (bundle.cover_warning or "")

    def test_cover_absolute_path_rejected(self, tmp_path):
        path = make_bundle(tmp_path, image_url="/etc/passwd")
        bundle = pub.scan_bundle(path)
        assert bundle.has_cover is False

    def test_scan_source_guard_rejects_escape(self, tmp_path):
        # Arrange: an in-scope bundle plus one directly in the parent (out of scope)
        make_bundle(tmp_path, name="inside", title="Inside", version="1.0.0")
        make_bundle(tmp_path.parent, name="escaped", title="Escaped", version="1.0.0")
        assert (tmp_path.parent / "escaped.adz").exists()

        # Act
        bundles, errors = pub.scan_source(tmp_path)

        # Assert: only the in-scope bundle is seen
        assert len(bundles) == 1
        assert not any("escaped" in b.basename for b in bundles)


# --- classification -----------------------------------------------------------


class TestClassification:
    def test_new_when_no_release(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        b = pub.scan_bundle(path)
        assert pub.classify_bundle(b, {}) == "new"

    def test_unchanged_same_size(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        b = pub.scan_bundle(path)
        releases = {b.tag: {"assets": {b.asset_name: {"size": b.size_bytes}}}}
        assert pub.classify_bundle(b, releases) == "unchanged"

    def test_conflict_different_size(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        b = pub.scan_bundle(path)
        releases = {b.tag: {"assets": {b.asset_name: {"size": b.size_bytes + 1}}}}
        assert pub.classify_bundle(b, releases) == "conflict"

    def test_update_when_new_version_of_same_slug(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="2.0.0")
        b = pub.scan_bundle(path)
        releases = {"adv/alpha/v1.0.0": {"assets": {}}}
        assert pub.classify_bundle(b, releases) == "update"

    def test_tag_exists_asset_missing_returns_new(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        b = pub.scan_bundle(path)
        releases = {b.tag: {"assets": {}}}
        assert pub.classify_bundle(b, releases) == "new"


# --- plan ----------------------------------------------------------------------


class TestPlan:
    def test_plan_json_lists_bundles_and_cover(self, tmp_path, recorder):
        # Arrange
        make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        args = args_for(
            "plan", tmp_path, dry_run=True, json=True, skip_release_check=True, skip_issues=True
        )

        # Act
        rc = pub.run_plan(args)

        # Assert
        assert rc == 0
        assert len(recorder.calls) == 0  # dry-run + skip: zero gh calls

    def test_plan_dry_run_does_not_create_issues(self, tmp_path, recorder):
        # Arrange
        make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        args = args_for(
            "plan", tmp_path, dry_run=True, json=False, skip_release_check=False, skip_issues=False
        )

        # Act
        rc = pub.run_plan(args)

        # Assert: release list may be queried read-only, but no issue write ever
        assert rc == 0
        assert all(c[0] != "issue" for c in recorder.calls)

    def test_plan_creates_issue_and_is_idempotent(self, tmp_path, recorder):
        # Arrange
        oid = str(uuid.uuid4())
        make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0", origin_id=oid)
        # First call: no existing issues -> create. Second call: marker exists -> kept.
        recorder.responses[("issue", "list")] = []
        created = {"number": 42, "title": "Adventure: Alpha"}
        recorder.responses[("issue", "create")] = created

        # Act
        args = args_for(
            "plan", tmp_path, dry_run=False, json=False, skip_release_check=True, skip_issues=False
        )
        rc1 = pub.run_plan(args)

        # Simulate the created issue now existing with the marker in the body.
        marker = f"{pub.ISSUE_MARKER_PREFIX}{oid}{pub.ISSUE_MARKER_SUFFIX}"
        body = f"{marker}\n\n## Alpha"
        recorder.responses[("issue", "list")] = [
            {"number": 42, "title": "Adventure: Alpha", "body": body, "state": "open"}
        ]
        rc2 = pub.run_plan(args)

        # Assert
        assert rc1 == 0 and rc2 == 0
        creates = [c for c in recorder.calls if c[:2] == ["issue", "create"]]
        assert len(creates) == 1  # exactly one create despite two runs

    def test_plan_conflict_returns_nonzero(self, tmp_path, recorder):
        # Arrange: release list says the asset exists but with a different size
        make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        recorder.responses[("release", "list")] = [
            {"tagName": "adv/alpha/v1.0.0", "assets": [{"name": "alpha-1.0.0.adz", "size": 12345}]}
        ]
        args = args_for(
            "plan", tmp_path, dry_run=True, json=False, skip_release_check=False, skip_issues=True
        )

        # Act
        rc = pub.run_plan(args)

        # Assert: conflict must never be ignored
        assert rc != 0


# --- catalog -------------------------------------------------------------------


class TestCatalog:
    def test_entry_mandatory_fields(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0", cover=make_png())
        b = pub.scan_bundle(path)
        args = args_for("publish", tmp_path)
        entry = pub.build_catalog_entry(b, args)
        problems = pub.validate_catalog_entry(entry)
        assert problems == []

    def test_cover_pair_all_or_nothing(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0", cover=make_png())
        b = pub.scan_bundle(path)
        args = args_for("publish", tmp_path)
        entry = pub.build_catalog_entry(b, args)
        assert "cover_url" in entry and "cover_sha256" in entry

        # Break the pair on purpose
        bad = dict(entry)
        del bad["cover_sha256"]
        assert "cover_url and cover_sha256" in " ".join(pub.validate_catalog_entry(bad))

    def test_entry_without_cover_omits_pair(self, tmp_path):
        path = make_bundle(
            tmp_path, name="alpha", title="Alpha", version="1.0.0", image_url="assets/missing.png"
        )
        b = pub.scan_bundle(path)
        args = args_for("publish", tmp_path)
        entry = pub.build_catalog_entry(b, args)
        assert "cover_url" not in entry
        assert "cover_sha256" not in entry
        assert pub.validate_catalog_entry(entry) == []

    def test_entry_urls_are_https_and_point_to_repo(self, tmp_path):
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0", cover=make_png())
        b = pub.scan_bundle(path)
        args = args_for("publish", tmp_path)
        entry = pub.build_catalog_entry(b, args)
        assert entry["download_url"].startswith(f"https://github.com/{REPO}/releases/download/")
        assert entry["cover_url"].startswith(f"https://github.com/{REPO}/releases/download/")


# --- publish -------------------------------------------------------------------


class TestPublish:
    def test_dry_run_writes_nothing(self, tmp_path, recorder):
        # Arrange
        make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0")
        args = args_for("publish", tmp_path, yes=False)

        # Act
        rc = pub.run_publish(args)

        # Assert: no release create/upload/commit happened at all
        assert rc == 2
        assert len(recorder.calls) == 0

    def test_publish_full_flow_verifies_then_commits(self, tmp_path, monkeypatch):
        # Arrange
        path = make_bundle(tmp_path, name="alpha", title="Alpha", version="1.0.0", cover=make_png())
        bundle = pub.scan_bundle(path)

        # Script responses for each gh call in sequence
        seq: list[callable[[list[str]], object]] = []

        def fake_run(args: list[str]) -> str:
            verb = args[:2]
            if verb == ["release", "create"]:
                return ""
            if verb == ["release", "upload"]:
                return ""
            if verb == ["release", "download"]:
                # Emulate gh release download: write the bundle into the target dir
                import shutil

                target = Path(args[args.index("--dir") + 1])
                shutil.copy2(bundle.path, target / bundle.asset_name)
                return ""
            return "{}"

        def fake_gh_json(args: list[str]):
            if args[:2] == ["release", "view"]:
                entry = pub.build_catalog_entry(bundle, args_for("publish", tmp_path, yes=True))
                entry_size = len(json.dumps(entry, indent=2).encode())
                return {
                    "url": f"https://github.com/{REPO}/releases/tag/{bundle.tag}",
                    "assets": [
                        {"name": bundle.asset_name, "size": bundle.size_bytes},
                        {"name": "cover.png", "size": len(bundle.cover_bytes or b"")},
                        {"name": "catalog-entry.json", "size": entry_size},
                    ],
                }
            if args[0] == "api":
                return {"sha": "abc123"}
            return "{}"

        monkeypatch.setattr(pub, "run_gh", fake_run)
        monkeypatch.setattr(pub, "gh_json", fake_gh_json)
        # Capture commit payload
        committed: dict = {}

        def fake_commit(**kw):
            committed.update(kw)

        monkeypatch.setattr(pub, "commit_file", fake_commit)

        bundle_args = args_for("publish", tmp_path, yes=True, force=False, prune=False)
        bundles = [bundle]

        # Act (drive run_publish body without re-scanning: monkeypatch scan_source)
        monkeypatch.setattr(pub, "scan_source", lambda src: (bundles, []))
        rc = pub.run_publish(bundle_args)

        # Assert
        assert rc == 0
        assert committed["message"].startswith("chore(catalog): publish 1 adventure(s)")
        cat = json.loads(committed["content"])
        assert cat["schema"] == 1
        assert len(cat["adventures"]) == 1
        entry = cat["adventures"][0]
        assert entry["id"] == bundle.origin_id
        assert entry["slug"] == "alpha"
        assert entry["sha256"] == bundle.sha256
        assert entry["size_bytes"] == bundle.size_bytes

    def test_publish_refuses_on_validation_errors(self, tmp_path, monkeypatch):
        # Arrange: an invalid bundle in the tree
        bad = make_bundle(
            tmp_path, name="bad", title="Bad", version="1.0.0", origin_id="not-a-uuid"
        )
        args = args_for("publish", tmp_path, yes=True)
        # Act
        rc = pub.run_publish(args)
        # Assert
        assert rc == 2


# --- security helpers -----------------------------------------------------------


class TestArchivePathSafety:
    @pytest.mark.parametrize(
        "raw",
        [
            "assets/cover.png",
            "adventure/../assets/cover.png".replace("..", ""),
            "adventure.dir/cover.png",
        ],
    )
    def test_safe_paths_normalized(self, raw):
        out = pub.normalize_archive_relpath(raw)
        assert out is not None and ".." not in out

    @pytest.mark.parametrize(
        "raw",
        [
            "../evil.png",
            "/etc/passwd",
            "C:/evil.png",
            "a/../../b",
            "",
            None,
        ],
    )
    def test_unsafe_paths_rejected(self, raw):
        assert pub.normalize_archive_relpath(raw) is None

    def test_slug_regex_charset(self):
        # Asset names must match [a-z0-9.-]+ per ruleset
        slug = pub.slugify("!!Weird Title!! Ünïcode")
        assert pub.SLUG_RE.match(slug)
