# tests/test_line_push.py
from __future__ import annotations

import json
import os
import sys
import requests

PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"


def load_env(path: str = ".env") -> None:
    """外部依存を入れずに .env を簡易ロード（#で始まる行と空行は無視）。"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # 既に環境変数にある場合は上書きしない
            os.environ.setdefault(k, v)


def main() -> int:
    load_env(".env")

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    to_user = os.environ.get("LINE_TO_USER_ID")

    if not token or not to_user:
        print(
            "環境変数が不足しています。'.env' に以下を設定してください：\n"
            "  LINE_CHANNEL_ACCESS_TOKEN=...\n"
            "  LINE_TO_USER_ID=...\n",
            file=sys.stderr,
        )
        return 2

    text = "bitbank-dca: LINE Messaging API テスト通知です 📩"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": to_user,
        "messages": [{"type": "text", "text": text}],
    }

    try:
        resp = requests.post(PUSH_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=10)
    except requests.RequestException as e:
        print(f"HTTPエラー: {e}", file=sys.stderr)
        return 3

    print("status:", resp.status_code)
    try:
        print("body:", resp.json())
    except Exception:
        print("body(text):", resp.text)

    # 仕様上 200 が正常
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())