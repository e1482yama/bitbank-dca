# tests/test_dry_run_plan.py
from __future__ import annotations
import os, sys
from pathlib import Path
from datetime import datetime

# --- .env ロード（強制上書き） ---
def load_env(path: str = ".env") -> None:
    p = Path(__file__).resolve().parent.parent / path
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

# --- import パスにプロジェクトルートを追加 ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.infra.bitbank.public_client import BitbankPublicClient
from app.core.specs import get_pair_spec
from app.services.orders import build_plan_for_pair, PairExecutionReport
from app.services.pricing import vol5m_pct
from app.services.guards import GuardParams, evaluate_pair_guard
from app.services.reporting import format_line_message


def main():
    load_env(".env")  # ← ここで .env を読み込む

    cfg = load_config()
    pub = BitbankPublicClient()

    pair = "btc_jpy"
    spec = get_pair_spec(pair)
    jpy_alloc = int(cfg.dca_total_jpy * cfg.dca_ratio_btc)

    # 計画作成（発注はしない）
    plan = build_plan_for_pair(pub, spec, pair, jpy_alloc)

    # ガード判定
    vol_abs = vol5m_pct(pub, pair)
    params = GuardParams(
        max_spread_pct=cfg.guard_max_spread_pct,
        max_vol5m_pct=cfg.guard_max_vol5m_pct,
        max_slip_pct=None,
        kill_switch=False,
    )
    ok, reason, meta = evaluate_pair_guard(plan.quote, vol_abs, params)

    # 通知文（ドライラン）
    rep = PairExecutionReport(
        pair=pair,
        status="FILLED" if ok else "SKIPPED",
        reason=reason,
        jpy_planned=plan.jpy_alloc,
        quote_price=plan.quote.price,
        avg_price=None,
        executed_qty=plan.qty if ok else 0.0,
        details={"spread": plan.quote.spread_pct or 0.0, "vol5m_abs": vol_abs, **meta},
    )
    text = format_line_message(
        title="Bitbank DCA (dry-run)",
        executed_at=datetime.now(),
        total_budget_jpy=cfg.dca_total_jpy,
        dip_multiplier=cfg.dca_dip_multiplier,
        reports=[rep],
        jpy_balance_after=None,
        low_balance_threshold=20000,
        extra_note="※ ドライラン（発注なし）",
    )

    print("PLAN:", plan)
    print("GUARD:", ok, reason, meta)
    print("\n--- LINE text (dry-run) ---\n" + text)


if __name__ == "__main__":
    main()