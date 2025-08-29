# app/services/guards.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from app.core.models import Quote
from app.core.errors import SkipReason


@dataclass(frozen=True)
class GuardParams:
    """
    ガード用のしきい値セット。
    - max_spread_pct: 許容スプレッド上限（例: 0.004 = 0.4%）
    - max_vol5m_pct: 直近5分の変化率（絶対値）の上限（例: 0.02 = 2%）
    - max_slip_pct: 擬似スリッページ上限（未使用なら None）
    - kill_switch : 緊急停止（True なら全スキップ）
    """
    max_spread_pct: float
    max_vol5m_pct: float
    max_slip_pct: float | None
    kill_switch: bool = False


def evaluate_pair_guard(
    quote: Quote,
    vol5m_abs: float,
    params: GuardParams,
) -> Tuple[bool, SkipReason | None, Dict[str, float]]:
    """
    1ペア分の発注可否を判定する。
    戻り値: (OK?, SkipReason or None, 詳細メタ)

    判定順:
      1) KillSwitch
      2) DATA 異常 (price/bid/ask<=0)
      3) SPREAD (quote.spread_pct > max_spread_pct)
      4) VOL5M (vol5m_abs > max_vol5m_pct)
      5) SLIP  (未実装: params.max_slip_pct が None ならスキップしない)
    """
    # 1) KillSwitch
    if params.kill_switch:
        return False, SkipReason.KILL, {}

    # 2) DATA 異常
    if quote.price <= 0 or (quote.best_bid <= 0 and quote.best_ask <= 0):
        return False, SkipReason.DATA, {"price": quote.price, "best_bid": quote.best_bid, "best_ask": quote.best_ask}

    # 3) SPREAD
    if quote.spread_pct is not None and quote.spread_pct > params.max_spread_pct:
        return False, SkipReason.SPREAD, {"spread": quote.spread_pct, "limit": params.max_spread_pct}

    # 4) VOL5M
    if vol5m_abs > params.max_vol5m_pct:
        return False, SkipReason.VOL, {"vol5m_abs": vol5m_abs, "limit": params.max_vol5m_pct}

    # 5) SLIP（将来拡張: 板厚から推定。初期実装では未使用）
    if params.max_slip_pct is not None:
        # ここにスリッページ推定ロジックを実装する場合は、
        # 想定数量と板深さから価格インパクトを見積もって比較する。
        pass

    return True, None, {}


def make_dip_flags(
    change24h_map: Dict[str, float],
    dip_threshold_abs: float,
) -> Dict[str, bool]:
    """
    ディップ判定フラグを作成する。
    ルール: 24h変化率 <= -dip_threshold_abs なら True（= dip）
      例) dip_threshold_abs=0.03 のとき、-3%以下で dip 扱い。

    Args:
        change24h_map: {pair: 24h変化率} 例: {"btc_jpy": -0.025, "eth_jpy": -0.045}
        dip_threshold_abs: 例 0.03 (= 3%)

    Returns:
        {pair: bool} 例: {"btc_jpy": False, "eth_jpy": True}
    """
    flags: Dict[str, bool] = {}
    for pair, chg in change24h_map.items():
        flags[pair] = (chg <= -abs(dip_threshold_abs))
    return flags