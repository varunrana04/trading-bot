"""
Order Book Reconstruction
Maintains real-time Level 2 order book from WebSocket depth updates
"""

import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import bisect


class OrderBook:
    """
    Real-time order book reconstruction from Binance depth snapshots
    Optimized for fast access and OBI calculation
    """
    
    def __init__(self, symbol: str, depth_levels: int = 20):
        """
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            depth_levels: Number of price levels to track
        """
        self.symbol = symbol
        self.depth_levels = depth_levels
        
        # Order book data: {price: quantity}
        self.bids = {}  # Buy orders (descending price)
        self.asks = {}  # Sell orders (ascending price)
        
        # Sorted price lists for fast access
        self.bid_prices = []  # Sorted descending
        self.ask_prices = []  # Sorted ascending
        
        # Metadata
        self.last_update_id = 0
        self.last_update_time = 0
        self.update_count = 0
        
    def update(self, depth_data: Dict):
        """
        Update order book from depth snapshot
        
        Args:
            depth_data: {
                'b': [[price, qty], ...],  # Bids
                'a': [[price, qty], ...],  # Asks
                'E': event_time,
                'u': last_update_id
            }
        """
        try:
            # Update metadata
            self.last_update_id = depth_data.get('u', 0)
            self.last_update_time = depth_data.get('E', 0)
            
            # Process bids
            self.bids.clear()
            self.bid_prices.clear()
            for price_str, qty_str in depth_data.get('b', []):
                price = float(price_str)
                qty = float(qty_str)
                if qty > 0:  # Only add non-zero quantities
                    self.bids[price] = qty
                    self.bid_prices.append(price)
            
            # Sort bids descending (highest price first)
            self.bid_prices.sort(reverse=True)
            
            # Process asks
            self.asks.clear()
            self.ask_prices.clear()
            for price_str, qty_str in depth_data.get('a', []):
                price = float(price_str)
                qty = float(qty_str)
                if qty > 0:
                    self.asks[price] = qty
                    self.ask_prices.append(price)
            
            # Sort asks ascending (lowest price first)
            self.ask_prices.sort()
            
            self.update_count += 1
            
        except Exception as e:
            print(f"[ERROR] Order book update failed for {self.symbol}: {e}")
    
    def get_best_bid(self) -> Optional[Tuple[float, float]]:
        """Get best bid (highest buy price)"""
        if self.bid_prices:
            price = self.bid_prices[0]
            return price, self.bids[price]
        return None
    
    def get_best_ask(self) -> Optional[Tuple[float, float]]:
        """Get best ask (lowest sell price)"""
        if self.ask_prices:
            price = self.ask_prices[0]
            return price, self.asks[price]
        return None
    
    def get_mid_price(self) -> Optional[float]:
        """Get mid price (average of best bid and ask)"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2.0
        return None
    
    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None
    
    def get_spread_pct(self) -> Optional[float]:
        """Get spread as percentage of mid price"""
        spread = self.get_spread()
        mid = self.get_mid_price()
        
        if spread and mid:
            return (spread / mid) * 100
        return None
    
    def get_bid_depth(self, levels: Optional[int] = None) -> float:
        """Get total bid volume up to N levels"""
        if levels is None:
            levels = self.depth_levels
        
        total = 0.0
        for i, price in enumerate(self.bid_prices[:levels]):
            total += self.bids[price]
        return total
    
    def get_ask_depth(self, levels: Optional[int] = None) -> float:
        """Get total ask volume up to N levels"""
        if levels is None:
            levels = self.depth_levels
        
        total = 0.0
        for i, price in enumerate(self.ask_prices[:levels]):
            total += self.asks[price]
        return total
    
    def get_weighted_mid_price(self, levels: int = 5) -> Optional[float]:
        """
        Calculate volume-weighted mid price (VWAP-style)
        More accurate than simple mid price
        """
        if not self.bid_prices or not self.ask_prices:
            return None
        
        bid_volume = 0.0
        bid_value = 0.0
        for i, price in enumerate(self.bid_prices[:levels]):
            qty = self.bids[price]
            bid_volume += qty
            bid_value += price * qty
        
        ask_volume = 0.0
        ask_value = 0.0
        for i, price in enumerate(self.ask_prices[:levels]):
            qty = self.asks[price]
            ask_volume += qty
            ask_value += price * qty
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return None
        
        total_value = bid_value + ask_value
        return total_value / total_volume
    
    def get_order_book_imbalance(self, levels: Optional[int] = None) -> float:
        """
        Calculate Order Book Imbalance (OBI)
        
        OBI = (Bid_Volume - Ask_Volume) / (Bid_Volume + Ask_Volume)
        
        Returns:
            Value between -1 and +1
            > 0.3: Strong buy pressure (price likely to rise)
            < -0.3: Strong sell pressure (price likely to fall)
        """
        bid_depth = self.get_bid_depth(levels)
        ask_depth = self.get_ask_depth(levels)
        
        total_depth = bid_depth + ask_depth
        if total_depth == 0:
            return 0.0
        
        obi = (bid_depth - ask_depth) / total_depth
        return obi
    
    def get_stats(self) -> Dict:
        """Get order book statistics"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        return {
            'symbol': self.symbol,
            'best_bid': best_bid[0] if best_bid else None,
            'best_bid_qty': best_bid[1] if best_bid else None,
            'best_ask': best_ask[0] if best_ask else None,
            'best_ask_qty': best_ask[1] if best_ask else None,
            'mid_price': self.get_mid_price(),
            'spread': self.get_spread(),
            'spread_pct': self.get_spread_pct(),
            'bid_depth': self.get_bid_depth(),
            'ask_depth': self.get_ask_depth(),
            'obi': self.get_order_book_imbalance(),
            'update_count': self.update_count,
            'last_update': self.last_update_time
        }
    
    def __repr__(self):
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return f"OrderBook({self.symbol}: {best_bid[0] if best_bid else 'N/A'} / {best_ask[0] if best_ask else 'N/A'})"


