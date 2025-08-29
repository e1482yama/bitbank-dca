# app/services/allocation.py
from __future__ import annotations

from typing import Dict


def allocate_amounts(weights: Dict[str, float], total_jpy: int) -> Dict[str, int]:
    """
    総額を各ペアへ配分する（重みは単純な float の辞書を想定）。

    Args:
        weights: 例 {"btc_jpy": 0.7, "eth_jpy": 0.3}
        total_jpy: 総予算（円）

    Returns:
        例 {"btc_jpy": 7000, "eth_jpy": 3000}

    備考:
        ・小数誤差で合計がズレないよう、最後のペアに余りを与える
        ・weights の合計が 1.0 でなくても、比率として扱う（全体で正規化）
    """
    pairs = list(weights.keys())
    if not pairs:
        return {}

    # 正規化（合計が 0 の場合は均等割）
    s = sum(float(w) for w in weights.values())
    if s <= 0:
        norm = {p: 1.0 / len(pairs) for p in pairs}
    else:
        norm = {p: float(weights[p]) / s for p in pairs}

    allocs: Dict[str, int] = {}
    acc = 0
    for i, pair in enumerate(pairs):
        if i < len(pairs) - 1:
            j = int(total_jpy * norm[pair])
            allocs[pair] = j
            acc += j
        else:
            # 最後のペアに余りを与えて合計を合わせる
            allocs[pair] = total_jpy - acc
    return allocs


def apply_dip_multiplier(
    *,
    dip_flags: Dict[str, bool],
    allocs: Dict[str, int],
    base_total: int,
    multiplier: float,
    cap_total: int,
) -> Dict[str, int]:
    """
    ディップ（下落）フラグが立っているペアに追加予算を配分する。
    追加後の総額は min(base_total * multiplier, cap_total) を超えない。

    ルール:
      1) dip が 1件以上あるとき、extra = target_total - base_total を計算
      2) extra を dip 対象ペアへ「元の alloc 比例」で配分
      3) 端数は最後の dip ペアに付与して合計を合わせる
      4) dip が 0 件、または multiplier<=1 の場合はそのまま返す

    Args:
        dip_flags: 例 {"btc_jpy": True, "eth_jpy": False}
        allocs:    例 {"btc_jpy": 7000, "eth_jpy": 3000}
        base_total: ベース総額（= sum(allocs.values()) の想定）
        multiplier: 例 1.5
        cap_total:  上限（例: int(base_total * multiplier)）

    Returns:
        追加配分後の円配分（辞書）
    """
    if base_total <= 0 or multiplier <= 1.0:
        return dict(allocs)

    target_total = min(int(base_total * float(multiplier)), int(cap_total))
    extra = target_total - base_total
    if extra <= 0:
        return dict(allocs)

    dips = [p for p, f in dip_flags.items() if f and p in allocs]
    if not dips:
        # dip 対象が無ければそのまま
        return dict(allocs)

    # dip 対象の元予算合計（ゼロなら均等割）
    dip_base_sum = sum(allocs[p] for p in dips)
    result = dict(allocs)

    if dip_base_sum <= 0:
        # 均等割
        q, r = divmod(extra, len(dips))
        for i, p in enumerate(dips):
            result[p] += q + (1 if i == len(dips) - 1 and r > 0 else 0)
        return result

    # 元配分に比例して extra を配る
    acc = 0
    for i, p in enumerate(dips):
        if i < len(dips) - 1:
            add = int(extra * (allocs[p] / dip_base_sum))
            result[p] += add
            acc += add
        else:
            # 余りは最後の dip ペアへ
            result[p] += (extra - acc)
    return result