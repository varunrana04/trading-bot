#!/usr/bin/env python3
"""
================================================================================
                    LIVE DATA FEED - BINANCE WEBSOCKET
================================================================================
Real-time data feed for paper trading system.
Connects to Binance WebSocket for 15m and 1hr candles.
================================================================================
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional
import pandas as pd
import numpy as np

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

import requests
import os

# Get API keys from environment (optional - not needed for public data)
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

# Try python-binance, but we have a fallback
try:
    from binance.client import Client
    BINANCE_AVAILABLE = True
except ImportError as e:
    BINANCE_AVAILABLE = False
    Client = None
    print(f"INFO: python-binance not available, using REST API fallback: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataFeed")

# REST API fallback for fetching klines
BINANCE_FUTURES_API = "https://fapi.binance.com"
CRYPTOCOMPARE_API = "https://min-api.cryptocompare.com"

def fetch_klines_rest(symbol: str, interval: str, limit: int = 200) -> list:
    """Fetch klines using direct REST API (fallback method)"""
    url = f"{BINANCE_FUTURES_API}/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 451:
            # Geo-restricted, try CryptoCompare
            logger.warning(f"Binance geo-restricted (451), trying CryptoCompare...")
            return fetch_klines_cryptocompare(symbol, interval, limit)
        else:
            logger.error(f"REST API error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"REST API request failed: {e}")
        return []


def fetch_klines_cryptocompare(symbol: str, interval: str, limit: int = 200) -> list:
    """Fetch klines from CryptoCompare (works globally, no geo-restrictions)"""
    # Convert symbol format: BTCUSDT -> BTC, ETHUSDT -> ETH
    base_symbol = symbol.replace("USDT", "")
    
    # Map interval to CryptoCompare format
    interval_map = {
        "15m": ("histominute", 15),  # 15 min candles
        "1h": ("histohour", 1),      # 1 hour candles
        "4h": ("histohour", 4),      # 4 hour candles
        "1d": ("histoday", 1),       # 1 day candles
    }
    
    if interval not in interval_map:
        logger.error(f"Unsupported interval for CryptoCompare: {interval}")
        return []
    
    endpoint, aggregate = interval_map[interval]
    url = f"{CRYPTOCOMPARE_API}/data/v2/{endpoint}"
    
    params = {
        "fsym": base_symbol,
        "tsym": "USDT",
        "limit": limit,
        "aggregate": aggregate
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "Success":
                # Convert to Binance kline format
                klines = []
                for candle in data.get("Data", {}).get("Data", []):
                    klines.append([
                        candle["time"] * 1000,  # timestamp in ms
                        str(candle["open"]),
                        str(candle["high"]),
                        str(candle["low"]),
                        str(candle["close"]),
                        str(candle.get("volumefrom", 0)),  # volume
                    ])
                logger.info(f"✅ CryptoCompare: {base_symbol} {interval} - {len(klines)} candles")
                return klines
            else:
                logger.error(f"CryptoCompare error: {data.get('Message', 'Unknown error')}")
                return []
        else:
            logger.error(f"CryptoCompare API error {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"CryptoCompare request failed: {e}")
        return []


class CandleBuffer:
    """Buffer to store candles and provide pandas-ready data"""
    
    def __init__(self, max_candles: int = 500):
        self.max_candles = max_candles
        self.data: Dict[str, Dict[str, List]] = {}  # symbol -> timeframe -> candles
    
    def add_candle(self, symbol: str, timeframe: str, candle: Dict):
        """Add a new candle to the buffer"""
        if symbol not in self.data:
            self.data[symbol] = {}
        if timeframe not in self.data[symbol]:
            self.data[symbol][timeframe] = []
        
        candles = self.data[symbol][timeframe]
        
        # Check if this updates the last candle or is new
        if candles and candles[-1]['timestamp'] == candle['timestamp']:
            candles[-1] = candle  # Update
        else:
            candles.append(candle)  # New candle
            if len(candles) > self.max_candles:
                candles.pop(0)
    
    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get candles as DataFrame"""
        if symbol not in self.data or timeframe not in self.data[symbol]:
            return None
        
        candles = self.data[symbol][timeframe]
        if not candles:
            return None
        
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    
    def get_latest(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get the latest candle"""
        if symbol not in self.data or timeframe not in self.data[symbol]:
            return None
        candles = self.data[symbol][timeframe]
        return candles[-1] if candles else None


class BinanceDataFeed:
    """Real-time data feed from Binance"""
    
    BINANCE_WS_URL = "wss://fstream.binance.com/ws"
    
    def __init__(self, symbols: List[str], timeframes: List[str] = ["15m", "1h"]):
        self.symbols = [s.lower() for s in symbols]
        self.timeframes = timeframes
        self.buffer = CandleBuffer()
        self.callbacks: List[Callable] = []
        self.running = False
        self.ws = None
        
        # REST client for initial data
        self.client = None
        if BINANCE_AVAILABLE:
            try:
                self.client = Client("", "", {"timeout": 30})
            except:
                pass
    
    def add_callback(self, callback: Callable):
        """Add callback for new candle events"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, symbol: str, timeframe: str, candle: Dict, is_closed: bool):
        """Notify all callbacks of new candle"""
        for cb in self.callbacks:
            try:
                cb(symbol, timeframe, candle, is_closed)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def fetch_initial_data(self, days: int = 7):
        """Fetch historical data to initialize buffers"""
        if not self.client:
            logger.warning("No REST client - starting with empty buffers")
            return
        
        logger.info("Fetching initial historical data...")
        
        for symbol in self.symbols:
            symbol_upper = symbol.upper()
            for tf in self.timeframes:
                try:
                    # Calculate limit based on timeframe
                    if tf == "15m":
                        limit = min(days * 96, 500)
                    elif tf == "1h":
                        limit = min(days * 24, 500)
                    else:
                        limit = 200
                    
                    klines = self.client.futures_klines(
                        symbol=symbol_upper,
                        interval=tf,
                        limit=limit
                    )
                    
                    for k in klines:
                        candle = {
                            'timestamp': k[0],
                            'open': float(k[1]),
                            'high': float(k[2]),
                            'low': float(k[3]),
                            'close': float(k[4]),
                            'volume': float(k[5])
                        }
                        self.buffer.add_candle(symbol_upper, tf, candle)
                    
                    logger.info(f"Loaded {len(klines)} {tf} candles for {symbol_upper}")
                    
                except Exception as e:
                    logger.error(f"Error fetching {symbol_upper} {tf}: {e}")
    
    def _parse_kline_message(self, msg: Dict) -> Optional[Dict]:
        """Parse WebSocket kline message"""
        if 'k' not in msg:
            return None
        
        k = msg['k']
        return {
            'symbol': k['s'],
            'timeframe': k['i'],
            'timestamp': k['t'],
            'open': float(k['o']),
            'high': float(k['h']),
            'low': float(k['l']),
            'close': float(k['c']),
            'volume': float(k['v']),
            'is_closed': k['x']
        }
    
    async def _connect(self):
        """Connect to WebSocket with automatic reconnection"""
        # Build stream names
        streams = []
        for symbol in self.symbols:
            for tf in self.timeframes:
                streams.append(f"{symbol}@kline_{tf}")
        
        url = f"{self.BINANCE_WS_URL}/{'/'.join(streams)}"
        
        # If multiple streams, use combined stream
        if len(streams) > 1:
            stream_str = "/".join(streams)
            url = f"wss://fstream.binance.com/stream?streams={stream_str}"
        
        # Reconnection settings
        max_retries = 5
        base_delay = 2  # seconds
        retry_count = 0
        
        while self.running or retry_count == 0:
            try:
                logger.info(f"Connecting to WebSocket...")
                
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self.ws = ws
                    self.running = True
                    retry_count = 0  # Reset on successful connection
                    logger.info("WebSocket connected!")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            
                            # Handle combined stream format
                            if 'data' in data:
                                data = data['data']
                            
                            parsed = self._parse_kline_message(data)
                            if parsed:
                                symbol = parsed['symbol']
                                tf = parsed['timeframe']
                                
                                candle = {
                                    'timestamp': parsed['timestamp'],
                                    'open': parsed['open'],
                                    'high': parsed['high'],
                                    'low': parsed['low'],
                                    'close': parsed['close'],
                                    'volume': parsed['volume']
                                }
                                
                                self.buffer.add_candle(symbol, tf, candle)
                                self._notify_callbacks(symbol, tf, candle, parsed['is_closed'])
                                
                        except asyncio.TimeoutError:
                            # Send ping to keep alive
                            await ws.ping()
                        except Exception as e:
                            logger.error(f"Message error: {e}")
                            break  # Break inner loop to reconnect
                            
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded. Stopping.")
                    self.running = False
                    break
                    
                delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
                logger.warning(f"WebSocket error: {e}. Retry {retry_count}/{max_retries} in {delay}s...")
                await asyncio.sleep(delay)
    
    
    def start(self):
        """Start the data feed (blocking)"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not installed. Run: pip install websockets")
            return
        
        # Fetch initial data
        self.fetch_initial_data()
        
        # Start WebSocket
        asyncio.run(self._connect())
    
    async def start_async(self):
        """Start the data feed (async)"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not installed")
            return
        
        self.fetch_initial_data()
        await self._connect()
    
    def stop(self):
        """Stop the data feed"""
        self.running = False
        if self.ws:
            asyncio.create_task(self.ws.close())
    
    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get current candle data as DataFrame"""
        return self.buffer.get_dataframe(symbol.upper(), timeframe)
    
    def get_latest(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get latest candle"""
        return self.buffer.get_latest(symbol.upper(), timeframe)