class OrderBookManager:
    """Manages multiple order books for different symbols"""
    
    def __init__(self, symbols: List[str], depth_levels: int = 20):
        self.books = {
            symbol: OrderBook(symbol, depth_levels)
            for symbol in symbols
        }
    
    def update(self, symbol: str, depth_data: Dict):
        """Update order book for symbol"""
        if symbol in self.books:
            self.books[symbol].update(depth_data)
    
    def get_book(self, symbol: str) -> Optional[OrderBook]:
        """Get order book for symbol"""
        return self.books.get(symbol)
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all order books"""
        return {
            symbol: book.get_stats()
            for symbol, book in self.books.items()
        }


# Example usage
if __name__ == "__main__":
    # Test order book
    book = OrderBook('BTCUSDT')
    
    # Simulate depth update
    test_data = {
        'u': 12345,
        'E': int(time.time() * 1000),
        'b': [  # Bids (buy orders)
            ['99000.00', '1.5'],
            ['98999.00', '2.0'],
            ['98998.00', '0.8'],
        ],
        'a': [  # Asks (sell orders)
            ['99001.00', '1.2'],
            ['99002.00', '1.8'],
            ['99003.00', '0.5'],
        ]
    }
    
    book.update(test_data)
    
    print("Order Book Stats:")
    print(f"  Best Bid: ${book.get_best_bid()[0]:,.2f} x {book.get_best_bid()[1]}")
    print(f"  Best Ask: ${book.get_best_ask()[0]:,.2f} x {book.get_best_ask()[1]}")
    print(f"  Mid Price: ${book.get_mid_price():,.2f}")
    print(f"  Spread: ${book.get_spread():.2f} ({book.get_spread_pct():.4f}%)")
    print(f"  Bid Depth: {book.get_bid_depth():.2f}")
    print(f"  Ask Depth: {book.get_ask_depth():.2f}")
    print(f"  OBI: {book.get_order_book_imbalance():.4f}")
