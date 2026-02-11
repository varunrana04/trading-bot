"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    STATE MANAGER - CRASH RECOVERY                           ║
║  Persists open positions, allows graceful shutdown and restart recovery     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
    from core.state_manager import StateManager

    sm = StateManager()
    
    # Save state every cycle
    sm.save_positions(positions_dict)
    
    # On startup, recover
    positions = sm.load_positions()
    
    # Register shutdown handler
    sm.register_signal_handlers(cleanup_func)
"""

import json
import os
import signal
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import asdict

logger = logging.getLogger("StateManager")


class StateManager:
    """
    Manages persistent state for crash recovery.
    
    Saves open positions and bot state to disk every cycle, 
    allowing the bot to recover after unexpected crashes.
    """
    
    DEFAULT_STATE_DIR = "results/bot_state"
    
    def __init__(self, state_dir: str = None):
        self.state_dir = state_dir or self.DEFAULT_STATE_DIR
        os.makedirs(self.state_dir, exist_ok=True)
        
        self._state_file = os.path.join(self.state_dir, "bot_state.json")
        self._backup_file = os.path.join(self.state_dir, "bot_state.backup.json")
        self._shutdown_requested = False
        self._cleanup_callbacks: List[Callable] = []
        
        logger.info(f"StateManager initialized at {self.state_dir}")
    
    # ═══════════════════════════════════════════════════════════════════════
    #                       POSITION PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_positions(self, positions: Dict, balance: float = 0, 
                       extra_data: Dict = None):
        """
        Save current positions and state to disk.
        
        Called every trading cycle to ensure crash recovery.
        Uses atomic write (write to temp, then rename) to prevent corruption.
        
        Args:
            positions: Dict of symbol -> position data (dataclass or dict)
            balance: Current balance
            extra_data: Any additional state to persist
        """
        state = {
            "timestamp": datetime.now().isoformat(),
            "balance": balance,
            "positions": {},
            "extra": extra_data or {}
        }
        
        # Convert positions (handle dataclass objects)
        for symbol, pos in positions.items():
            if hasattr(pos, '__dataclass_fields__'):
                state["positions"][symbol] = asdict(pos)
            elif isinstance(pos, dict):
                state["positions"][symbol] = pos
            else:
                state["positions"][symbol] = str(pos)
        
        # Atomic write: write to temp file, then rename
        temp_file = self._state_file + ".tmp"
        try:
            # Backup current state first
            if os.path.exists(self._state_file):
                shutil.copy2(self._state_file, self._backup_file)
            
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            # Atomic rename
            os.replace(temp_file, self._state_file)
            
            n_pos = len(state["positions"])
            if n_pos > 0:
                logger.debug(f"State saved: {n_pos} positions, balance=${balance:.2f}")
                
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def load_positions(self) -> Optional[Dict]:
        """
        Load saved positions from disk.
        
        Returns:
            Dict with keys: timestamp, balance, positions, extra
            Returns None if no saved state exists
        """
        # Try primary state file first
        for filepath in [self._state_file, self._backup_file]:
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r') as f:
                        state = json.load(f)
                    
                    n_pos = len(state.get("positions", {}))
                    age = self._state_age(state.get("timestamp", ""))
                    
                    logger.info(
                        f"Loaded state from {os.path.basename(filepath)}: "
                        f"{n_pos} positions, age={age}"
                    )
                    return state
                    
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not load {filepath}: {e}")
                    continue
        
        logger.info("No saved state found — starting fresh")
        return None
    
    def clear_state(self):
        """Clear saved state (called on clean shutdown with no open positions)."""
        for filepath in [self._state_file, self._backup_file]:
            if os.path.exists(filepath):
                os.remove(filepath)
        logger.info("State cleared")
    
    def has_saved_state(self) -> bool:
        """Check if there is saved state to recover."""
        return os.path.exists(self._state_file) or os.path.exists(self._backup_file)
    
    def _state_age(self, timestamp_str: str) -> str:
        """Calculate human-readable age of saved state."""
        try:
            saved_time = datetime.fromisoformat(timestamp_str)
            delta = datetime.now() - saved_time
            
            if delta.total_seconds() < 60:
                return f"{int(delta.total_seconds())}s"
            elif delta.total_seconds() < 3600:
                return f"{int(delta.total_seconds() / 60)}m"
            elif delta.total_seconds() < 86400:
                return f"{delta.total_seconds() / 3600:.1f}h"
            else:
                return f"{delta.days}d"
        except (ValueError, TypeError):
            return "unknown"
    
    # ═══════════════════════════════════════════════════════════════════════
    #                      GRACEFUL SHUTDOWN
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_signal_handlers(self, cleanup_func: Callable = None):
        """
        Register OS signal handlers for graceful shutdown.
        
        Catches SIGINT (Ctrl+C) and SIGTERM to allow clean exit.
        
        Args:
            cleanup_func: Optional function to call during shutdown
        """
        if cleanup_func:
            self._cleanup_callbacks.append(cleanup_func)
        
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        logger.info("Signal handlers registered for graceful shutdown")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} — initiating graceful shutdown...")
        
        self._shutdown_requested = True
        
        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Cleanup callback error: {e}")
        
        logger.info("Graceful shutdown complete")
    
    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested
    
    # ═══════════════════════════════════════════════════════════════════════
    #                        TRADE HISTORY
    # ═══════════════════════════════════════════════════════════════════════
    
    def append_trade(self, trade_data: Dict):
        """Append a completed trade to the persistent trade history."""
        history_file = os.path.join(self.state_dir, "trade_history.json")
        
        trades = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    trades = json.load(f)
            except (json.JSONDecodeError, IOError):
                trades = []
        
        # Convert dataclass if needed
        if hasattr(trade_data, '__dataclass_fields__'):
            trade_data = asdict(trade_data)
        
        trade_data['recorded_at'] = datetime.now().isoformat()
        trades.append(trade_data)
        
        with open(history_file, 'w') as f:
            json.dump(trades, f, indent=2, default=str)
    
    def get_trade_history(self, limit: int = None) -> List[Dict]:
        """Get trade history, optionally limited to last N trades."""
        history_file = os.path.join(self.state_dir, "trade_history.json")
        
        if not os.path.exists(history_file):
            return []
        
        try:
            with open(history_file, 'r') as f:
                trades = json.load(f)
            
            if limit:
                return trades[-limit:]
            return trades
        except (json.JSONDecodeError, IOError):
            return []


# ═══════════════════════════════════════════════════════════════════════════════
#                              SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("=" * 60)
    print("  STATE MANAGER - SELF TEST")
    print("=" * 60)
    
    # Use temp dir for test
    with tempfile.TemporaryDirectory() as tmp:
        sm = StateManager(state_dir=tmp)
        
        # Test 1: Save and load positions
        test_positions = {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "direction": "BUY",
                "entry_price": 50000.0,
                "margin": 100.0,
                "leverage": 10
            }
        }
        
        sm.save_positions(test_positions, balance=9900.0)
        loaded = sm.load_positions()
        
        assert loaded is not None
        assert "BTCUSDT" in loaded["positions"]
        assert loaded["balance"] == 9900.0
        print("[OK] Test 1: Save/Load positions PASSED")
        
        # Test 2: Clear state
        sm.clear_state()
        assert not sm.has_saved_state()
        print("[OK] Test 2: Clear state PASSED")
        
        # Test 3: Trade history
        sm.append_trade({"symbol": "ETHUSDT", "pnl": 15.50})
        sm.append_trade({"symbol": "BTCUSDT", "pnl": -5.20})
        history = sm.get_trade_history()
        assert len(history) == 2
        print("[OK] Test 3: Trade history PASSED")
        
        # Test 4: Load with no state
        sm.clear_state()
        assert sm.load_positions() is None
        print("[OK] Test 4: Empty state PASSED")
        
        print("\nAll tests passed! [OK]")
