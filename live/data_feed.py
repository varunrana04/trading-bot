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
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional
import pandas as pd
import numpy as np

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    from binance.client import Client
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    Client = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataFeed")


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
            except Exception as e:
                logger.warning(f"Could not initialize Binance REST client: {e}")
    
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
    
    def fetch_initial_data(self, days: int = 3):
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
                
                time.sleep(0.5)  # Rate-limit protection between requests
    
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
    """Simulated data feed for testing without WebSocket"""
    
    def __init__(self, symbols: List[str], timeframes: List[str] = ["15m", "1h"]):
        self.symbols = [s.upper() for s in symbols]
        self.timeframes = timeframes
        self.buffer = CandleBuffer()
        self.callbacks: List[Callable] = []
        self.running = False
        
        self.client = None
        if BINANCE_AVAILABLE:
            try:
                self.client = Client("", "", {"timeout": 30})
            except Exception as e:
                logger.warning(f"Could not initialize Binance REST client: {e}")
    
    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, symbol: str, timeframe: str, candle: Dict, is_closed: bool):
        for cb in self.callbacks:
            try:
                cb(symbol, timeframe, candle, is_closed)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def fetch_latest(self):
        """Fetch latest candles from REST API with rate-limit protection"""
        if not self.client:
            return
        
        for symbol in self.symbols:
            for tf in self.timeframes:
                try:
                    klines = self.client.futures_klines(
                        symbol=symbol,
                        interval=tf,
                        limit=200
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
                        self.buffer.add_candle(symbol, tf, candle)
                    
                    # Notify for latest candle
                    if klines:
                        self._notify_callbacks(symbol, tf, candle, True)
                        
                except Exception as e:
                    logger.error(f"Fetch error: {e}")
                
                time.sleep(0.5)  # Rate-limit protection between requests
    
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
