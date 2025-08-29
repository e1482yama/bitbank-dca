# app/core/specs.py
from __future__ import annotations

from typing import Dict, Iterable, Optional
from .models import PairSpec


class PairSpecRepository:
    """
    取引ペアごとの最小数量・刻み・価格刻みを管理するリポジトリ。
    - 現状は内部テーブルで安全運用（将来: 取引所API等から同期に拡張）
    - 値は保守的（厳しめ）に設定。未登録ペアは例外として明示的に止める。
    """

    def __init__(self, table: Optional[Dict[str, PairSpec]] = None) -> None:
        self._table: Dict[str, PairSpec] = table or {
            "btc_jpy": PairSpec("btc_jpy", min_size=0.0001, size_step=0.0001, price_step=1.0),
            "eth_jpy": PairSpec("eth_jpy", min_size=0.0001, size_step=0.0001, price_step=1.0),
            # 追加例:
            # "link_jpy": PairSpec("link_jpy", min_size=0.1, size_step=0.1, price_step=1.0),
        }

    # 取得系 ---------------------------------------------------------------

    def get(self, pair: str) -> PairSpec:
        """指定ペアの仕様を取得。未登録なら KeyError。"""
        spec = self._table.get(pair)
        if spec is None:
            raise KeyError(f"PairSpec not found for '{pair}'. Register it in PairSpecRepository.")
        return spec

    def contains(self, pair: str) -> bool:
        """登録有無の真偽。"""
        return pair in self._table

    def pairs(self) -> Iterable[str]:
        """登録済みペア一覧。"""
        return self._table.keys()

    # メンテ系（運用での一時調整や将来の自動同期に備える） ----------------

    def upsert(self, spec: PairSpec) -> None:
        """既存は置換・新規は追加。"""
        self._table[spec.pair] = spec

    def remove(self, pair: str) -> None:
        """登録削除。存在しない場合は KeyError。"""
        if pair not in self._table:
            raise KeyError(f"PairSpec not found for '{pair}'.")

        del self._table[pair]

# ---- 関数的インターフェース（既存コード互換のための簡便API） ----

# デフォルトのリポジトリ
DEFAULT_PAIR_SPEC_REPO = PairSpecRepository()


def get_pair_spec(pair: str) -> PairSpec:
    """指定ペアの取引仕様を返す（関数インターフェース）。"""
    return DEFAULT_PAIR_SPEC_REPO.get(pair)


def list_supported_pairs() -> list[str]:
    """登録済みペア一覧を返す。"""
    return list(DEFAULT_PAIR_SPEC_REPO.pairs())