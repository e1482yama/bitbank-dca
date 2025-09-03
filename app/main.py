# app/main.py
from __future__ import annotations

import argparse
import os
from pathlib import Path
from datetime import datetime

from app.config import load_config
from app.infra.bitbank.public_client import BitbankPublicClient
from app.infra.bitbank.private_client import BitbankPrivateClient
from app.infra.notifier.line_messaging_api import LineMessagingNotifier
from app.core.specs import get_pair_spec
from app.services.allocation import allocate_amounts, apply_dip_multiplier
from app.services.pricing import get_quote, vol5m_pct, change24h_pct
from app.services.guards import GuardParams, evaluate_pair_guard, make_dip_flags
from app.services.orders import (
    build_plan_for_pair,
    execute_plan_for_pair,
    PairExecutionReport,
)
from app.services.reporting import format_line_message


PAIRS = ["btc_jpy", "eth_jpy"]


def _load_env(path: str = ".env", override: bool = False) -> None:
    """プロジェクト直下の .env を読み込んで環境変数に設定する。"""
    p = Path(__file__).resolve().parent.parent / path
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if override or k not in os.environ:
            os.environ[k] = v


def _weights_from_config(cfg) -> dict[str, float]:
    return {
        "btc_jpy": float(cfg.dca_ratio_btc),
        "eth_jpy": float(cfg.dca_ratio_eth),
    }


def _guard_params_from_config(cfg) -> GuardParams:
    return GuardParams(
        max_spread_pct=cfg.guard_max_spread_pct,
        max_vol5m_pct=cfg.guard_max_vol5m_pct,
        max_slip_pct=None,
        kill_switch=False,
    )


def run(dry_run: bool = True) -> int:
    # .env を読み込む
    _load_env(".env", override=False)

    cfg = load_config()

    # --- clients ---
    pub = BitbankPublicClient()
    prv = BitbankPrivateClient(cfg.bitbank_api_key, cfg.bitbank_api_secret)
    notifier = LineMessagingNotifier(cfg.line_channel_access_token, cfg.line_to_user_id)

    # --- budget & base allocations ---
    total_jpy = int(cfg.dca_total_jpy)
    weights = _weights_from_config(cfg)
    base_allocs = allocate_amounts(weights=weights, total_jpy=total_jpy)
    print("[DCA] total_jpy:", total_jpy)
    print("[DCA] base_allocs:", base_allocs)

    # --- market snapshot for guards & dip ---
    quotes: dict[str, tuple] = {}
    vol5m_map: dict[str, float] = {}
    chg24h_map: dict[str, float] = {}
    for pair in PAIRS:
        quotes[pair] = get_quote(pub, pair)
        vol5m_map[pair] = vol5m_pct(pub, pair)
        chg24h_map[pair] = change24h_pct(pub, pair)

    # --- dip flags & apply multiplier ---
    dip_flags = make_dip_flags(chg24h_map, cfg.guard_dip_threshold)
    allocs = apply_dip_multiplier(
        dip_flags=dip_flags,
        allocs=base_allocs,
        base_total=total_jpy,
        multiplier=cfg.dca_dip_multiplier,
        cap_total=int(total_jpy * cfg.dca_dip_multiplier),
    )
    print("[DCA] dip_flags:", dip_flags)
    print("[DCA] final_allocs:", allocs)

    # --- JPY balance check ---
    free_jpy_before = prv.get_free_jpy()
    print("[BALANCE] free_jpy_before:", free_jpy_before)

    if free_jpy_before < sum(allocs.values()):
        # スキップ通知のみ
        reports: list[PairExecutionReport] = []
        text = format_line_message(
            title="Bitbank DCA",
            executed_at=datetime.now(),
            total_budget_jpy=total_jpy,
            dip_multiplier=cfg.dca_dip_multiplier,
            reports=reports,
            jpy_balance_after=free_jpy_before,
            low_balance_threshold=20000,
            extra_note="残高不足のため今週は全スキップしました",
        )
        print("\n--- message (insufficient balance) ---\n" + text)
        notifier.notify(text)
        return 0

    # --- per pair: plan -> guard -> (maybe) execute ---
    guard_params = _guard_params_from_config(cfg)
    reports: list[PairExecutionReport] = []

    for pair, jpy_alloc in allocs.items():
        spec = get_pair_spec(pair)
        # 計画（価格参照→数量計算→丸め）
        plan = build_plan_for_pair(pub, spec, pair, jpy_alloc)

        # ガード評価
        ok, reason, meta = evaluate_pair_guard(quotes[pair], vol5m_map[pair], guard_params)
        if not ok:
            reports.append(
                PairExecutionReport(
                    pair=pair,
                    status="SKIPPED",
                    reason=reason,
                    jpy_planned=jpy_alloc,
                    quote_price=plan.quote.price,
                    avg_price=None,
                    executed_qty=0.0,
                    details={"spread": plan.quote.spread_pct or 0.0, "vol5m_abs": vol5m_map[pair], **meta},
                )
            )
            continue

        if dry_run:
            # 実オーダーせず、FILLED体裁でqty/quoteを表示
            reports.append(
                PairExecutionReport(
                    pair=pair,
                    status="FILLED",
                    reason=None,
                    jpy_planned=jpy_alloc,
                    quote_price=plan.quote.price,
                    avg_price=None,
                    executed_qty=plan.qty,
                    details={"spread": plan.quote.spread_pct or 0.0, "vol5m_abs": vol5m_map[pair]},
                )
            )
        else:
            # 実注文
            rep = execute_plan_for_pair(pub, prv, plan, guard_params)
            reports.append(rep)

    # --- balance after & notify ---
    free_jpy_after = prv.get_free_jpy()

    text = format_line_message(
        title="Bitbank DCA" + (" (dry-run)" if dry_run else ""),
        executed_at=datetime.now(),
        total_budget_jpy=total_jpy,
        dip_multiplier=cfg.dca_dip_multiplier,
        reports=reports,
        jpy_balance_after=free_jpy_after,
        low_balance_threshold=20000,
        extra_note=("※ 実発注なし" if dry_run else None),
    )

    print("\n--- message ---\n" + text)
    notifier.notify(text)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="実オーダーせず、配分と数量のみ計算して通知")
    args = parser.parse_args()
    return_code = run(dry_run=bool(args.dry_run))
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
