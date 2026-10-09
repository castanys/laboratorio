"""LAB-01: the privacy check exits 0 on clean content and 1 on a path under the home
directory, an email, a phone number or a token. Offending strings are built in pieces so
this file itself stays clean."""
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "comprueba_privacidad.sh")

BAD = {
    "home": "config lives in /ho" + "me/alice/.config/x",
    "email": "write to alice" + "@" + "gmail.com for help",
    "phone-intl": "call +34 " + "600 11 22 33 now",
    "phone-plain": "number 600" + "111222 here",
    "token-github": "token ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4",
    "token-anthropic": "key sk-ant-" + "api03-abcDEF123456789xyz",
    "token-aws": "id AKIA" + "ABCDEFGHIJKLMNOP",
    "token-assign": "api_key = '" + "abcdef1234567890abcd'",
    "private-key": "-----BEGIN RSA PRIV" + "ATE KEY-----",
}
GOOD = (
    "Run `git clone https://github.com/castanys/laboratorio`.\n"
    "Set WHATSAPP_API_URL=http://gateway.invalid:8080 and WHATSAPP_RECIPIENT=<group-id>.\n"
    "Contact: someone@example.com. Release 1.2.3 on 2026-10-08, version 3.12.\n"
    "Clone with git@github.com:castanys/laboratorio.git; co-author noreply@anthropic.com.\n"
)


def run(path):
    r = subprocess.run(["bash", SCRIPT, str(path)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_clean_content_exits_zero(tmp_path):
    (tmp_path / "README.md").write_text(GOOD)
    code, out = run(tmp_path)
    assert code == 0, out


@pytest.mark.parametrize("kind", sorted(BAD))
def test_each_leak_exits_one_without_printing_it(tmp_path, kind):
    (tmp_path / "README.md").write_text(GOOD)
    (tmp_path / "doc.md").write_text("line one\n" + BAD[kind] + "\n")
    code, out = run(tmp_path)
    assert code == 1, out
    assert "doc.md:2" in out
    secret = BAD[kind].split()[-1]
    assert secret not in out


def test_deny_list_term_is_a_leak(tmp_path):
    (tmp_path / "doc.md").write_text("made by Someone Private\n")
    deny = os.path.join(ROOT, ".privacy-deny")
    original = open(deny).read() if os.path.exists(deny) else None  # absent in the public copy
    try:
        with open(deny, "a") as f:
            f.write("someone private\n")
        code, out = run(tmp_path)
    finally:
        if original is None:
            os.remove(deny)
        else:
            with open(deny, "w") as f:
                f.write(original)
    assert code == 1, out


def test_published_content_of_this_repo_is_clean():
    r = subprocess.run(["bash", SCRIPT], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
