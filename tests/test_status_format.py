import status_format as sf

GOOD = """GOAL: ship the plugin
## OPEN (1)
1. `PLG-01` wins: the check exits 0; serves GOAL: ship [impact 8] [origin human]
## DECISIONS (1)
- 2026-10-08: free plugin first.
## DONE (0)
"""


def test_good_file_passes():
    assert sf.check(GOOD) == []


def test_must_start_with_goal():
    assert any("GOAL:" in f for f in sf.check("# Title\n" + GOOD))


def test_sections_in_order_and_present():
    bad = GOOD.replace("## DONE (0)\n", "").replace("## OPEN (1)", "## DONE (0)\n## OPEN (1)")
    assert any("order" in f or "missing" in f for f in sf.check(bad))


def test_counter_must_match():
    assert any("says (3)" in f for f in sf.check(GOOD.replace("OPEN (1)", "OPEN (3)")))


def test_item_needs_stable_id_and_no_hash_id():
    bad = GOOD.replace("`PLG-01` ", "#12 ")
    out = sf.check(bad)
    assert any("stable id" in f for f in out) and any("#NN" in f for f in out)


def test_item_needs_wins_and_impact():
    out = sf.check(GOOD.replace("wins: the check exits 0; ", "").replace("[impact 8] ", ""))
    assert any("wins:" in f for f in out) and any("impact" in f for f in out)


def test_no_tables_and_line_cap():
    assert any("table" in f for f in sf.check(GOOD + "| a | b |\n|---|---|\n"))
    assert any("lines" in f for f in sf.check(GOOD + "- x\n" * 61))


def test_warns_when_decisions_pass_ten():
    many = GOOD.replace("- 2026-10-08: free plugin first.\n", "- d\n" * 11)
    assert any("DECISIONS" in w for w in sf.warnings(many))
