import datetime as dt
import io
import os

import weekly_cap as wc

RENEWS = dt.datetime(2026, 10, 11, 18, 0, tzinfo=dt.timezone.utc)


def at(days):
    return RENEWS - dt.timedelta(days=7) + dt.timedelta(days=days, hours=1)


def test_cap_grows_by_day_and_never_passes_the_share():
    caps = [wc.cap_today(RENEWS, at(d), reserve=15, margin=5)[0] for d in range(7)]
    assert caps == sorted(caps)
    assert abs(caps[0] - (85 / 7 + 5)) < 1e-9
    assert caps[-1] == 85


def test_pause_reason_when_over_todays_cap():
    reason = wc.pause_reason({"seven_day": (40.0, RENEWS.isoformat())}, now=at(0))
    assert reason and "week" in reason


def test_no_reason_when_under_cap_or_unknown():
    assert wc.pause_reason({"seven_day": (10.0, RENEWS.isoformat())}, now=at(0)) is None
    assert wc.pause_reason({}, now=at(0)) is None


def test_reserve_stops_even_on_the_last_day():
    assert wc.pause_reason({"seven_day": (86.0, RENEWS.isoformat())}, now=at(6))


def test_cli_exit_code(capsys):
    assert wc.main(["--pct", "10", "--renews", RENEWS.isoformat(), "--now", at(3).isoformat()]) == 0
    assert wc.main(["--pct", "90", "--renews", RENEWS.isoformat(), "--now", at(3).isoformat()]) == 1
    assert "week" in capsys.readouterr().out


# LAB-04: the weekly percentage and the renewal time are read from the usage endpoint
# instead of being typed by hand. The fixture is the shape of a real reply (2026-10-09), cut
# down.
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "usage_response.json")
with open(FIXTURE, "rb") as _f:
    BODY = _f.read()


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_from(body, seen=None):
    def opener(req, timeout=None):
        if seen is not None:
            seen.append(req)
        return Reply(body)
    return opener


def test_read_usage_sends_the_given_token(monkeypatch):
    monkeypatch.delenv(wc.TOKEN_ENV, raising=False)
    seen = []
    usage = wc.read_usage(opener_from(BODY, seen), token="tok-fake")
    assert usage == {"seven_day": (43.0, "2026-10-11T18:00:00.178275+00:00")}
    assert seen[0].full_url == wc.URL
    assert seen[0].get_header("Authorization") == "Bearer tok-fake"


def test_read_usage_none_without_token_or_on_a_bad_reply(monkeypatch):
    monkeypatch.delenv(wc.TOKEN_ENV, raising=False)
    assert wc.read_usage(opener_from(BODY)) is None
    assert wc.read_usage(opener_from(b"not json"), token="t") is None
    assert wc.read_usage(opener_from(b'{"seven_day": null}'), token="t") is None


# LAB-09 (2026-10-09): the directory's review held the submission for "Uses a credential
# from the user's machine" (2 findings: the login file and the macOS keychain) and asked for
# a sensitive user_config option instead. Expected: the token is handed over by the user
# (the plugin option, exported to the plugin's processes, or a command of theirs) and no
# published file reads the login store. The forbidden strings are built in pieces so this
# file stays clean.
FORBIDDEN = (".credentials" + ".json", "find-generic-" + "password", "claudeAi" + "Oauth")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_read_usage_takes_the_plugin_option_from_the_environment(monkeypatch):
    monkeypatch.setenv(wc.TOKEN_ENV, "tok-env")
    seen = []
    assert wc.read_usage(opener_from(BODY, seen))["seven_day"][0] == 43.0
    assert seen[0].get_header("Authorization") == "Bearer tok-env"


def test_token_cmd_is_what_the_users_command_prints():
    assert wc.token_from_cmd("echo tok-cmd") == "tok-cmd"
    assert wc.token_from_cmd("echo ''") is None
    assert wc.token_from_cmd("exit 3") is None
    assert wc.token_from_cmd(None) is None


def test_cli_hands_the_token_cmd_result_to_the_reading(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(wc, "read_usage", lambda token=None: seen.append(token) or
                        {"seven_day": (10.0, RENEWS.isoformat())})
    assert wc.main(["--token-cmd", "echo tok-cmd", "--now", at(3).isoformat()]) == 0
    assert seen == ["tok-cmd"]
    assert "10 %" in capsys.readouterr().out


def test_no_published_file_reads_the_login_store():
    for d in ("scripts", "commands", "hooks", "tests", "README.md", "README.es.md"):
        path = os.path.join(ROOT, d)
        files = [path] if os.path.isfile(path) else [
            os.path.join(r, n) for r, _, names in os.walk(path) for n in names
            if not n.endswith((".pyc", ".png"))]
        for f in files:
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for bad in FORBIDDEN:
                assert bad not in text, (os.path.relpath(f, ROOT), bad)


def test_cli_reads_the_usage_when_no_pct_is_given(monkeypatch, capsys):
    monkeypatch.setattr(wc, "read_usage", lambda token=None: {"seven_day": (90.0, RENEWS.isoformat())})
    assert wc.main(["--now", at(3).isoformat()]) == 1
    assert "90 %" in capsys.readouterr().out
    monkeypatch.setattr(wc, "read_usage", lambda token=None: {"seven_day": (10.0, RENEWS.isoformat())})
    assert wc.main(["--now", at(3).isoformat()]) == 0
    assert "10 %" in capsys.readouterr().out


def test_cli_exit_2_when_usage_cannot_be_read(monkeypatch, capsys):
    monkeypatch.setattr(wc, "read_usage", lambda token=None: None)
    assert wc.main([]) == 2
    out = capsys.readouterr().out
    assert "--pct" in out and "--token-cmd" in out


def test_renewal_shown_to_the_minute_despite_jittering_seconds(monkeypatch, capsys):
    # The endpoint gives 17:59:59.74 one call and 18:00:00.18 the next: both are 18:00.
    monkeypatch.setattr(wc, "read_usage",
                        lambda token=None: {"seven_day": (10.0, "2026-10-11T17:59:59.743958+00:00")})
    assert wc.main(["--now", at(3).isoformat()]) == 0
    assert "2026-10-11 18:00 UTC" in capsys.readouterr().out
