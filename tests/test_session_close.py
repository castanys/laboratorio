import pytest

import session_close as sc

STATUS = """GOAL: g
## OPEN (2)
1. `ALP-01` wins: x; serves GOAL: g [impact 8]
2. `BET-02` wins: y; serves GOAL: g [impact 6]
## DECISIONS (0)
## DONE (0)
"""


def test_close_item_moves_it_and_fixes_counters():
    new, hist = sc.close_item(STATUS, "ALP-01", "did it", 7, "2026-10-08", decision="chose z")
    assert "## OPEN (1)" in new and "`ALP-01` wins" not in new
    assert "1. `BET-02`" in new
    assert "## DONE (1)" in new and "1. `ALP-01` did it (PR #7, 2026-10-08)" in new
    assert "## DECISIONS (1)" in new and "- 2026-10-08: chose z" in new
    assert hist == ""


def test_done_keeps_last_ten_and_moves_rest_to_history():
    text = STATUS.replace("## DONE (0)\n", "## DONE (10)\n" + "".join(
        "%d. `O-%02d` old (PR #%d, 2026-01-01)\n" % (i, i, i) for i in range(1, 11)))
    new, hist = sc.close_item(text, "ALP-01", "did it", 7, "2026-10-08")
    assert "## DONE (10)" in new and "`O-09`" in new and "`O-10`" not in new
    assert "`O-10`" in hist


def test_unknown_item_raises():
    with pytest.raises(sc.CannotClose):
        sc.close_item(STATUS, "Z-99", "x", 1, "2026-10-08")


class Fake:
    def __init__(self, checks_state="SUCCESS", pr_open=True):
        self.calls = []
        self.state = checks_state
        self.pr_open = pr_open

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return 0, "feat/x\n"
        if cmd[:3] == ["gh", "pr", "view"] and "number,state" in cmd:
            return (0, '{"number": 7, "state": "OPEN"}') if self.pr_open else (1, "")
        if cmd[:3] == ["gh", "pr", "create"]:
            return 0, "https://github.com/o/r/pull/7\n"
        if cmd[:3] == ["gh", "pr", "view"] and "statusCheckRollup" in cmd:
            return 0, '{"statusCheckRollup": [{"name": "t", "status": "COMPLETED", "conclusion": "%s"}]}' % self.state
        return 0, ""


def test_red_ci_never_merges(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    run = Fake("FAILURE")
    with pytest.raises(sc.CannotClose) as e:
        sc.close(str(tmp_path), "ALP-01", "feat: x", "body", "did it", run=run, today="2026-10-08")
    assert "CI" in str(e.value)
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in run.calls)


def test_green_ci_merges_and_returns_last_line(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    run = Fake()
    out = sc.close(str(tmp_path), "ALP-01", "feat: x", "body", "did it", run=run, today="2026-10-08")
    assert out == "DONE: PR #7 merged."
    assert any(c[:3] == ["gh", "pr", "merge"] and "--squash" in c for c in run.calls)
    assert "## DONE (1)" in (tmp_path / "STATUS.md").read_text()


def test_refuses_to_close_from_main(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    run = Fake()
    orig = run.__call__
    run2 = lambda cmd, cwd=None: (0, "main\n") if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"] else orig(cmd, cwd)
    with pytest.raises(sc.CannotClose):
        sc.close(str(tmp_path), "ALP-01", "feat: x", "b", "c", run=run2, today="2026-10-08")
