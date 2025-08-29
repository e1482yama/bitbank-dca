# tests/test_bitbank_private.py
from __future__ import annotations
import os
from pathlib import Path

# --- .env ロード（上書きモード） ---
def load_env(path: str = ".env") -> None:
    p = Path(__file__).resolve().parent.parent / path
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ[k] = v  # ★ 強制上書き

# プロジェクトルートを import パスに追加
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infra.bitbank.private_client import BitbankPrivateClient
from app.config import load_config


def main():
    load_env(".env")  # ← ここで .env を読み込む

    # デバッグ表示（長い値は頭だけ）
    print("BITBANK_API_KEY head:", os.environ.get("BITBANK_API_KEY", "")[:6])
    print("BITBANK_API_SECRET head:", os.environ.get("BITBANK_API_SECRET", "")[:6])

    cfg = load_config()
    client = BitbankPrivateClient(cfg.bitbank_api_key, cfg.bitbank_api_secret)

    # 資産一覧（生JSON）
    assets = client.assets()
    print("assets:", assets)

    # JPY残高（整数円）
    free_jpy = client.get_free_jpy()
    print("free_jpy:", free_jpy)


if __name__ == "__main__":
    main()