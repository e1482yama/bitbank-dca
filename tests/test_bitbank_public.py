# tests/test_bitbank_public.py
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infra.bitbank.public_client import BitbankPublicClient

def main():
    pub = BitbankPublicClient()

    tj = pub.ticker("btc_jpy")
    print("ticker:", tj.get("data", {}) or tj)

    dj = pub.depth("btc_jpy")
    data = dj.get("data", {}) or {}
    bids = data.get("bids", [])[:1]
    asks = data.get("asks", [])[:1]
    print("depth best:", {"bid": bids[0] if bids else None, "ask": asks[0] if asks else None})

    # JST当日の日付は pricing 側で作っていますが、ここでは簡単に固定で確認したい場合は今日を渡すようにしてください
    # 例: yyyymmdd = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
    # ここでは API 疎通確認のみ ticker/depth を見られれば十分です

if __name__ == "__main__":
    main()