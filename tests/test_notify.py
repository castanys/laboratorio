import io
import json

import notify_whatsapp as nw


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_config_reads_env_file_and_environment_wins(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# c\nWHATSAPP_API_URL=http://a.invalid/\nWHATSAPP_RECIPIENT='g1'\n")
    assert nw.config(env, {}) == ("http://a.invalid", "g1")
    assert nw.config(env, {"WHATSAPP_RECIPIENT": "g2", "OTHER": "x"}) == ("http://a.invalid", "g2")


def test_no_default_url():
    assert nw.config("/nonexistent/.env", {}) == ("", "")


def test_send_posts_json_and_needs_success():
    seen = {}

    def opener(req, timeout):
        seen["body"] = json.loads(req.data)
        seen["url"] = req.full_url
        return Resp(b'{"success": true}')

    assert nw.send("hi", "http://a.invalid", "g1", opener) is True
    assert seen == {"body": {"recipient": "g1", "message": "hi"}, "url": "http://a.invalid/send"}
    assert nw.send("hi", "http://a.invalid", "g1", lambda r, timeout: Resp(b'{"success": false}')) is False


def test_send_without_destination_or_url_does_nothing():
    def boom(*a, **k):
        raise AssertionError("must not call")
    assert nw.send("hi", "http://a.invalid", "", boom) is False
    assert nw.send("hi", "", "g1", boom) is False


def test_send_survives_network_errors():
    def down(req, timeout):
        raise OSError("down")
    assert nw.send("hi", "http://a.invalid", "g1", down) is False
