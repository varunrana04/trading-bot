"""
Position Manager
Tracks all open positions across strategies
"""

from typing import Dict, List, Optional
from collections import defaultdict


class PositionManager:
    """
    Unified position tracking across all markets
    """
    
    def __init__(self, max_positions: int = 50):
        self.max_positions = max_positions
        
        # Positions: {position_id: {strategy, symbol, side, entry, qty, ...}}
        self.positions = {}
        self.next_id = 1
        
    def add_position(self, strategy_name: str, order: Dict):
        """Add a new position"""
        position_id = self.next_id
        self.next_id += 1
        
        self.positions[position_id] = {
            'strategy': strategy_name,
            'symbol': order.get('symbol', ''),
            'side': order.get('side', ''),
            'entry_price': order.get('price', 0),
            'quantity': order.get('quantity', 0),
            'entry_time': order.get('time', 0)
        }
        
        return position_id
    
    def remove_position(self, position_id: int):
        """Close and remove a position"""
        if position_id in self.positions:
            del self.positions[position_id]
    
    def position_count(self) -> int:
        """Get number of open positions"""
        return len(self.positions)
    
    def get_positions_by_strategy(self, strategy_name: str) -> List[Dict]:
        """Get all positions for a strategy"""
        return [
            pos for pos in self.positions.values()
            if pos['strategy'] == strategy_name
        ]
    
    def close_all_positions(self, zerodha_client, binance_client):
        """Close all open positions (emergency shutdown)"""
        print(f"[POSITION MGR] Closing {len(self.positions)} positions...")
        
        for pos_id, position in list(self.positions.items()):
            try:
                # Close via appropriate broker
                # (Simplified - would need actual close logic)
                self.remove_position(pos_id)
            except Exception as e:
                print(f"[ERROR] Failed to close position {pos_id}: {e}")
