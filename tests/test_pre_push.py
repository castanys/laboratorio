import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "pre-push")
ZERO = "0" * 40


def push(line):
    return subprocess.run(["sh", HOOK, "origin", "x"], input=line, capture_output=True, text=True)


def test_blocks_updating_or_deleting_main():
    assert push("refs/heads/x abc refs/heads/main def\n").returncode == 1
    assert push("(delete) %s refs/heads/master def\n" % ZERO).returncode == 1


def test_allows_branches_tags_and_first_push():
    assert push("refs/heads/x abc refs/heads/feat/x %s\n" % ZERO).returncode == 0
    assert push("refs/tags/v1 abc refs/tags/v1 %s\n" % ZERO).returncode == 0
    assert push("refs/heads/main abc refs/heads/main %s\n" % ZERO).returncode == 0
