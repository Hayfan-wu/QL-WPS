import os

from wps_auto import load_project_env


def test_load_project_env_sets_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "WPS_PROJECT_DIR=/opt/QL-WPS",
                "WPS_SCRIPT_PATH=/opt/QL-WPS/wps_auto.py",
                "QL_URL=http://127.0.0.1:5700",
                "QL_CLIENT_ID=wps_client_id",
                "QL_CLIENT_SECRET=wps_client_secret",
                "WXPUSHER_APP_TOKEN=token",
                "WXPUSHER_UID=uid",
            ]
        ),
        encoding="utf-8",
    )

    for key in (
        "WPS_PROJECT_DIR",
        "WPS_SCRIPT_PATH",
        "QL_URL",
        "QL_CLIENT_ID",
        "QL_CLIENT_SECRET",
        "WXPUSHER_APP_TOKEN",
        "WXPUSHER_UID",
    ):
        monkeypatch.delenv(key, raising=False)

    values = load_project_env(str(env_file))

    assert values["WPS_PROJECT_DIR"] == "/opt/QL-WPS"
    assert os.getenv("WPS_SCRIPT_PATH") == "/opt/QL-WPS/wps_auto.py"
    assert os.getenv("QL_CLIENT_ID") == "wps_client_id"
    assert os.getenv("WXPUSHER_APP_TOKEN") == "token"
