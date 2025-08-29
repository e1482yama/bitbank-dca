# tests/test_line_push_dryrun.py
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
from app.infra.notifier.line_messaging_api import LineMessagingNotifier
from app.core.specs import get_pair_spec
from app.services.orders import build_plan_for_pair, PairExecutionReport
from app.services.pricing import vol5m_pct
from app.services.guards import GuardParams, evaluate_pair_guard
from app.services.reporting import format_line_message


def make_report_for_pair(pub: BitbankPublicClient, pair: str, jpy_alloc: int,
                         max_spread: float, max_vol5m: float) -> PairExecutionReport:
    spec = get_pair_spec(pair)
    plan = build_plan_for_pair(pub, spec, pair, jpy_alloc)
    vol_abs = vol5m_pct(pub, pair)
    params = GuardParams(
        max_spread_pct=max_spread,
        max_vol5m_pct=max_vol5m,
        max_slip_pct=None,
        kill_switch=False,
    )
    ok, reason, meta = evaluate_pair_guard(plan.quote, vol_abs, params)

    return PairExecutionReport(
        pair=pair,
        status="FILLED" if ok else "SKIPPED",  # ドライランなので見た目用
        reason=reason,
        jpy_planned=plan.jpy_alloc,
        quote_price=plan.quote.price,
        avg_price=None,                        # 実約定なし
        executed_qty=plan.qty if ok else 0.0,
        details={"spread": plan.quote.spread_pct or 0.0, "vol5m_abs": vol_abs, **meta},
    )


def main():
    load_env(".env")
    cfg = load_config()

    pub = BitbankPublicClient()

    # 7:3配分（.env の DCA_TOTAL_JPY / DCA_RATIO_xxx を使用）
    btc_alloc = int(cfg.dca_total_jpy * cfg.dca_ratio_btc)
    eth_alloc = int(cfg.dca_total_jpy * cfg.dca_ratio_eth)

    btc_rep = make_report_for_pair(pub, "btc_jpy", btc_alloc, cfg.guard_max_spread_pct, cfg.guard_max_vol5m_pct)
    eth_rep = make_report_for_pair(pub, "eth_jpy", eth_alloc, cfg.guard_max_spread_pct, cfg.guard_max_vol5m_pct)

    text = format_line_message(
        title="Bitbank DCA (dry-run)",
        executed_at=datetime.now(),
        total_budget_jpy=cfg.dca_total_jpy,
        dip_multiplier=cfg.dca_dip_multiplier,
        reports=[btc_rep, eth_rep],
        jpy_balance_after=None,
        low_balance_threshold=20000,
        extra_note="※ ドライラン（発注なし）",
    )

    # LINEへ送信
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    to_user = os.environ["LINE_TO_USER_ID"]
    notifier = LineMessagingNotifier(token, to_user)
    notifier.notify(text)

    print("sent.")
    print("\n--- message ---\n" + text)


if __name__ == "__main__":
    main()