"""
Correlation Guard — Prevents over-exposure to correlated assets.

BTC, ETH, SOL are highly correlated crypto assets.
XAU, XAG are correlated precious metals.
This guard limits same-direction positions within each group.

Usage:
    from core.correlation_guard import CorrelationGuard
    
    guard = CorrelationGuard()
    can_open, reason = guard.can_open("ETHUSDT", "BUY", current_positions)
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("CorrelationGuard")

# Correlation groups — assets that tend to move together
CORRELATION_GROUPS = {
    "crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "metals": ["XAUUSDT", "XAGUSDT"],
}

# Max same-direction positions per group
MAX_SAME_DIRECTION_PER_GROUP = 2


class CorrelationGuard:
    """
    Prevents over-exposure to correlated assets.
    
    If 2 crypto positions are already LONG, blocks opening another crypto LONG.
    Metal group is independent from crypto group.
    """
    
    def __init__(self, max_per_group: int = MAX_SAME_DIRECTION_PER_GROUP,
                 groups: Dict[str, List[str]] = None):
        self.max_per_group = max_per_group
        self.groups = groups or CORRELATION_GROUPS
        
        # Build reverse lookup: symbol -> group name
        self._symbol_to_group = {}
        for group_name, symbols in self.groups.items():
            for symbol in symbols:
                self._symbol_to_group[symbol] = group_name
    
    def can_open(self, symbol: str, direction: str, 
                 positions: Dict) -> Tuple[bool, str]:
        """
        Check if a new position is allowed given correlation limits.
        
        Args:
            symbol: The symbol to open (e.g., "ETHUSDT")
            direction: "BUY" or "SELL"
            positions: Dict of symbol -> position objects with .direction attr
        
        Returns:
            (allowed, reason) — True if allowed, False with explanation if blocked
        """
        group = self._symbol_to_group.get(symbol)
        
        if not group:
            # Unknown symbol, no group restriction
            return True, ""
        
        group_symbols = self.groups[group]
        
        # Count same-direction positions in this group
        same_dir_count = 0
        same_dir_symbols = []
        
        for sym in group_symbols:
            if sym == symbol:
                continue
            pos = positions.get(sym)
            if pos is None:
                continue
            
            pos_dir = getattr(pos, 'direction', None) or pos.get('direction', '') if isinstance(pos, dict) else getattr(pos, 'direction', '')
            
            if pos_dir == direction:
                same_dir_count += 1
                same_dir_symbols.append(sym)
        
        if same_dir_count >= self.max_per_group:
            reason = (
                f"Correlation limit: {same_dir_count} {direction} positions "
                f"already open in {group} group ({', '.join(same_dir_symbols)}). "
                f"Max {self.max_per_group} allowed."
            )
            logger.warning(f"BLOCKED {symbol} {direction}: {reason}")
            return False, reason
        
        return True, ""
    
    def get_group_exposure(self, positions: Dict) -> Dict[str, Dict]:
        """Get exposure summary per group."""
        exposure = {}
        for group_name, symbols in self.groups.items():
            longs = []
            shorts = []
            for sym in symbols:
                pos = positions.get(sym)
                if pos is None:
                    continue
                direction = getattr(pos, 'direction', None) or (pos.get('direction', '') if isinstance(pos, dict) else '')
                if direction == "BUY":
                    longs.append(sym)
                elif direction == "SELL":
                    shorts.append(sym)
            exposure[group_name] = {
                "longs": longs, "shorts": shorts,
                "net": len(longs) - len(shorts)
            }
        return exposure


# Self-test
if __name__ == "__main__":
    guard = CorrelationGuard(max_per_group=2)
    
    print("=" * 50)
    print("  CORRELATION GUARD - SELF TEST")
    print("=" * 50)
    
    # Simulated positions
    class MockPos:
        def __init__(self, d): self.direction = d
    
    positions = {
        "BTCUSDT": MockPos("BUY"),
        "ETHUSDT": MockPos("BUY"),
    }
    
    # Test 1: Should block 3rd crypto LONG
    ok, reason = guard.can_open("SOLUSDT", "BUY", positions)
    assert not ok, "Should have blocked 3rd crypto long"
    print(f"[OK] Test 1: Blocked 3rd crypto LONG - {reason[:50]}")
    
    # Test 2: Should allow crypto SHORT (different direction)
    ok, reason = guard.can_open("SOLUSDT", "SELL", positions)
    assert ok, "Should allow SHORT in same group"
    print(f"[OK] Test 2: Allowed crypto SHORT")
    
    # Test 3: Should allow metals (different group)
    ok, reason = guard.can_open("XAUUSDT", "BUY", positions)
    assert ok, "Should allow different group"
    print(f"[OK] Test 3: Allowed metals BUY (different group)")
    
    # Test 4: Exposure summary
    exp = guard.get_group_exposure(positions)
    assert exp["crypto"]["net"] == 2
    print(f"[OK] Test 4: Exposure summary correct")
    
    print("\nAll tests passed!")
