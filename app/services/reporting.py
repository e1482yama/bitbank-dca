# app/services/reporting.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional

from app.core.errors import SkipReason
from app.services.orders import PairExecutionReport

JST = timezone(timedelta(hours=9))


def _fmt_jst(dt: Optional[datetime] = None) -> str:
    dt = dt.astimezone(JST) if dt else datetime.now(JST)
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_money(jpy: int | float) -> str:
    # JPYは区切りカンマ、少数は切り捨て
    try:
        j = int(jpy)
    except Exception:
        j = 0
    return f"{j:,}円"


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "-"
    return f"{x*100:.2f}%"


def _status_emoji(status: str) -> str:
    s = status.upper()
    if s == "FILLED":
        return "✅"
    if s == "SKIPPED":
        return "⏸️"
    if s == "ERROR":
        return "⚠️"
    return "ℹ️"


def _reason_label(reason: Optional[SkipReason]) -> str:
    if reason is None:
        return ""
    # 人が見やすい短い日本語へ（Enum/文字列 両対応）
    mapping = {}
    try:
        mapping[getattr(SkipReason, "SPREAD")] = "スプレッド上限超"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "VOL")] = "5分ボラ上限超"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "SLIP")] = "スリッページ上限超"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "MIN_SIZE")] = "最小数量未満"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "INSUFF_JPY")] = "残高不足"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "KILL")] = "キルスイッチ"
    except Exception:
        pass
    try:
        mapping[getattr(SkipReason, "DATA")] = "データ不整合"
    except Exception:
        pass

    # Enum の場合
    if isinstance(reason, SkipReason):
        return mapping.get(reason, getattr(reason, "name", str(reason)))

    # 文字列の場合（後方互換・未知理由の素通し）
    if isinstance(reason, str):
        try:
            enum_reason = getattr(SkipReason, reason)
            return mapping.get(enum_reason, reason)
        except Exception:
            return reason

    return "-"


def _fmt_pair_line(r: PairExecutionReport) -> str:
    """
    1ペア分の行を作る。
    - quote_price: 数量計算に使った参照価格（最良ask）
    - avg_price  : 実際の平均約定価格
    """
    emj = _status_emoji(r.status)
    head = f"{emj} {r.pair}"

    planned = f"割当: {_fmt_money(r.jpy_planned)}"
    quote = f"quote: {r.quote_price:,.0f}円"
    spread = f"spread: {_fmt_pct(r.details.get('spread'))}"
    vol = f"5m: {_fmt_pct(r.details.get('vol5m_abs'))}"
    chg = r.details.get("chg24h_pct") if r.details else None
    chg24 = None
    if isinstance(chg, (int, float)):
        chg24 = f" / 24h: {chg:+.2f}%"
    else:
        chg24 = ""

    if r.status.upper() == "FILLED":
        avg = f"avg: {r.avg_price:,.0f}円" if (r.avg_price or 0) > 0 else "avg: -"
        qty = f"qty: {r.executed_qty:.8f}"
        return f"{head}\n  {planned} / {quote} / {avg}\n  {qty} / {spread} / {vol}{chg24}"
    elif r.status.upper() == "SKIPPED":
        reason = _reason_label(r.reason)
        return f"{head}\n  SKIP: {reason}\n  {planned} / {quote} / {spread} / {vol}{chg24}"
    else:  # ERROR など
        return f"{head}\n  ERROR\n  {planned} / {quote} / {spread} / {vol}"


def format_line_message(
    *,
    title: str = "Bitbank DCA",
    executed_at: Optional[datetime] = None,
    total_budget_jpy: Optional[int] = None,
    dip_multiplier: Optional[float] = None,
    reports: Iterable[PairExecutionReport],
    jpy_balance_after: Optional[int] = None,
    low_balance_threshold: Optional[int] = None,
    extra_note: Optional[str] = None,
) -> str:
    """
    LINE送信用のテキストを組み立てる。

    Args:
        title: 見出し
        executed_at: 実行時刻（JST表示）。未指定ならnow(JST)
        total_budget_jpy: 今回の通常予算（dip前）
        dip_multiplier: ディップ倍率（適用上限の情報として表示）
        reports: 1ペアごとの実行結果
        jpy_balance_after: 約定後のJPY残高（通知時点で取得できるなら）
        low_balance_threshold: 残高下限のしきい値（下回ると⚠️で別行表示）
        extra_note: 任意の追記（ドライラン等の注記）

    Returns:
        LINE Notifyへそのまま送れるテキスト
    """
    lines: list[str] = []

    # ヘッダ
    at = _fmt_jst(executed_at)
    head = f"【{title}】{at}"
    if total_budget_jpy is not None:
        head += f" / 予算: {_fmt_money(total_budget_jpy)}"
    if dip_multiplier is not None:
        head += f" / dip×{dip_multiplier:.2f}"
    lines.append(head)

    # 明細
    has_any = False
    for r in reports:
        has_any = True
        lines.append(_fmt_pair_line(r))
    if not has_any:
        lines.append("（対象ペアなし）")

    # フッタ：残高・注意など
    if jpy_balance_after is not None:
        bal_line = f"JPY残高: {_fmt_money(jpy_balance_after)}"
        if low_balance_threshold is not None and jpy_balance_after < low_balance_threshold:
            bal_line = "⚠️ " + bal_line + f"（しきい値 {_fmt_money(low_balance_threshold)} を下回りました）"
        lines.append(bal_line)

    if extra_note:
        lines.append(extra_note)

    return "\n".join(lines)


# --- ログやテスト向けの要約（任意） ---

def summarize_stats(reports: Iterable[PairExecutionReport]) -> dict:
    """
    集計用の簡易サマリを返す（ログ/検証用）。
    Returns:
        {
          "filled_pairs": int,
          "skipped_pairs": int,
          "error_pairs": int,
          "filled_jpy_planned": int,   # 予定額の合計（FILLEDのみ）
          "executed_qty_sum": float,   # 約定数量の合計（FILLEDのみ）
        }
    """
    filled = skipped = error = 0
    jpy_sum = 0
    qty_sum = 0.0
    for r in reports:
        s = (r.status or "").upper()
        if s == "FILLED":
            filled += 1
            jpy_sum += int(r.jpy_planned)
            qty_sum += float(r.executed_qty)
        elif s == "SKIPPED":
            skipped += 1
        else:
            error += 1
    return {
        "filled_pairs": filled,
        "skipped_pairs": skipped,
        "error_pairs": error,
        "filled_jpy_planned": jpy_sum,
        "executed_qty_sum": qty_sum,
    }