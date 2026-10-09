import json
import os
import struct
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_plugin_manifest_is_valid_json_with_name():
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
        data = json.load(f)
    assert data["name"] == "laboratorio" and data["version"]


def test_both_readmes_exist_and_are_in_their_language():
    en = open(os.path.join(ROOT, "README.md")).read()
    es = open(os.path.join(ROOT, "README.es.md")).read()
    assert "Install" in en and "Instalación" in es
    assert "README.es.md" in en and "README.md" in es


# 2026-10-09 (LAB-05): following the README in an empty repo, `claude plugin marketplace add`
# failed with "Marketplace file not found at …/.claude-plugin/marketplace.json" and
# `claude plugin validate --strict` failed on "No author information provided".
# Expected: the repo is its own marketplace listing this plugin, and the manifest has an author.
def test_repo_is_its_own_marketplace_listing_the_plugin():
    with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")) as f:
        market = json.load(f)
    plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    assert market["name"] and market["owner"]["name"]
    listed = {p["name"]: p for p in market["plugins"]}
    assert listed[plugin["name"]]["source"] == "./"


def test_manifest_has_author():
    plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    assert plugin["author"]["name"]


# 2026-10-09 (LAB-05): in an empty repo, after the README install, `python3 scripts/weekly_cap.py …`
# exited 2 ("can't open file …/scripts/weekly_cap.py") and `bash ./laboratorio/scripts/install_hooks.sh`
# exited 127: the plugin lands in a versioned cache, not in the user's repo.
# Expected: install clones to one fixed folder and every command runs scripts from that folder.
CLONE = "~/laboratorio"


def _commands(text):
    blocks = re.findall(r"```sh\n(.*?)```", text, re.S)
    inline = re.findall(r"`((?:python3|bash) [^`]+)`", text)
    return [line for b in blocks for line in b.splitlines() if line.strip()] + inline


def test_readme_commands_run_from_any_repo():
    for name in ("README.md", "README.es.md"):
        text = open(os.path.join(ROOT, name)).read()
        cmds = _commands(text)
        assert f"git clone https://github.com/castanys/laboratorio {CLONE}" in cmds, name
        assert f"claude plugin marketplace add {CLONE}" in cmds, name
        for cmd in cmds:
            if cmd.startswith("bash .claude/") or "comprueba_privacidad" in cmd:
                continue  # Develop section: run inside the clone
            for path in re.findall(r"(\S*scripts/\S+\.(?:py|sh))", cmd):
                assert path.startswith(CLONE + "/scripts/"), f"{name}: {cmd}"
                assert os.path.exists(os.path.join(ROOT, path[len(CLONE) + 1:])), path


# 2026-10-09 (LAB-09): the directory's validation of castanys/laboratorio@main warned
# "No icon" (the first save fixes the listing icon for good: square PNG, 512-2048 px, under
# 2 MB) and held the submission for "Uses a credential from the user's machine" asking for a
# user_config option with sensitive: true. Expected: a square PNG at the path `icon` names,
# and the token declared as a sensitive option.
def test_manifest_icon_is_a_square_png_within_the_directory_limits():
    plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    assert plugin["icon"].startswith("./")
    path = os.path.join(ROOT, plugin["icon"])
    assert os.path.getsize(path) < 2 * 1024 * 1024
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", head[16:24])
    assert width == height and 512 <= width <= 2048


def test_manifest_asks_for_the_usage_token_instead_of_reading_it():
    plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    option = plugin["userConfig"]["usage_token"]
    assert option["type"] == "string" and option["sensitive"] is True
    assert option["title"] and option["description"]
