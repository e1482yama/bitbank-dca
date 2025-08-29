# app/infra/bitbank/private_client.py
from __future__ import annotations

import json
import time
import hmac
import hashlib
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from app.core.errors import InfraError
from app.core.ports import PrivateTradePort


class BitbankPrivateClient(PrivateTradePort):
    """
    bitbank プライベートAPIクライアント（最小実装）
      - base: https://api.bitbank.cc
      - 代表的なエンドポイント:
         GET  /v1/user/assets                # 資産一覧
         POST /v1/user/spot/order            # スポット新規注文
      - 認証（従来の NONCE 方式）:
         GET  : HMAC_SHA256(secret, nonce + path + '?' + query)
         POST : HMAC_SHA256(secret, nonce + body_json)
      - 注意:
         ・nonce はミリ秒で単調増加（同一msも+1補正）
         ・POST は署名に使った JSON 文字列と送信文字列を完全一致させる
    """

    _nonce_lock = threading.Lock()
    _last_nonce = 0

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        timeout_sec: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base = "https://api.bitbank.cc"
        self.timeout = timeout_sec
        self.session = session or requests.Session()
        self.api_key = api_key
        self.api_secret = api_secret  # str のまま保持（署名時に encode）

    # ---------- 認証ヘルパ ----------
    def _next_nonce(self) -> str:
        with self._nonce_lock:
            now = int(time.time() * 1000)
            if now <= self._last_nonce:
                now = self._last_nonce + 1
            self._last_nonce = now
            return str(now)

    def _hmac(self, message: str) -> str:
        return hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _headers_post(self, body: Dict[str, Any] | None) -> Dict[str, str]:
        nonce = self._next_nonce()
        body_json = "" if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        sig = self._hmac(nonce + body_json)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": sig,
            "Content-Type": "application/json",
        }

    def _headers_get(self, path: str, params: Dict[str, Any] | None) -> Dict[str, str]:
        nonce = self._next_nonce()
        q = urlencode(params or {}, doseq=True)
        sig = self._hmac(nonce + path + (f"?{q}" if q else ""))
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": sig,
            "Content-Type": "application/json",
        }

    # ---------- low-level ----------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        headers = self._headers_get(path, params)
        try:
            r = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise InfraError(f"private GET failed: {url} ({e})") from e

        if r.status_code != 200:
            raise InfraError(f"private GET {url} -> {r.status_code}")

        try:
            data = r.json()
        except ValueError as e:
            raise InfraError(f"private GET json decode error: {url}") from e

        if not isinstance(data, dict) or int(data.get("success", 0)) != 1:
            raise InfraError(f"private GET success!=1: {url} body={data}")

        return data

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        # 署名に使うJSON文字列を先に作る（送信と完全一致させる）
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = self._headers_post(body)
        try:
            # json= ではなく data= に上の payload をそのまま渡す
            r = self.session.post(url, headers=headers, data=payload.encode("utf-8"), timeout=self.timeout)
        except requests.RequestException as e:
            raise InfraError(f"private POST failed: {url} ({e})") from e

        if r.status_code != 200:
            raise InfraError(f"private POST {url} -> {r.status_code} body={r.text}")

        try:
            data = r.json()
        except ValueError as e:
            raise InfraError(f"private POST json decode error: {url}") from e

        if not isinstance(data, dict) or int(data.get("success", 0)) != 1:
            raise InfraError(f"private POST success!=1: {url} body={data}")

        return data

    # ---------- PrivateTradePort ----------
    def assets(self) -> Dict[str, Any]:
        """資産一覧（生JSON）"""
        return self._get("/v1/user/assets")

    def get_free_jpy(self) -> int:
        """JPY free_amount を整数円で返す"""
        data = self.assets()
        assets = (data.get("data", {}) or {}).get("assets", []) or []
        for a in assets:
            if str(a.get("asset", "")).lower() == "jpy":
                try:
                    return int(float(a.get("free_amount", "0")))
                except Exception:
                    return 0
        return 0

    def market_buy(self, pair: str, size: float) -> Dict[str, Any]:
        """
        成行買い（最小実装）
        Returns:
            { "avg_price": float, "executed_size": float, "order_id": str|None, "raw": {...} }
        """
        body = {
            "pair": pair,
            "amount": f"{size:.8f}".rstrip("0").rstrip(".") or "0",
            "side": "buy",
            "type": "market",
        }
        res = self._post("/v1/user/spot/order", body)
        data = (res.get("data") or {}) if isinstance(res, dict) else {}

        avg = (
            data.get("average_price")
            or data.get("avg_price")
            or (data.get("trades", [{}])[0].get("price") if isinstance(data.get("trades"), list) and data.get("trades") else 0)
            or 0
        )
        exe = data.get("executed_amount") or data.get("executed_size") or data.get("filled_amount") or data.get("executed_quantity") or 0
        oid = data.get("order_id") or data.get("orderId")

        try:
            avg_f = float(avg)
        except Exception:
            avg_f = 0.0
        try:
            exe_f = float(exe)
        except Exception:
            exe_f = 0.0

        return {"avg_price": avg_f, "executed_size": exe_f, "order_id": oid, "raw": res}