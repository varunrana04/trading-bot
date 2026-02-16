#!/usr/bin/env python3
"""
================================================================================
                    BOT API - REST ENDPOINTS FOR BOT STATE
================================================================================
Lightweight FastAPI routes that expose the trading bot's internal state.
Mounted alongside the Gradio dashboard on the same port.
================================================================================
"""

from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
from typing import Optional, List
from collections import deque
import logging
import time
import traceback
import os

logger = logging.getLogger("BotAPI")

# API key for authentication (set via env var on Render)
BOT_API_KEY = os.environ.get("BOT_API_KEY", "")

router = APIRouter(prefix="/api")

# Reference to the dashboard instance — set by app.py at startup
_dashboard = None

# Equity curve — balance snapshots over time (max 500 points)
_equity_curve: deque = deque(maxlen=500)
_last_equity_ts: float = 0


def set_dashboard(dashboard_instance):
    """Set the dashboard reference so API can access bot state."""
    global _dashboard
    _dashboard = dashboard_instance


def _record_equity():
    """Record a balance snapshot if enough time has passed (60s min)."""
    global _last_equity_ts
    if not _dashboard or not _dashboard.paper_trader:
        return
    now = time.time()
    if now - _last_equity_ts < 60:
        return
    _last_equity_ts = now
    _equity_curve.append({
        "timestamp": datetime.utcnow().isoformat(),
        "balance": round(_dashboard.paper_trader.balance, 2),
        "open_positions": len(_dashboard.paper_trader.positions),
    })


def _safe_attr(obj, attr, default=None):
    """Safely get attribute, returning default if obj is None."""
    if obj is None:
        return default
    return getattr(obj, attr, default)


@router.get("/health")
async def health_check():
    """Lightweight health check — no data processing."""
    return {"ok": True, "timestamp": datetime.utcnow().isoformat()}


