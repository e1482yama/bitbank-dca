# app/core/ports.py
from __future__ import annotations
from typing import Protocol, Dict, Any


class PublicPricePort(Protocol):
    """
    価格取得用の抽象インターフェース。
    BitbankPublicClient などがこれを実装する。
    """
    def ticker(self, pair: str) -> Dict[str, Any]: ...
    def depth(self, pair: str) -> Dict[str, Any]: ...
    def candlestick(self, pair: str, candle_type: str, yyyymmdd: str) -> Dict[str, Any]: ...


class PrivateTradePort(Protocol):
    """
    取引系の抽象インターフェース。
    BitbankPrivateClient などがこれを実装する。
    """
    def assets(self) -> Dict[str, Any]: ...
    def place_market_buy(self, pair: str, quantity: float) -> Dict[str, Any]: ...
    def orders_info(self, pair: str, order_id: str) -> Dict[str, Any]: ...


class NotifierPort(Protocol):
    """
    通知系の抽象インターフェース。
    LINE Notify などがこれを実装する。
    """
    def send(self, token: str, message: str) -> None: ...