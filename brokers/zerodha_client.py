"""
Complete Zerodha Kite Connect Integration
Handles options and stock trading with real API
"""

from kiteconnect import KiteConnect
from typing import Dict, List, Optional
import pandas as pd


class ZerodhaClient:
    """
    Zerodha broker integration with Kite Connect
    """
    
    def __init__(self, api_key: str, api_secret: str, access_token: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Initialize Kite Connect
        self.kite = KiteConnect(api_key=api_key)
        
        if access_token:
            self.kite.set_access_token(access_token)
            print("[ZERODHA] ✓ Connected with access token")
        else:
            print("[ZERODHA] ⚠ Need to generate access token")
            print(f"[ZERODHA] Login URL: {self.kite.login_url()}")
    
    def set_access_token(self, request_token: str):
        """Generate and set access token"""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.kite.set_access_token(data["access_token"])
            print("[ZERODHA] ✓ Access token generated")
            return data["access_token"]
        except Exception as e:
            print(f"[ZERODHA] ✗ Token generation failed: {e}")
            return None
    
    def place_order(self, signal: Dict, position_size: float) -> Dict:
        """
        Place order on Zerodha
        
        Args:
            signal: {
                'action': 'BUY'|'SELL'|'ENTER'|'EXIT',
                'symbol': 'NIFTY'|stock name,
                'tradingsymbol': 'NIFTY25JAN24000CE',
                'quantity': lot_size,
                'price': limit_price (optional)
            }
            position_size: Capital allocated
        
        Returns:
            Order details
        """
        try:
            action = signal.get('action', 'BUY')
            transaction_type = self.kite.TRANSACTION_TYPE_BUY if action in ['BUY', 'ENTER'] else self.kite.TRANSACTION_TYPE_SELL
            
            # Determine exchange
            if 'NIFTY' in signal.get('tradingsymbol', '') or 'BANKNIFTY' in signal.get('tradingsymbol', ''):
                exchange = self.kite.EXCHANGE_NFO  # Options
            else:
                exchange = self.kite.EXCHANGE_NSE  # Stocks
            
            # Place order
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=signal.get('tradingsymbol', signal.get('symbol', '')),
                transaction_type=transaction_type,
                quantity=int(signal.get('quantity', 1)),
                order_type=self.kite.ORDER_TYPE_LIMIT if 'price' in signal else self.kite.ORDER_TYPE_MARKET,
                product=self.kite.PRODUCT_MIS,  # Intraday
                price=signal.get('price', 0) if 'price' in signal else None
            )
            
            print(f"[ZERODHA] ✓ Order placed: {order_id}")
            
            return {
                'status': 'PLACED',
                'order_id': order_id,
                'symbol': signal.get('tradingsymbol', ''),
                'quantity': signal.get('quantity', 0),
                'time': pd.Timestamp.now()
            }
            
        except Exception as e:
            print(f"[ZERODHA] ✗ Order failed: {e}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> pd.DataFrame:
        """
        Get option chain for NIFTY/BANKNIFTY
        
        Args:
            symbol: 'NIFTY' or 'BANKNIFTY'
            expiry: Expiry date (optional, uses nearest if not provided)
        
        Returns:
            DataFrame with option chain
        """
        try:
            # Get instruments
            instruments = self.kite.instruments(self.kite.EXCHANGE_NFO)
            df = pd.DataFrame(instruments)
            
            # Filter by symbol
            df = df[df['name'] == symbol]
            
            # Filter by expiry if provided
            if expiry:
                df = df[df['expiry'] == expiry]
            else:
                # Get nearest expiry
                df = df[df['expiry'] == df['expiry'].min()]
            
            return df
            
        except Exception as e:
            print(f"[ZERODHA] ✗ Option chain fetch failed: {e}")
            return pd.DataFrame()
    
    def get_stock_quote(self, symbol: str) -> Dict:
        """Get real-time stock quote"""
        try:
            quote = self.kite.quote(f"NSE:{symbol}")
            return quote.get(f"NSE:{symbol}", {})
        except Exception as e:
            print(f"[ZERODHA] ✗ Quote fetch failed: {e}")
            return {}
    
    def get_historical_data(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str = 'day'
    ) -> pd.DataFrame:
        """
        Get historical data for stocks
        
        Args:
            symbol: Stock symbol
            from_date: 'YYYY-MM-DD'
            to_date: 'YYYY-MM-DD'
            interval: 'minute', 'day', '5minute', etc.
        """
        try:
            instrument_token = self._get_instrument_token(symbol)
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            return pd.DataFrame(data)
            
        except Exception as e:
            print(f"[ZERODHA] ✗ Historical data fetch failed: {e}")
            return pd.DataFrame()
    
    def _get_instrument_token(self, symbol: str) -> int:
        """Get instrument token for a symbol"""
        try:
            instruments = self.kite.instruments(self.kite.EXCHANGE_NSE)
            df = pd.DataFrame(instruments)
            token = df[df['tradingsymbol'] == symbol]['instrument_token'].values[0]
            return token
        except:
            return 0
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            positions = self.kite.positions()
            return positions.get('net', [])
        except Exception as e:
            print(f"[ZERODHA] ✗ Positions fetch failed: {e}")
            return []
    
    def close_position(self, tradingsymbol: str):
        """Close a specific position"""
        try:
            positions = self.get_positions()
            
            for pos in positions:
                if pos['tradingsymbol'] == tradingsymbol and pos['quantity'] != 0:
                    # Place reverse order
                    transaction_type = self.kite.TRANSACTION_TYPE_SELL if pos['quantity'] > 0 else self.kite.TRANSACTION_TYPE_BUY
                    
                    self.kite.place_order(
                        variety=self.kite.VARIETY_REGULAR,
                        exchange=pos['exchange'],
                        tradingsymbol=tradingsymbol,
                        transaction_type=transaction_type,
                        quantity=abs(pos['quantity']),
                        order_type=self.kite.ORDER_TYPE_MARKET,
                        product=pos['product']
                    )
                    
                    print(f"[ZERODHA] ✓ Closed position: {tradingsymbol}")
                    
        except Exception as e:
            print(f"[ZERODHA] ✗ Close position failed: {e}")