@router.get("/status")
async def get_status():
    """Bot running state, uptime, and basic info."""
    if not _dashboard:
        return {"status": "offline", "message": "Dashboard not initialized"}

    _record_equity()

    pt = _dashboard.paper_trader
    return {
        "status": "running" if _dashboard.running else "stopped",
        "symbols": _dashboard.symbols,
        "balance": round(pt.balance, 2) if pt else 0,
        "starting_balance": _dashboard.balance,
        "last_update": _dashboard.last_update.isoformat() if _dashboard.last_update else None,
        "open_positions_count": len(pt.positions) if pt else 0,
        "total_trades": len(pt.trades) if pt else 0,
        "uptime_seconds": round(time.time() - _dashboard._start_time, 0) if hasattr(_dashboard, '_start_time') else None,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/positions")
async def get_positions():
    """All open positions with unrealized P&L."""
    if not _dashboard or not _dashboard.paper_trader:
        return {"positions": [], "count": 0}

    _record_equity()
    positions = []

    # Use list() snapshot for thread safety — prevents RuntimeError if
    # the trading loop modifies positions while we iterate
    for symbol, pos in list(_dashboard.paper_trader.positions.items()):
        try:
            # Guard against corrupted entry_price
            if not pos.entry_price or pos.entry_price == 0:
                continue

            # Get current price from data feed
            current_price = pos.entry_price
            if _dashboard.data_feed:
                latest = _dashboard.data_feed.get_latest(symbol, "15m")
                if latest:
                    current_price = latest['close']

            # Calculate unrealized P&L
            if pos.direction == "BUY":
                pnl_pct = (current_price - pos.entry_price) / pos.entry_price * 100
            else:
                pnl_pct = (pos.entry_price - current_price) / pos.entry_price * 100

            pnl_usd = pos.margin * pos.leverage * (pnl_pct / 100)

            # TP/SL progress (how close to target) — guard against div-by-zero
            tp_progress = 0
            sl_progress = 0
            try:
                if pos.direction == "BUY":
                    if pos.tp_price != pos.entry_price:
                        tp_progress = (current_price - pos.entry_price) / (pos.tp_price - pos.entry_price) * 100
                    if pos.sl_price != pos.entry_price:
                        sl_progress = (pos.entry_price - current_price) / (pos.entry_price - pos.sl_price) * 100
                else:
                    if pos.tp_price != pos.entry_price:
                        tp_progress = (pos.entry_price - current_price) / (pos.entry_price - pos.tp_price) * 100
                    if pos.sl_price != pos.entry_price:
                        sl_progress = (current_price - pos.entry_price) / (pos.sl_price - pos.entry_price) * 100
            except (ZeroDivisionError, TypeError):
                pass

            positions.append({
                "symbol": symbol,
                "direction": pos.direction,
                "entry_price": round(pos.entry_price, 6),
                "current_price": round(current_price, 6),
                "entry_time": pos.entry_time,
                "leverage": pos.leverage,
                "margin": round(pos.margin, 2),
                "tp_price": round(pos.tp_price, 6),
                "sl_price": round(pos.sl_price, 6),
                "pnl_pct": round(pnl_pct, 3),
                "pnl_usd": round(pnl_usd, 2),
                "hold_candles": getattr(pos, 'hold_candles', 0),
                "max_pnl_pct": round(getattr(pos, 'max_pnl_pct', 0), 3),
                "tp_progress": round(max(0, min(tp_progress, 100)), 1),
                "sl_progress": round(max(0, min(sl_progress, 100)), 1),
            })
        except Exception as e:
            logger.warning(f"Failed to serialize position {symbol}: {e}")
            positions.append({"symbol": symbol, "error": str(e)})

    return {"positions": positions, "count": len(positions)}


@router.get("/trades")
async def get_trades(symbol: Optional[str] = None, limit: int = 50):
    limit = min(max(limit, 1), 500)  # Clamp to prevent abuse
    """Recent trade history."""
    if not _dashboard or not _dashboard.paper_trader:
        return {"trades": [], "count": 0}

    trades = _dashboard.paper_trader.trades
    if symbol:
        trades = [t for t in trades if t.symbol == symbol]

    # Take last N trades
    trades = trades[-limit:]

    result = []
    for t in reversed(trades):  # Most recent first
        result.append({
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_price": round(t.entry_price, 6),
            "exit_price": round(t.exit_price, 6),
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "leverage": t.leverage,
            "margin": round(t.margin, 2),
            "pnl": round(t.pnl, 2),
            "pnl_pct": round(t.pnl_pct, 3),
            "exit_reason": t.exit_reason,
            "conviction": round(t.conviction, 3) if t.conviction else 0
        })

    return {"trades": result, "count": len(result)}


@router.get("/signals")
async def get_signals():
    """Latest signals per symbol."""
    if not _dashboard or not _dashboard.signal_engine:
        return {"signals": {}}

    signals = {}
    for symbol in _dashboard.symbols:
        last = _dashboard.signal_engine.get_last_signal(symbol)
        if last:
            signals[symbol] = {
                "signal": last.get("signal", "HOLD"),
                "direction": last.get("direction", "NEUTRAL"),
                "confidence": last.get("confidence", 0),
                "score": last.get("score", 0),
                "price": last.get("price", 0),
                "reason": last.get("reason", ""),
                "timestamp": last.get("timestamp", "")
            }
        else:
            signals[symbol] = {
                "signal": "WAIT",
                "direction": "NEUTRAL",
                "confidence": 0,
                "score": 0,
                "price": 0,
                "reason": "No data yet"
            }

    return {"signals": signals}


@router.get("/stats")
async def get_stats():
    """Performance statistics."""
    if not _dashboard or not _dashboard.paper_trader:
        return {"stats": {}}

    stats = _dashboard.paper_trader.get_stats()

    # Add circuit breaker status
    stats["circuit_breaker"] = {
        "active": _dashboard.paper_trader._circuit_open,
        "consecutive_losses": _dashboard.paper_trader._consecutive_losses,
        "daily_pnl": round(_dashboard.paper_trader._daily_pnl, 2)
    }

    return {"stats": stats}


@router.get("/equity")
async def get_equity():
    """Equity curve — balance over time."""
    _record_equity()
    return {"curve": list(_equity_curve), "points": len(_equity_curve)}


@router.get("/export")
async def export_all():
    """Full data export — trade history, stats, equity, positions, logs.
    Use this to pull all data from the running Render instance."""
    if not _dashboard:
        return {"error": "Dashboard not initialized"}

    try:
        _record_equity()
        pt = _dashboard.paper_trader

        # Serialize all trades
        all_trades = []
        if pt:
            for t in pt.trades:
                try:
                    all_trades.append({
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "entry_price": round(t.entry_price, 6),
                        "exit_price": round(t.exit_price, 6),
                        "entry_time": t.entry_time,
                        "exit_time": t.exit_time,
                        "leverage": t.leverage,
                        "margin": round(t.margin, 2),
                        "pnl": round(t.pnl, 2),
                        "pnl_pct": round(t.pnl_pct, 3),
                        "exit_reason": t.exit_reason,
                        "conviction": round(getattr(t, 'conviction', 0) or 0, 3)
                    })
                except Exception as e:
                    all_trades.append({"error": str(e)})

        # Serialize open positions
        open_positions = []
        if pt:
            for sym, pos in list(pt.positions.items()):
                try:
                    open_positions.append({
                        "symbol": sym,
                        "direction": pos.direction,
                        "entry_price": round(pos.entry_price, 6),
                        "entry_time": pos.entry_time,
                        "leverage": pos.leverage,
                        "margin": round(pos.margin, 2),
                        "tp_price": round(pos.tp_price, 6),
                        "sl_price": round(pos.sl_price, 6),
                        "hold_candles": getattr(pos, 'hold_candles', 0),
                        "max_pnl_pct": round(getattr(pos, 'max_pnl_pct', 0), 3),
                    })
                except Exception as e:
                    open_positions.append({"symbol": sym, "error": str(e)})

        return {
            "exported_at": datetime.utcnow().isoformat(),
            "status": "running" if _dashboard.running else "stopped",
            "uptime_seconds": round(time.time() - _dashboard._start_time, 0) if hasattr(_dashboard, '_start_time') else None,
            "balance": round(pt.balance, 2) if pt else 0,
            "starting_balance": _dashboard.balance,
            "stats": pt.get_stats() if pt else {},
            "circuit_breaker": {
                "active": pt._circuit_open if pt else False,
                "consecutive_losses": pt._consecutive_losses if pt else 0,
                "daily_pnl": round(pt._daily_pnl, 2) if pt else 0,
            },
            "trades": all_trades,
            "total_trades": len(all_trades),
            "open_positions": open_positions,
            "equity_curve": list(_equity_curve),
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/logs")
async def get_logs(limit: int = 100):
    """Recent activity logs."""
    limit = min(max(limit, 1), 500)
    if not _dashboard:
        return {"logs": [], "count": 0}

    logs = getattr(_dashboard, 'logs', [])[-limit:]
    return {"logs": logs, "count": len(logs)}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header on /api/* routes (except /api/health)."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Skip auth for health check, root, and non-API paths (like Gradio)
        if not path.startswith("/api") or path == "/api/health":
            return await call_next(request)
        # If no key is configured, allow all (local dev)
        if not BOT_API_KEY:
            return await call_next(request)
        # Check header
        key = request.headers.get("X-API-Key", "")
        if key != BOT_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return await call_next(request)


# Allowed origins — FinSight AI frontend + local dev
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    os.environ.get("FINSIGHT_ORIGIN", "http://localhost:3000"),
]


def create_api_app() -> FastAPI:
    """Create the FastAPI app with CORS, auth, and bot routes."""
    api_app = FastAPI(
        title="Trading Bot API",
        version="1.2.0",
        description="REST API for the Paper Trading Bot"
    )

    # CORS — restricted to known frontends
    api_app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    # API key auth
    api_app.add_middleware(APIKeyMiddleware)

    api_app.include_router(router)

    @api_app.get("/")
    async def root():
        return {
            "name": "Trading Bot API",
            "version": "1.2.0",
            "auth": "required" if BOT_API_KEY else "disabled",
            "endpoints": ["/api/health", "/api/status", "/api/positions", "/api/trades", "/api/signals", "/api/stats", "/api/equity"]
        }

    return api_app
