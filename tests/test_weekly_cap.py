import datetime as dt

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


# LAB-04: the weekly percentage and the renewal time are read from the `claude` login
# instead of being typed by hand. The fixture is the shape of a real reply of the usage
# endpoint (2026-10-09), cut down.
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "usage_response.json")
LOGIN = {"claudeAiOauth": {"accessToken": "tok-fake", "refreshToken": "r", "expiresAt": 1}}


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


def write_login(tmp_path, data=LOGIN):
    path = tmp_path / ".credentials.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_read_usage_takes_the_week_from_the_login(tmp_path):
    with open(FIXTURE, "rb") as f:
        body = f.read()
    seen = []
    usage = wc.read_usage(opener_from(body, seen), credentials=write_login(tmp_path),
                          keychain=lambda: None)
    assert usage == {"seven_day": (43.0, "2026-10-11T18:00:00.178275+00:00")}
    assert seen[0].full_url == wc.URL
    assert seen[0].get_header("Authorization") == "Bearer tok-fake"


def test_read_usage_none_without_login_or_on_a_bad_reply(tmp_path):
    with open(FIXTURE, "rb") as f:
        body = f.read()
    assert wc.read_usage(opener_from(body), credentials=str(tmp_path / "missing"),
                         keychain=lambda: None) is None
    assert wc.read_usage(opener_from(b"not json"), credentials=write_login(tmp_path),
                         keychain=lambda: None) is None
    assert wc.read_usage(opener_from(b'{"seven_day": null}'), credentials=write_login(tmp_path),
                         keychain=lambda: None) is None


def test_read_usage_falls_back_to_the_macos_keychain(tmp_path):
    with open(FIXTURE, "rb") as f:
        body = f.read()
    seen = []
    usage = wc.read_usage(opener_from(body, seen), credentials=str(tmp_path / "missing"),
                          keychain=lambda: json.dumps(LOGIN))
    assert usage["seven_day"][0] == 43.0
    assert seen[0].get_header("Authorization") == "Bearer tok-fake"


def test_login_path_follows_claude_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert wc.credentials_path() == os.path.join(str(tmp_path), ".credentials.json")


def test_cli_reads_the_login_when_no_pct_is_given(monkeypatch, capsys):
    monkeypatch.setattr(wc, "read_usage", lambda: {"seven_day": (90.0, RENEWS.isoformat())})
    assert wc.main(["--now", at(3).isoformat()]) == 1
    assert "90 %" in capsys.readouterr().out
    monkeypatch.setattr(wc, "read_usage", lambda: {"seven_day": (10.0, RENEWS.isoformat())})
    assert wc.main(["--now", at(3).isoformat()]) == 0
    assert "10 %" in capsys.readouterr().out


def test_cli_exit_2_when_usage_cannot_be_read(monkeypatch, capsys):
    monkeypatch.setattr(wc, "read_usage", lambda: None)
    assert wc.main([]) == 2
    assert "--pct" in capsys.readouterr().out


def test_tests_never_see_the_real_login():
    assert not os.path.exists(wc.credentials_path())


def test_renewal_shown_to_the_minute_despite_jittering_seconds(monkeypatch, capsys):
    # The endpoint gives 17:59:59.74 one call and 18:00:00.18 the next: both are 18:00.
    monkeypatch.setattr(wc, "read_usage",
                        lambda: {"seven_day": (10.0, "2026-10-11T17:59:59.743958+00:00")})
    assert wc.main(["--now", at(3).isoformat()]) == 0
    assert "2026-10-11 18:00 UTC" in capsys.readouterr().out
