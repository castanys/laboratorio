"""LAB-06: what goes public is a fresh tree built from this repo, without its working files
(their history would leak them if this repo were made public as is), and whose own suite
passes there; the CI never runs a fork's pull request on the self-hosted runner."""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, "scripts", "exporta_publico.sh")
INTERNAL = ("STATUS.md", "HISTORICO.md", "DEMANDA.md", "CLAUDE.md", "ERRORES_REPORTADOS.md",
            "LECCIONES.md", "pcc.yml", ".privacy-deny")
PUBLIC = ("README.md", "README.es.md", "LICENSE", ".claude-plugin/plugin.json",
          ".claude-plugin/marketplace.json", ".github/workflows/ci.yml", ".claude/test.sh",
          "scripts/weekly_cap.py", "scripts/comprueba_privacidad.sh", "tests/conftest.py")
EXPORTED = os.environ.get("LAB_EXPORTED") == "1"


def export(dest):
    return subprocess.run(["bash", EXPORT, str(dest)], capture_output=True, text=True)


@pytest.mark.skipif(EXPORTED, reason="already inside an exported tree")
def test_export_leaves_out_the_working_files_and_keeps_the_plugin(tmp_path):
    dest = tmp_path / "public"
    r = export(dest)
    assert r.returncode == 0, r.stdout + r.stderr
    for name in INTERNAL:
        assert not (dest / name).exists(), name
    for name in PUBLIC:
        assert (dest / name).is_file(), name
    assert os.access(dest / ".claude" / "test.sh", os.R_OK)
    assert os.access(dest / "hooks" / "pre-push", os.X_OK)


@pytest.mark.skipif(EXPORTED, reason="already inside an exported tree")
def test_export_refuses_a_non_empty_destination(tmp_path):
    (tmp_path / "old.txt").write_text("x\n")
    r = export(tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert (tmp_path / "old.txt").read_text() == "x\n"


@pytest.mark.skipif(EXPORTED, reason="already inside an exported tree")
def test_exported_tree_passes_its_own_suite(tmp_path):
    dest = tmp_path / "public"
    assert export(dest).returncode == 0
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    env = dict(os.environ, LAB_EXPORTED="1")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:cacheprovider"],
                       cwd=dest, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_ci_never_runs_a_fork_or_the_public_repo_on_the_own_runner():
    ci = open(os.path.join(ROOT, ".github", "workflows", "ci.yml")).read()
    assert "pull_request_target" not in ci
    runs_on = re.findall(r"^\s*runs-on:\s*(.+)$", ci, re.M)
    assert runs_on, "no runs-on"
    for line in runs_on:
        assert line.strip() != "self-hosted", "unconditional self-hosted runner"
        if "self-hosted" in line:
            assert "github.event.repository.private" in line, line
            assert "!github.event.pull_request.head.repo.fork" in line, line
            assert "'ubuntu-latest'" in line, line


def published_files():
    out = subprocess.run(["bash", os.path.join(ROOT, "scripts", "comprueba_privacidad.sh"), "--list"],
                         capture_output=True, text=True, check=True).stdout
    files = [f for f in out.splitlines() if os.path.isfile(os.path.join(ROOT, f))]
    if not files:  # an exported tree not yet committed: every file in it is published
        skip = {".git", ".venv", "__pycache__", ".pytest_cache"}
        for d, dirs, names in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in skip]
            files += [os.path.relpath(os.path.join(d, n), ROOT) for n in names]
    return files


def test_published_tree_meets_the_official_directory_checklist():
    """The blocking rows of claude.com/docs/plugins/pre-submission-checklist (2026-10-09)."""
    files = published_files()
    manifest = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    name = manifest["name"]
    assert re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?", name), name
    assert name not in ("claude", "anthropic", "official", "plugin", "mcp", "test"), name
    assert all(manifest.get(k) for k in ("description", "author", "version", "license"))
    readme = re.sub(r"```.*?```", "", open(os.path.join(ROOT, "README.md")).read(), flags=re.S)
    assert len(readme.split()) >= 40
    assert "LICENSE" in files
    assert len(files) <= 512
    for f in files:
        base = os.path.basename(f)
        assert base not in (".DS_Store", "Thumbs.db", "desktop.ini") and "__MACOSX" not in f, f
        assert not os.path.islink(os.path.join(ROOT, f)), f
        assert os.path.getsize(os.path.join(ROOT, f)) < 256 * 1024, f
    assert len({f.lower() for f in files}) == len(files), "names differing only by case"
    if "hooks/hooks.json" in files:
        assert "hooks" in json.load(open(os.path.join(ROOT, "hooks", "hooks.json")))
