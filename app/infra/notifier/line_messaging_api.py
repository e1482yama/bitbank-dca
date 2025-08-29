# app/infra/notifier/line_messaging_api.py
from __future__ import annotations

import json
from typing import Optional

import requests


class LineMessagingNotifier:
    """
    LINE Messaging API の最小実装（テキスト push のみ）。
    - 依存最小：requests のみ
    - 送信先は単一ユーザー（userId）を前提
    """

    PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"

    def __init__(self, channel_access_token: str, to_user_id: str, timeout_sec: float = 10.0) -> None:
        """
        Args:
            channel_access_token: LINE Messaging API のチャネルアクセストークン（長い方）
            to_user_id: 送信先ユーザーID（ボットを友だち追加したユーザーの userId）
            timeout_sec: HTTP タイムアウト秒
        """
        self.token = channel_access_token
        self.to = to_user_id
        self.timeout = timeout_sec

    # NotifierPort のメソッド名に合わせたい場合：
    # - もし ports.py が notify(text: str) を想定しているならそのまま使えます。
    # - もし send(text: str) という名前なら、下の alias を使ってください。
    def notify(self, text: str) -> None:
        """
        テキストを1ユーザーに push 送信する（最小実装）。
        失敗時は requests.HTTPError を送出。
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": self.to,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        resp = requests.post(self.PUSH_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=self.timeout)
        # 200 か 201 あたりが正常（仕様上 200）
        if resp.status_code != 200:
            # 失敗詳細を見たいときは resp.text をログに出す
            try:
                detail = resp.json()
            except Exception:
                detail = {"body": resp.text}
            raise requests.HTTPError(f"LINE push failed: {resp.status_code}", response=resp, request=resp.request)

    # alias: NotifierPort のメソッド名が send の場合に備えて
    def send(self, text: str) -> None:
        self.notify(text)