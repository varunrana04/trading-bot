"""
Complete Binance Futures Integration
Handles crypto futures trading with real API
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, List, Optional
import pandas as pd
import time


class BinanceFuturesClient:
    """
    Binance Futures broker integration
    """
    
    def __init__(self, api_key: str, api_secret: str, paper_trading: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper_trading = paper_trading  # PAPER TRADING MODE - no real orders
        
        # Initialize Binance Client
        try:
            self.client = Client(api_key, api_secret)
            
            # Test connection
            self.client.ping()
            
            if self.paper_trading:
                print("[BINANCE] ✓ Connected in PAPER TRADING mode (simulated orders)")
            else:
                print("[BINANCE] ✓ Connected successfully (LIVE TRADING)")
            
        except Exception as e:
            print(f"[BINANCE] ✗ Connection failed: {e}")
            self.client = None
    
    def place_order(self, signal: Dict, position_size: float) -> Dict:
        """
        Place futures order on Binance (or simulate if paper trading)
        
        Args:
            signal: {
                'action': 'LONG'|'SHORT'|'CLOSE',
                'symbol': 'BTCUSDT',
                'quantity': 0.001,
                'leverage': 5
            }
            position_size: USD value
        
        Returns:
            Order details
        """
        try:
            symbol = signal.get('symbol', 'BTCUSDT')
            action = signal.get('action', 'LONG')
            
            # Get current price
            price = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            
            # Calculate quantity
            if 'quantity' in signal:
                quantity = signal['quantity']
            else:
                quantity = round(position_size / price, 3)
            
            leverage = signal.get('leverage', 5)
            
            # PAPER TRADING MODE - Simulate order
            if self.paper_trading:
                print(f"[BINANCE PAPER] ✓ Simulated order: {symbol} {action} {quantity} @ ${price:,.2f} ({leverage}x)")
                
                return {
                    'status': 'FILLED',
                    'order_id': f'PAPER_{int(time.time())}',
                    'symbol': symbol,
                    'side': action,
                    'quantity': quantity,
                    'price': price,
                    'time': pd.Timestamp.now(),
                    'paper_trade': True
                }
            
            # LIVE TRADING MODE - Real order (requires balance)
            else:
                # Set leverage
                self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
                
                # Determine side
                if action in ['LONG', 'BUY']:
                    side = Client.SIDE_BUY
                elif action in ['SHORT', 'SELL']:
                    side = Client.SIDE_SELL
                else:
                    return {'status': 'INVALID_ACTION'}
                
                # Place order
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=quantity
                )
                
                print(f"[BINANCE LIVE] ✓ Order filled: {symbol} {action} {quantity}")
                
                return {
                    'status': 'FILLED',
                    'order_id': order.get('orderId', ''),
                    'symbol': symbol,
                    'side': action,
                    'quantity': quantity,
                    'price': float(order.get('avgPrice', 0)),
                    'time': pd.Timestamp.now(),
                    'paper_trade': False
                }
            
        except BinanceAPIException as e:
            print(f"[BINANCE] ✗ Order failed: {e}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    def get_funding_rate(self, symbol: str = 'BTCUSDT') -> float:
        """
        Get current funding rate for perpetual futures
        
        Returns:
            Funding rate (e.g., 0.0001 = 0.01%)
        """
        try:
            funding_info = self.client.futures_funding_rate(symbol=symbol, limit=1)
            
            if funding_info:
                rate = float(funding_info[0]['fundingRate'])
                return rate
            
            return 0.0
            
        except Exception as e:
            print(f"[BINANCE] ✗ Funding rate fetch failed: {e}")
            return 0.0
    
    def get_mark_price(self, symbol: str) -> float:
        """Get mark price (fair value)"""
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            return float(ticker['markPrice'])
        except:
            return 0.0
    
    def get_futures_price(self, symbol: str) -> float:
        """Get current futures price"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except:
            return 0.0
    
    def get_spot_price(self, symbol: str) -> float:
        """Get spot price (remove USDT for spot symbol)"""
        try:
            # Convert BTCUSDT to BTC/USDT for spot
            spot_symbol = symbol  # Already in correct format
            ticker = self.client.get_symbol_ticker(symbol=spot_symbol)
            return float(ticker['price'])
        except:
            return 0.0
    
    def calculate_basis(self, symbol: str) -> float:
        """
        Calculate basis (futures - spot)
        
        Returns:
            Basis in percentage
        """
        futures_price = self.get_futures_price(symbol)
        spot_price = self.get_spot_price(symbol)
        
        if spot_price > 0:
            basis_pct = ((futures_price - spot_price) / spot_price) * 100
            return basis_pct
        
        return 0.0
    
    def get_account_balance(self) -> Dict:
        """Get futures account balance"""
        try:
            account = self.client.futures_account()
            return {
                'balance': float(account.get('totalWalletBalance', 0)),
                'available': float(account.get('availableBalance', 0)),
                'unrealized_pnl': float(account.get('totalUnrealizedProfit', 0))
            }
        except Exception as e:
            print(f"[BINANCE] ✗ Balance fetch failed: {e}")
            return {'balance': 0, 'available': 0, 'unrealized_pnl': 0}
    
    def get_positions(self) -> List[Dict]:
        """Get all open futures positions"""
        try:
            positions = self.client.futures_position_information()
            
            # Filter only positions with non-zero size
            open_positions = [
                pos for pos in positions
                if float(pos.get('positionAmt', 0)) != 0
            ]
            
            return open_positions
            
        except Exception as e:
            print(f"[BINANCE] ✗ Positions fetch failed: {e}")
            return []
    
    def close_position(self, symbol: str):
        """Close a specific futures position"""
        try:
            positions = self.get_positions()
            
            for pos in positions:
                if pos['symbol'] == symbol:
                    position_amt = float(pos['positionAmt'])
                    
                    if position_amt == 0:
                        continue
                    
                    # Determine close side (opposite of position)
                    side = Client.SIDE_SELL if position_amt > 0 else Client.SIDE_BUY
                    quantity = abs(position_amt)
                    
                    # Place closing order
                    self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=quantity,
                        reduceOnly=True
                    )
                    
                    print(f"[BINANCE] ✓ Closed position: {symbol}")
                    
        except Exception as e:
            print(f"[BINANCE] ✗ Close position failed: {e}")
    
    def get_historical_klines(
        self,
        symbol: str,
        interval: str = '1h',
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get historical candlestick data
        
        Args:
            symbol: 'BTCUSDT'
            interval: '1m', '5m', '15m', '1h', '4h', '1d'
            limit: Number of candles
        """
        try:
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            print(f"[BINANCE] ✗ Historical data fetch failed: {e}")
            return pd.DataFrame()
