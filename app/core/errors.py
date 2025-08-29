# app/core/errors.py
from __future__ import annotations

from enum import Enum


# ========= 理由コード（通知・ログで使う共通キー） =========

class SkipReason(str, Enum):
    SPREAD = "SPREAD"         # スプレッド超過
    VOL = "VOL"               # 5分ボラ上限超過
    SLIP = "SLIP"             # 擬似スリッページ上限超過
    MIN_SIZE = "MIN_SIZE"     # 最小数量未満
    INSUFF_JPY = "INSUFF_JPY" # 残高不足（全スキップ）
    KILL = "KILL"             # キルスイッチ（手動停止）
    DATA = "DATA"             # データ不整合（価格/板など）


# ========= ドメイン例外 =========
# 役割: サービス層から上位へ “どういう失敗か” を明確に伝える。
#       infra層（HTTP/署名）と区別し、通知/再試行の判断に使う。

class DomainError(Exception):
    """本アプリのドメインで扱う基底例外。"""
    pass


class ConfigError(DomainError):
    """設定値の不正（weights不一致・合計!=1.0 など）。"""
    pass


class SpecNotFound(DomainError):
    """取引仕様が未登録。"""
    def __init__(self, pair: str):
        super().__init__(f"PairSpec not found for '{pair}'")
        self.pair = pair


class GuardRejected(DomainError):
    """ガードで弾いたことを表す例外。"""
    def __init__(self, reason: SkipReason, details: dict | None = None):
        super().__init__(f"Guard rejected: {reason}")
        self.reason = reason
        self.details = details or {}


class MinSizeViolation(DomainError):
    """丸め後数量が最小数量未満で発注不可。"""
    def __init__(self, pair: str, min_size: float, got: float):
        super().__init__(f"Min size violation for {pair}: min={min_size}, got={got}")
        self.pair = pair
        self.min_size = min_size
        self.got = got


class InsufficientJpy(DomainError):
    """JPY残高不足（全スキップ対象）。"""
    def __init__(self, balance: int, required: int):
        super().__init__(f"Insufficient JPY: balance={balance}, required={required}")
        self.balance = balance
        self.required = required


class KillSwitchEnabled(DomainError):
    """キルスイッチON（安全停止）。"""
    pass


# ========= インフラ関連（HTTP/認証/レート制限） =========
# 役割: infra層で捕捉→サービス層へこの例外で伝播。

class InfraError(Exception):
    """外部I/O由来の基底例外（HTTP/署名/タイムアウト等）。"""
    pass


class ApiAuthError(InfraError):
    """認証/署名エラー。"""
    pass


class ApiRateLimit(InfraError):
    """429 レート制限。上位で指数バックオフ再試行対象。"""
    pass


class ApiHTTPError(InfraError):
    """その他HTTPエラー（4xx/5xx）。"""
    def __init__(self, status: int, body: str | None = None):
        super().__init__(f"HTTP error: {status}")
        self.status = status
        self.body = body or ""