class SimulatedDataFeed:
    """Simulated data feed for testing without WebSocket - with REST API fallback"""
    
    def __init__(self, symbols: List[str], timeframes: List[str] = ["15m", "1h"]):
        self.symbols = [s.upper() for s in symbols]
        self.timeframes = timeframes
        self.buffer = CandleBuffer()
        self.callbacks: List[Callable] = []
        self.running = False
        
        # Try python-binance first, fallback to REST API
        self.client = None
        self.use_rest_fallback = False
        
        logger.info(f"SimulatedDataFeed init: BINANCE_AVAILABLE={BINANCE_AVAILABLE}")
        if BINANCE_AVAILABLE:
            try:
                self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, {"timeout": 30})
                logger.info("✅ Binance client created successfully")
            except Exception as e:
                logger.warning(f"⚠️ python-binance client failed: {e}, using REST fallback")
                self.use_rest_fallback = True
        else:
            logger.info("ℹ️ python-binance not available, using REST API fallback")
            self.use_rest_fallback = True
    
    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, symbol: str, timeframe: str, candle: Dict, is_closed: bool):
        for cb in self.callbacks:
            try:
                cb(symbol, timeframe, candle, is_closed)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def fetch_latest(self):
        """Fetch latest candles from REST API"""
        logger.info(f"Fetching data for {len(self.symbols)} symbols (REST fallback: {self.use_rest_fallback})...")
        
        for symbol in self.symbols:
            for tf in self.timeframes:
                try:
                    # Use REST API fallback or python-binance client
                    if self.use_rest_fallback or not self.client:
                        klines = fetch_klines_rest(symbol, tf, 200)
                    else:
                        klines = self.client.futures_klines(
                            symbol=symbol,
                            interval=tf,
                            limit=200
                        )
                    
                    if klines:
                        for k in klines:
                            candle = {
                                'timestamp': k[0],
                                'open': float(k[1]),
                                'high': float(k[2]),
                                'low': float(k[3]),
                                'close': float(k[4]),
                                'volume': float(k[5])
                            }
                            self.buffer.add_candle(symbol, tf, candle)
                        
                        # Notify for latest candle
                        self._notify_callbacks(symbol, tf, candle, True)
                        logger.info(f"✅ {symbol} {tf}: {len(klines)} candles loaded")
                    else:
                        logger.warning(f"⚠️ {symbol} {tf}: No data returned")
                        
                except Exception as e:
                    logger.error(f"❌ Fetch error for {symbol} {tf}: {e}")
    
    def start(self, interval_seconds: int = 60):
        """Start polling (blocking)"""
        logger.info(f"Starting simulated feed, polling every {interval_seconds}s")
        self.running = True
        
        self.fetch_latest()
        
        import time
        while self.running:
            time.sleep(interval_seconds)
            self.fetch_latest()
            logger.info(f"Data refreshed at {datetime.now()}")
    
    def stop(self):
        self.running = False
    
    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        return self.buffer.get_dataframe(symbol.upper(), timeframe)
    
    def get_latest(self, symbol: str, timeframe: str) -> Optional[Dict]:
        return self.buffer.get_latest(symbol.upper(), timeframe)


if __name__ == "__main__":
    # Test the data feed
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    def on_candle(symbol, timeframe, candle, is_closed):
        if is_closed:
            print(f"[CLOSED] {symbol} {timeframe}: {candle['close']}")
    
    # Use simulated feed for testing
    feed = SimulatedDataFeed(symbols, ["15m", "1h"])
    feed.add_callback(on_candle)
    
    print("Testing data feed...")
    feed.fetch_latest()
    
    for sym in symbols:
        for tf in ["15m", "1h"]:
            df = feed.get_dataframe(sym, tf)
            if df is not None:
                print(f"{sym} {tf}: {len(df)} candles, latest: {df['close'].iloc[-1]:.2f}")
