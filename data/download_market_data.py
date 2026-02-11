# data/download_market_data.py
import os
import csv
import json
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import ccxt
from kiteconnect import KiteConnect

# Load configuration
CONFIG_PATH = "broker_config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Config file not found: {CONFIG_PATH}")
        return None
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

class MarketDataDownloader:
    def __init__(self):
        self.config = load_config()
        self.data_dir = "data/historical"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize Binance
        self.binance = ccxt.binance({
            'apiKey': self.config['binance']['api_key'],
            'secret': self.config['binance']['api_secret'],
            'enableRateLimit': True
        })
        
        # Initialize Zerodha
        self.kite = KiteConnect(api_key=self.config['zerodha']['api_key'])
        self.kite.set_access_token(self.config['zerodha']['access_token'])

    def download_binance_data(self, symbol, timeframe, days_back):
        """Download historical data from Binance."""
        print(f"\n" + "="*80)
        print(f"Downloading {symbol} from Binance")
        print(f"Timeframe: {timeframe} | Days: {days_back}")
        print("="*80 + "\n")
        
        filename = f"{symbol.replace('/', '_')}_{timeframe}_{days_back}d.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        since = self.binance.parse8601((datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d %H:%M:%S'))
        
        all_candles = []
        print("Fetching data...")
        
        while True:
            try:
                candles = self.binance.fetch_ohlcv(symbol, timeframe, since, limit=1000)
                if not candles:
                    break
                
                all_candles.extend(candles)
                since = candles[-1][0] + 1
                print(f"  Downloaded {len(all_candles)} candles...", end='\r')
                
                # Break if we've reached current time
                if candles[-1][0] >= self.binance.milliseconds() - 60000: # within last minute
                     break
                     
                time.sleep(0.5) # Rate limit
                
            except Exception as e:
                print(f"\nError downloading {symbol}: {e}")
                break
                
        if all_candles:
            # Save to CSV
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                for candle in all_candles:
                    # Convert timestamp to ISO format
                    candle[0] = datetime.fromtimestamp(candle[0]/1000).strftime('%Y-%m-%d %H:%M:%S')
                    writer.writerow(candle)
            
            print(f"\n[OK] Downloaded {len(all_candles)} candles")
            print(f"[OK] Saved to: {filepath}")
            
            # Show summary
            df = pd.read_csv(filepath)
            start_price = df.iloc[0]['close']
            end_price = df.iloc[-1]['close']
            ret = ((end_price - start_price) / start_price) * 100
            
            print(f"\nData Summary:")
            print(f"  Start Date: {df.iloc[0]['timestamp']}")
            print(f"  End Date: {df.iloc[-1]['timestamp']}")
            print(f"  Total Rows: {len(df)}")
            print(f"  Start Price: ${start_price:,.2f}")
            print(f"  End Price: ${end_price:,.2f}")
            print(f"  Total Return: {ret:+.2f}%")
            
        else:
            print("\n[WARNING] No data downloaded")

    def download_zerodha_data(self, symbol, days_back):
        """Download historical data from Zerodha."""
        print(f"\n" + "="*80)
        print(f"Downloading {symbol} from Zerodha")
        print(f"Days back: {days_back}")
        print("="*80 + "\n")
        
        filename = f"Zerodha_{symbol.replace(' ', '_')}_{days_back}d.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)
        
        print(f"Fetching data from {from_date.date()} to {to_date.date()}...")
        
        try:
            # Get instrument token
            instruments = self.kite.instruments("NSE")
            token = None
            for inst in instruments:
                if inst['name'] == symbol or inst['tradingsymbol'] == symbol:
                    token = inst['instrument_token']
                    break
            
            # Fallback for indices
            if not token:
                instruments = self.kite.instruments("INDICES")
                for inst in instruments:
                    if inst['name'] == symbol:
                        token = inst['instrument_token']
                        break
            
            if not token:
                print(f"[ERROR] Instrument token not found for {symbol}")
                return

            records = self.kite.historical_data(
                token, 
                from_date, 
                to_date, 
                "day",
                continuous=False
            )
            
            if records:
                # Save to CSV with standardized columns
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    for candle in records:
                        # Zerodha returns 'date' which is datetime object
                        timestamp = candle['date'].strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([
                            timestamp,
                            candle['open'],
                            candle['high'],
                            candle['low'],
                            candle['close'],
                            candle['volume']
                        ])
                
                print(f"[OK] Downloaded {len(records)} candles")
                print(f"[OK] Saved to: {filepath}")
                
                # Show summary
                df = pd.read_csv(filepath)
                start_price = df.iloc[0]['close']
                end_price = df.iloc[-1]['close']
                ret = ((end_price - start_price) / start_price) * 100
                
                print(f"\nData Summary:")
                print(f"  Start Date: {df.iloc[0]['timestamp']}")
                print(f"  End Date: {df.iloc[-1]['timestamp']}")
                print(f"  Total Days: {len(df)}")
                print(f"  Start Price: {start_price:,.2f}")
                print(f"  End Price: {end_price:,.2f}")
                print(f"  Total Return: {ret:+.2f}%")
                
            else:
                print("[WARNING] No data returned from API")
                
        except Exception as e:
            print(f"[ERROR] Failed to download {symbol}: {e}")

def main():
    downloader = MarketDataDownloader()
    
    print("="*80)
    print("DOWNLOADING ALL STANDARD MARKET DATA")
    print("="*80)
    
    # 1. Crypto Data (Binance)
    # Download for all requested lookbacks and timeframes
    crypto_symbols = ['BTC/USDT', 'ETH/USDT']
    crypto_timeframes = ['5m', '15m', '30m', '1h', '1d']
    lookbacks = [30, 365, 1825, 3650]
    
    for symbol in crypto_symbols:
        for tf in crypto_timeframes:
            for days in lookbacks:
                # Skip very long lookbacks for high frequency data to save time/space if needed
                # But user requested exhaustive, so we try all.
                print(f"\n[1/3] Processing {symbol} {tf} {days}d...")
                downloader.download_binance_data(symbol, tf, days)

    # 2. Indian Market Data (Zerodha)
    # Indices don't have volume usually, but we keep the format
    indian_symbols = ['NIFTY 50', 'BANK NIFTY', 'SENSEX'] # Added SENSEX
    
    for symbol in indian_symbols:
        for days in lookbacks:
            print(f"\n[2/3] Processing {symbol} {days}d...")
            downloader.download_zerodha_data(symbol, days)
            
    print("\n" + "="*80)
    print("DOWNLOAD COMPLETE")
    print("="*80)
    print("\n[OK] All data saved to: data/historical")
    print("\nNEXT STEPS:")
    print("1. Run backtests/optimizer.py")
    print("2. Review optimizer_report.md")

if __name__ == "__main__":
    main()
