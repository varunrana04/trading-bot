"""
WebSocket Data Feed Handler
Manages real-time market data from Binance Futures WebSocket
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Callable, Optional
import websocket
from collections import deque


class BinanceDataFeed:
    """
    Real-time WebSocket data feed for Binance Futures
    Handles order book depth, trades, and ticker updates
    """
    
    def __init__(self, symbols: list, callbacks: Dict[str, Callable]):
        """
        Args:
            symbols: List of symbols to subscribe (e.g., ['BTCUSDT', 'ETHUSDT'])
            callbacks: Dict of callback functions {
                'orderbook': func(symbol, data),
                'trade': func(symbol, data),
                'ticker': func(symbol, data)
            }
        """
        self.symbols = [s.lower() for s in symbols]
        self.callbacks = callbacks
        self.ws = None
        self.running = False
        
        # Performance tracking
        self.message_count = 0
        self.last_latency = {}
        self.latency_buffer = {symbol: deque(maxlen=100) for symbol in symbols}
        
    def build_stream_url(self) -> str:
        """Build combined WebSocket URL for multiple streams"""
        base_url = "wss://fstream.binance.com/stream?streams="
        streams = []
        
        for symbol in self.symbols:
            # Order book depth updates (100ms)
            streams.append(f"{symbol}@depth20@100ms")
            # Aggregated trades
            streams.append(f"{symbol}@aggTrade")
            # 24hr ticker
            streams.append(f"{symbol}@ticker")
        
        return base_url + "/".join(streams)
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Measure latency
            receive_time = time.time() * 1000  # milliseconds
            
            data = json.loads(message)
            stream = data.get('stream', '')
            event_data = data.get('data', {})
            
            # Extract symbol and event type
            if '@depth' in stream:
                symbol = stream.split('@')[0].upper()
                event_type = 'orderbook'
                event_data['receive_time'] = receive_time
                
            elif '@aggTrade' in stream:
                symbol = stream.split('@')[0].upper()
                event_type = 'trade'
                event_data['receive_time'] = receive_time
                
            elif '@ticker' in stream:
                symbol = event_data.get('s', '').upper()
                event_type = 'ticker'
                event_data['receive_time'] = receive_time
            else:
                return
            
            # Calculate exchange-to-client latency
            if 'E' in event_data:  # Event time from exchange
                exchange_time = event_data['E']
                latency = receive_time - exchange_time
                self.last_latency[symbol] = latency
                self.latency_buffer[symbol].append(latency)
            
            # Call appropriate callback
            if event_type in self.callbacks:
                self.callbacks[event_type](symbol, event_data)
            
            self.message_count += 1
            
        except Exception as e:
            print(f"[ERROR] Data feed message error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"[ERROR] WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print(f"[WARN] WebSocket closed: {close_status_code} - {close_msg}")
        if self.running:
            print("[INFO] Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            self.start()
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        print(f"[INFO] WebSocket connected for {len(self.symbols)} symbols")
        print(f"[INFO] Subscribed to: {', '.join([s.upper() for s in self.symbols])}")
    
    def start(self):
        """Start WebSocket connection"""
        self.running = True
        url = self.build_stream_url()
        
        print(f"[INFO] Starting Binance data feed...")
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run WebSocket in blocking mode
        self.ws.run_forever()
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("[INFO] Data feed stopped")
    
    def get_stats(self) -> Dict:
        """Get performance statistics"""
        stats = {
            'messages_received': self.message_count,
            'latency': {}
        }
        
        for symbol in self.symbols:
            if len(self.latency_buffer[symbol]) > 0:
                latencies = list(self.latency_buffer[symbol])
                stats['latency'][symbol.upper()] = {
                    'current': self.last_latency.get(symbol.upper(), 0),
                    'avg': sum(latencies) / len(latencies),
                    'min': min(latencies),
                    'max': max(latencies)
                }
        
        return stats


# Example usage
if __name__ == "__main__":
    def on_orderbook(symbol, data):
        print(f"[{symbol}] Order Book Update - {len(data.get('b', []))} bids, {len(data.get('a', []))} asks")
    
    def on_trade(symbol, data):
        print(f"[{symbol}] Trade: {data['p']} @ {data['q']}")
    
    def on_ticker(symbol, data):
        print(f"[{symbol}] 24h: Vol={data['v']}, Change={data['P']}%")
    
    feed = BinanceDataFeed(
        symbols=['BTCUSDT', 'ETHUSDT'],
        callbacks={
            'orderbook': on_orderbook,
            'trade': on_trade,
            'ticker': on_ticker
        }
    )
    
    try:
        feed.start()
    except KeyboardInterrupt:
        feed.stop()
