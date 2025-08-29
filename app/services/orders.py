from __future__ import annotations

import os

from app.core.specs import get_pair_spec

from dataclasses import dataclass
from typing import Dict, Optional

from app.core.models import PairSpec, PairConfig, Quote
from app.core.errors import SkipReason, GuardRejected, MinSizeViolation, InfraError
from app.core.ports import PublicPricePort, PrivateTradePort
from app.services.pricing import get_quote, vol5m_pct
from app.services.rounding import round_qty_down
from app.services.guards import GuardParams, evaluate_pair_guard

# --- 約定情報の集計ヘルパ ---
def _collect_avg_and_qty(order_res: dict) -> tuple[float, float]:
    """
    private_client.market_buy() の戻り値から平均約定価格と約定数量を取り出す。
    戻り値は {"avg_price": float, "executed_size": float, "order_id": str|None, "raw": {...}}
    という正規化済みの形なので、素直に読む。
    """
    try:
        avg = float(order_res.get("avg_price", 0.0))
    except (TypeError, ValueError):
        avg = 0.0
    try:
        qty = float(order_res.get("executed_size", 0.0))
    except (TypeError, ValueError):
        qty = 0.0
    return avg, qty

# ========== 計画/結果DTO ==========

@dataclass(frozen=True)
class PairOrderPlan:
    """発注前に固めた計画（計算系のみ。I/Oなし）"""
    pair: str
    jpy_alloc: int            # このペアに割り当てた円
    quote: Quote              # 参照価格（最良askをpriceとする）
    raw_qty: float            # 丸め前の生数量 jpy_alloc / quote.price
    qty: float                # 取引所ルールで丸めた最終数量（0なら発注不可）


@dataclass(frozen=True)
class PairExecutionReport:
    """1ペアの最終結果（通知/集計用）"""
    pair: str
    status: str               # "FILLED" | "SKIPPED" | "ERROR"
    reason: Optional[SkipReason]  # スキップ時の理由
    jpy_planned: int          # 予定円額（配分後 or dip適用後）
    quote_price: float        # 数量計算に用いた参照価格（最良ask）
    avg_price: Optional[float]      # 取得できた平均約定単価（約定後）
    executed_qty: float              # 約定数量（FILLED時）。SKIPPEDは0
    details: Dict[str, float]        # 付加情報（spread/volなど）


# ========== 計画 ==========

def build_plan_for_pair(
    pub: PublicPricePort,
    spec: PairSpec,
    pair: str,
    jpy_alloc: int,
) -> PairOrderPlan:
    """
    価格参照→数量算出→丸め までを行い、発注前の「計画」を返す。
    I/Oは Public API のみ（価格系）。
    """
    quote = get_quote(pub, pair)
    raw_qty = jpy_alloc / quote.price if quote.price > 0 else 0.0
    qty = round_qty_down(spec, raw_qty)
    return PairOrderPlan(
        pair=pair,
        jpy_alloc=jpy_alloc,
        quote=quote,
        raw_qty=raw_qty,
        qty=qty,
    )


# ========== 実行（ガード→発注） ==========

def execute_plan_for_pair(pub, prv, plan, guard_params):
    pair = plan.pair
    spec = get_pair_spec(pair)  # 最小数量/刻み取得

    # 数量0 or 最小数量未満は SKIP（例外にしない）
    if plan.qty is None or plan.qty <= 0 or plan.qty < spec.min_size:
        return PairExecutionReport(
            pair=pair,
            status="SKIPPED",
            reason=SkipReason.MIN_SIZE,
            jpy_planned=plan.jpy_alloc,
            quote_price=plan.quote.price,
            avg_price=None,
            executed_qty=0.0,
            details={
                "min_size": spec.min_size,        # ← 正しい最小数量を表示
                "size_step": spec.size_step,
                "price_step": spec.price_step,
            },
        )

    # ここから実発注
    # 価格・スリッページなどの最終ガード（必要に応じて）
    ok, reason, meta = evaluate_pair_guard(plan.quote, vol5m_pct(pub, pair), guard_params)
    if not ok:
        return PairExecutionReport(
            pair=pair,
            status="SKIPPED",
            reason=reason,
            jpy_planned=plan.jpy_alloc,
            quote_price=plan.quote.price,
            avg_price=None,
            executed_qty=0.0,
            details={**meta, "spread": plan.quote.spread_pct or 0.0},
        )

    # --- Safety gate: require explicit DCA_LIVE to place real orders ---
    if os.getenv("DCA_LIVE", "0").lower() not in ("1", "true", "on", "yes"):
        return PairExecutionReport(
            pair=pair,
            status="SKIPPED",
            reason="LIVE_DISABLED",
            jpy_planned=plan.jpy_alloc,
            quote_price=plan.quote.price,
            avg_price=None,
            executed_qty=0.0,
            details={"note": "Live発注を無効化中。実行するには DCA_LIVE=1 を設定してください。"},
        )

    # マーケット成行購入（価格はサーバ側で決まる）
    order_res = prv.market_buy(pair, plan.qty)

    # 約定集計（平均約定価格など）
    avg, filled_qty = _collect_avg_and_qty(order_res)  # 既存の集計関数を仮定

    return PairExecutionReport(
        pair=pair,
        status="FILLED",
        reason=None,
        jpy_planned=plan.jpy_alloc,
        quote_price=plan.quote.price,
        avg_price=avg,
        executed_qty=filled_qty,
        details={"spread": plan.quote.spread_pct or 0.0},
    )