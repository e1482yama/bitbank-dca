# app/core/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class OrderStatus(str, Enum):
    """約定状態の正規化。取引所の表記差異はアダプタ側でこの列挙へ寄せる。"""
    FILLED = "filled"      # 完全約定
    PARTIAL = "partial"    # 部分約定
    REJECTED = "rejected"  # 拒否（数量/仕様/残高など）
    SKIPPED = "skipped"    # ガード等の理由で発注せず


@dataclass(frozen=True)
class PairConfig:
    """運用上の配分設定（Variables から読み込む想定）。"""
    pair: str      # e.g., "btc_jpy"
    weight: float  # 0.0 < weight <= 1.0, 全体で合計=1.0


@dataclass(frozen=True)
class PairSpec:
    """取引仕様（最小数量/刻み/価格刻み）。将来は自動同期も可。"""
    pair: str
    min_size: float   # この数量未満は発注不可
    size_step: float  # 数量の刻み
    price_step: float # 価格の刻み（成行では通常未使用だが表示等で利用）


@dataclass(frozen=True)
class Quote:
    """数量計算のための参照価格。price は原則 best_ask を採用。"""
    pair: str
    price: float      # 数量計算に使う参照価格（通常 best_ask）
    best_bid: float
    best_ask: float
    spread_pct: float # (ask - bid) / mid
    ts_ms: int        # 取得時刻（ミリ秒）


@dataclass(frozen=True)
class GuardPolicy:
    """ガード閾値のポリシー。Variables から生成する。"""
    slippage_pct: float    # 発注直前の擬似スリップ上限
    spread_max_pct: float  # スプレッド上限
    vol5m_max_pct: float   # 直近5分ボラ上限


@dataclass(frozen=True)
class GuardDecision:
    """ガード評価の結果。allow=False の場合 reasons に理由コードが入る。"""
    allow: bool
    reasons: List[str]          # 例: ["SPREAD", "VOL", "SLIP", "DATA"]
    details: Dict[str, float]   # 閾値・実測値などの数値詳細


@dataclass(frozen=True)
class OrderFill:
    """約定明細（部分約定を複数持つ想定）。"""
    qty: float
    price: float


@dataclass(frozen=True)
class OrderResult:
    """注文の集約結果。手数料はベース通貨数量（fee_qty）を保持。"""
    order_id: str
    status: OrderStatus
    filled_qty: float
    avg_price: Optional[float]          # 平均約定（未約定時は None）
    fee_qty: Optional[float]            # ベース通貨建ての手数料数量
    fills: List[OrderFill]


@dataclass(frozen=True)
class PairExecutionReport:
    """1ペアあたりの実行レポート。通知用に必要十分な粒度。"""
    pair: str
    alloc_jpy: int
    quote: float
    ordered_qty: float                  # 丸め後の発注数量（成行）
    result: Optional[OrderResult]       # ガードNG/スキップ時は None
    guard: GuardDecision                # allow=True でも詳細を残す


@dataclass(frozen=True)
class DipInfo:
    """ディップ買い増しの発動情報を構造化。"""
    trigger_pct: float                  # 例: -0.03
    multiplier: float                   # 例: 1.5
    fired: Dict[str, bool]              # { "btc_jpy": True, "eth_jpy": False }


@dataclass(frozen=True)
class RunReport:
    """1回の実行全体の集計（通知整形に使用）。"""
    ts_jst: str                         # 実行時刻（JST）
    total_jpy: int
    balance_jpy: int
    next_ts_jst: str                    # 次回予定（JST）
    pairs: List[PairExecutionReport]
    dip: DipInfo