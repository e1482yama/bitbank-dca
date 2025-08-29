# app/services/rounding.py
from __future__ import annotations

import math
from app.core.models import PairSpec


def floor_to_step(x: float, step: float) -> float:
    """
    正の数 x を step の倍数へ下方向丸め。stepとは通貨の購入最小単位
    例: x=0.00105, step=0.0001 -> 0.0010
    """
    if step <= 0:
        raise ValueError("step must be positive")
    # 浮動小数の丸め誤差吸収のため eps を加味
    eps = 1e-12
    return math.floor((x + eps) / step) * step


def round_qty_down(spec: PairSpec, raw_qty: float) -> float:
    """
    仕様に従い、数量を下方向丸め。
    - raw_qty < min_size -> 0.0（発注不可）
    - それ以外は size_step に沿って floor
    """
    if raw_qty < spec.min_size:
        return 0.0
    # min_size を基準に step 刻みで落とす（min_size 自体が刻みの原点でない可能性に対応）
    base = spec.min_size
    steps = math.floor((raw_qty - base) / spec.size_step)
    qty = base + steps * spec.size_step
    # 数学的には qty >= min_size を満たす
    # 表示上の微小誤差を抑えるため丸め
    return float(f"{qty:.12f}")