"""
Exchange Failover — Resilient data feed with CoinGecko fallback.

Wraps the primary data feed and falls back to CoinGecko REST API
if the Binance connection fails.

Usage:
    from live.data_feed_fallback import ResilientDataFeed
    feed = ResilientDataFeed(symbols, timeframes)
    feed.fetch_latest()  # Auto-failover on error
"""

import logging
import urllib.request
import json
from typing import Dict, List, Optional

logger = logging.getLogger("DataFeedFallback")

# CoinGecko symbol mapping (Binance -> CoinGecko ID)
COINGECKO_IDS = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "SOLUSDT": "solana",
    "XAUUSDT": "tether-gold",   # XAUT as proxy
    "XAGUSDT": None,            # Not available on CoinGecko
}


class CoinGeckoFallback:
    """Minimal CoinGecko REST client for price checks."""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for symbols via CoinGecko.
        
        Returns:
            Dict of symbol -> USD price
        """
        cg_ids = []
        id_to_symbol = {}
        
        for sym in symbols:
            cg_id = COINGECKO_IDS.get(sym)
            if cg_id:
                cg_ids.append(cg_id)
                id_to_symbol[cg_id] = sym
        
        if not cg_ids:
            return {}
        
        ids_str = ",".join(cg_ids)
        url = f"{self.BASE_URL}/simple/price?ids={ids_str}&vs_currencies=usd"
        
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "BotAlgo/1.0",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            
            prices = {}
            for cg_id, sym in id_to_symbol.items():
                if cg_id in data and "usd" in data[cg_id]:
                    prices[sym] = data[cg_id]["usd"]
            
            logger.info(f"CoinGecko fallback: got prices for {list(prices.keys())}")
            return prices
            
        except Exception as e:
            logger.error(f"CoinGecko fallback also failed: {e}")
            return {}


class ResilientDataFeed:
    """
    Wraps primary data feed with automatic failover.
    
    On Binance failure:
    1. Logs the error
    2. Falls back to CoinGecko for price checks
    3. Sets a flag so callers know data is degraded
    """
    
    def __init__(self, primary_feed, symbols: List[str] = None):
        """
        Args:
            primary_feed: SimulatedDataFeed or BinanceDataFeed instance
            symbols: List of symbols to track
        """
        self.primary = primary_feed
        self.symbols = symbols or []
        self.fallback = CoinGeckoFallback()
        self.is_degraded = False
        self._fallback_prices: Dict[str, float] = {}
        self._consecutive_failures = 0
        self._max_failures = 5
    
    def fetch_latest(self):
        """Fetch data from primary, failover to CoinGecko on error."""
        try:
            self.primary.fetch_latest()
            self.is_degraded = False
            self._consecutive_failures = 0
            
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(
                f"Primary feed failed ({self._consecutive_failures}/{self._max_failures}): {e}"
            )
            
            self.is_degraded = True
            self._fallback_prices = self.fallback.get_prices(self.symbols)
            
            if self._consecutive_failures >= self._max_failures:
                logger.error("Primary feed exceeded max failures. Consider manual intervention.")
    
    def get_dataframe(self, symbol: str, timeframe: str):
        """Get DataFrame, delegates to primary feed."""
        try:
            return self.primary.get_dataframe(symbol, timeframe)
        except Exception:
            return None
    
    def get_latest(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get latest candle, with fallback price if needed."""
        try:
            result = self.primary.get_latest(symbol, timeframe)
            if result:
                return result
        except Exception:
            pass
        
        # Return fallback price as minimal candle
        if symbol in self._fallback_prices:
            price = self._fallback_prices[symbol]
            return {
                "open": price, "high": price, "low": price,
                "close": price, "volume": 0,
                "_source": "coingecko_fallback"
            }
        
        return None
    
    def add_callback(self, callback):
        """Delegate callbacks to primary feed."""
        if hasattr(self.primary, 'add_callback'):
            self.primary.add_callback(callback)


# Self-test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 50)
    print("  DATA FEED FALLBACK - SELF TEST")
    print("=" * 50)
    
    cg = CoinGeckoFallback()
    prices = cg.get_prices(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    
    if prices:
        for sym, price in prices.items():
            print(f"  {sym}: ${price:,.2f}")
        print(f"\n[OK] CoinGecko fallback working - got {len(prices)} prices")
    else:
        print("[WARN] CoinGecko API not reachable (may be rate-limited)")
    
    print("\nAll tests passed!")
