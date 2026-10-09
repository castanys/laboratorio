import session_pass as sp

STATUS = """GOAL: g
## OPEN (3)
1. `ALP-01` wins: x; serves GOAL: g [impact 8]
2. `BET-02` wins: y; serves GOAL: g [impact 8] [origin human]
3. `CHA-03` wins: z; serves GOAL: g [impact 9] [origin plan]
## DECISIONS (0)
## DONE (0)
"""


def test_only_items_with_a_human_origin_are_picked_and_first_wins():
    item = sp.pick_item(STATUS)
    assert item.id == "BET-02"


def test_item_without_origin_is_never_launched():
    assert sp.pick_item(STATUS.replace(" [origin human]", "").replace(" [origin plan]", "")) is None


def test_waiting_item_is_skipped_until_its_date():
    waiting = STATUS.replace("`BET-02` wins", "`BET-02` (since 2026-12-01) wins")
    assert sp.pick_item(waiting, today="2026-10-08").id == "CHA-03"
    assert sp.pick_item(waiting, today="2026-12-01").id == "BET-02"


def test_command_has_budget_and_model():
    cmd = sp.build_command("do BET-02", model="sonnet", budget=8)
    assert cmd[:2] == ["claude", "-p"] and "--max-budget-usd" in cmd and "8" in cmd
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_last_line_verdict():
    assert sp.verdict("blah\nDONE: PR #3 merged.\n") == "DONE"
    assert sp.verdict("x\nBLOCKED: need a token\n") == "BLOCKED"
    assert sp.verdict("x\nrandom\n") == "NONE"


def test_over_cap_launches_nothing_and_notifies_once(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    sent, ran = [], []
    out = sp.run_pass(str(tmp_path), usage={"seven_day": (99.0, "2099-01-01T00:00:00+00:00")},
                      launch=lambda *a, **k: ran.append(a), notify=sent.append)
    assert out.startswith("paused") and ran == [] and len(sent) == 1


def test_non_done_verdict_notifies(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    sent = []
    out = sp.run_pass(str(tmp_path), usage={}, launch=lambda item, repo: "BLOCKED: need X",
                      notify=sent.append)
    assert out == "BLOCKED" and sent and "BET-02" in sent[0]


# LAB-04: without --pct the pass reads the quota from the `claude` login; if it cannot be
# read it launches nothing (the cap is the point of the plugin) and says why.
def test_unreadable_quota_launches_nothing(tmp_path):
    (tmp_path / "STATUS.md").write_text(STATUS)
    sent, ran = [], []
    out = sp.run_pass(str(tmp_path), usage=None, launch=lambda *a, **k: ran.append(a),
                      notify=sent.append)
    assert out.startswith("paused") and "--pct" in out and ran == [] and len(sent) == 1


def test_main_reads_the_quota_when_no_pct_is_given(tmp_path, monkeypatch):
    (tmp_path / "STATUS.md").write_text(STATUS)
    seen = []
    monkeypatch.setattr(sp.weekly_cap, "read_usage",
                        lambda token=None: {"seven_day": (99.0, "2099-01-01T00:00:00+00:00")})
    monkeypatch.setattr(sp, "run_pass", lambda repo, usage: seen.append(usage) or "paused")
    sp.main([str(tmp_path)])
    assert seen == [{"seven_day": (99.0, "2099-01-01T00:00:00+00:00")}]
