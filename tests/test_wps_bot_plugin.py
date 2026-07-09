import os
import sys


QL_BOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "QL-Bot"))
if QL_BOT_DIR not in sys.path:
    sys.path.insert(0, QL_BOT_DIR)

from bot_plugins import wps


def test_wps_plugin_reads_script_path_from_project_env(tmp_path):
    script_path = tmp_path / "wps_auto.py"
    (tmp_path / ".env").write_text(
        f"WPS_PROJECT_DIR={tmp_path}\nWPS_SCRIPT_PATH={script_path}\n",
        encoding="utf-8",
    )

    assert wps._get_wps_script_path(str(tmp_path)) == str(script_path)


def test_wps_plugin_injects_cookie_from_qinglong(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f"WPS_PROJECT_DIR={tmp_path}",
                f"WPS_SCRIPT_PATH={tmp_path / 'wps_auto.py'}",
                "WXPUSHER_APP_TOKEN=token",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(wps, "_get_wps_cookie", lambda project_dir: {"value": "cookie=value"})

    env = wps._build_wps_auto_env(str(tmp_path))

    assert env["WPS_COOKIE"] == "cookie=value"
    assert env["WXPUSHER_APP_TOKEN"] == "token"
