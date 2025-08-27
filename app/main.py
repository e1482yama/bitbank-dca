
from __future__ import annotations
import argparse
from .config import load_settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="実オーダーせず、設定と配分だけ確認")
    args = parser.parse_args()

    s = load_settings()
    alloc = {pair: round(s.total_jpy * w) for pair, w in zip(s.pairs, s.weights)}
    print("[SETTINGS]")
    print(f"pairs={s.pairs}, weights={s.weights}, total_jpy={s.total_jpy}")
    print(f"slip={s.slippage_pct}, spread={s.spread_max_pct}, vol5m={s.vol5m_max_pct}")
    print(f"dip_trigger={s.dip_trigger_pct}, dip_multiplier={s.dip_multiplier}")
    print(f"auth_mode={s.auth_mode}, time_window_ms={s.time_window_ms}")

    print("\n[ALLOC]")
    for p, j in alloc.items():
        print(f"{p}: {j} JPY")

    if args.dry_run:
        print("\n[DRY-RUN] 実オーダーは行いません。")
    else:
        print("\n[TODO] 発注ロジックを実装してください。")

if __name__ == "__main__":
    main()
