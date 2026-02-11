"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     CENTRALIZED CONFIG LOADER                               ║
║  Loads configuration from environment variables (.env) first,               ║
║  then falls back to config.json placeholders.                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
    from config.config_loader import get_config, get_api_keys

    config = get_config()
    keys = get_api_keys("binance")  # Returns {"api_key": "...", "api_secret": "..."}
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

logger = logging.getLogger("ConfigLoader")

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)

# Cache for loaded config
_config_cache: Optional[Dict] = None


def _load_json_config() -> Dict:
    """Load config.json and resolve ${ENV_VAR} placeholders."""
    config_path = Path(__file__).parent / "config.json"
    
    if not config_path.exists():
        logger.warning(f"config.json not found at {config_path}, using defaults")
        return {}
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return _resolve_env_vars(config)


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(obj, str):
        if obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            value = os.environ.get(env_var, "")
            if not value:
                logger.debug(f"Environment variable {env_var} not set")
            return value
        return obj
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def get_config() -> Dict:
    """
    Get the full configuration, resolved with environment variables.
    
    Priority:
    1. Environment variables (from .env or system)
    2. config.json values
    3. Defaults
    
    Returns:
        Dict with all configuration values
    """
    global _config_cache
    
    if _config_cache is None:
        _config_cache = _load_json_config()
    
    return _config_cache


def get_api_keys(broker: str) -> Dict[str, str]:
    """
    Get API keys for a specific broker.
    
    Environment variables take priority over config.json values.
    
    Args:
        broker: One of "binance", "zerodha", "oanda", "alphavantage"
    
    Returns:
        Dict with api_key, api_secret, and other broker-specific credentials
    """
    # Direct environment variable mapping
    env_mappings = {
        "binance": {
            "api_key": "BINANCE_API_KEY",
            "api_secret": "BINANCE_API_SECRET",
        },
        "zerodha": {
            "api_key": "ZERODHA_API_KEY",
            "api_secret": "ZERODHA_API_SECRET",
            "access_token": "ZERODHA_ACCESS_TOKEN",
        },
        "oanda": {
            "api_key": "OANDA_API_KEY",
            "account_id": "OANDA_ACCOUNT_ID",
            "environment": "OANDA_ENVIRONMENT",
        },
        "alphavantage": {
            "api_key": "ALPHAVANTAGE_API_KEY",
        },
    }
    
    broker = broker.lower()
    if broker not in env_mappings:
        logger.warning(f"Unknown broker: {broker}")
        return {}
    
    # Try environment variables first
    keys = {}
    for key_name, env_var in env_mappings[broker].items():
        value = os.environ.get(env_var, "")
        if value:
            keys[key_name] = value
    
    # Fall back to config.json if env vars not set
    if not keys or not keys.get("api_key"):
        config = get_config()
        broker_config = config.get(broker, {})
        for key_name in env_mappings[broker]:
            if key_name not in keys or not keys[key_name]:
                keys[key_name] = broker_config.get(key_name, "")
    
    # Validate - warn if no key found
    if not keys.get("api_key"):
        logger.warning(
            f"No API key found for {broker}. "
            f"Set {env_mappings[broker]['api_key']} in .env or environment."
        )
    
    return keys


def get_risk_limits() -> Dict:
    """Get risk management limits from config."""
    config = get_config()
    defaults = {
        "max_daily_loss_pct": -5.0,
        "max_drawdown_pct": -15.0,
        "max_consecutive_losses": 5,
        "max_position_per_strategy_pct": 20.0,
    }
    return {**defaults, **config.get("risk_limits", {})}


def get_capital() -> Dict:
    """Get capital settings from config, with env var overrides."""
    config = get_config()
    return {
        "crypto_usd": float(os.environ.get("CRYPTO_CAPITAL_USD", 
                            config.get("capital", {}).get("crypto_usd", 100.0))),
        "indian_inr": float(os.environ.get("INDIAN_CAPITAL_INR",
                            config.get("capital", {}).get("indian_inr", 10000.0))),
    }


def get_optimization_config() -> Dict:
    """Get optimization parameters from config."""
    config = get_config()
    defaults = {
        "in_sample_days": 90,
        "out_sample_days": 30,
        "reopt_frequency_days": 30,
        "min_sharpe_ratio": 0.5,
        "min_win_rate": 0.50,
    }
    return {**defaults, **config.get("optimization", {})}


def reload_config():
    """Force reload of configuration (useful after .env changes)."""
    global _config_cache
    _config_cache = None
    load_dotenv(_ENV_PATH, override=True)
    logger.info("Configuration reloaded")


# ═══════════════════════════════════════════════════════════════════════════════
#                        CONFIG VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

_VALIDATION_RULES = {
    "risk_limits": {
        "max_daily_loss_pct": {"type": (int, float), "range": (-100, 0), "default": -5.0},
        "max_drawdown_pct": {"type": (int, float), "range": (-100, 0), "default": -15.0},
        "max_consecutive_losses": {"type": int, "range": (1, 100), "default": 5},
        "max_position_per_strategy_pct": {"type": (int, float), "range": (1, 100), "default": 20.0},
    },
    "capital": {
        "crypto_usd": {"type": (int, float), "range": (0, 10_000_000), "default": 100.0},
        "indian_inr": {"type": (int, float), "range": (0, 100_000_000), "default": 10000.0},
    },
    "optimization": {
        "in_sample_days": {"type": int, "range": (7, 365), "default": 90},
        "out_sample_days": {"type": int, "range": (7, 365), "default": 30},
        "reopt_frequency_days": {"type": int, "range": (1, 365), "default": 30},
        "min_sharpe_ratio": {"type": (int, float), "range": (-5, 10), "default": 0.5},
        "min_win_rate": {"type": (int, float), "range": (0, 1), "default": 0.50},
    },
}


def validate_config(config: dict) -> list:
    """
    Validate config values against expected types and ranges.
    
    Returns:
        List of warning messages (empty if all valid)
    """
    warnings = []
    
    for section, rules in _VALIDATION_RULES.items():
        section_data = config.get(section, {})
        if not section_data:
            continue
        
        for key, rule in rules.items():
            value = section_data.get(key)
            if value is None:
                continue
            
            # Type check
            expected_type = rule["type"]
            if not isinstance(value, expected_type):
                warnings.append(
                    f"[{section}.{key}] Expected {expected_type}, got {type(value).__name__}: {value}"
                )
                continue
            
            # Range check
            lo, hi = rule["range"]
            if not (lo <= value <= hi):
                warnings.append(
                    f"[{section}.{key}] Value {value} out of range [{lo}, {hi}]"
                )
    
    for w in warnings:
        logger.warning(f"Config validation: {w}")
    
    return warnings


# ═══════════════════════════════════════════════════════════════════════════════
#                              SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("=" * 60)
    print("  CONFIG LOADER - SELF TEST")
    print("=" * 60)
    
    config = get_config()
    print(f"\nLoaded config sections: {list(config.keys())}")
    
    for broker in ["binance", "zerodha", "oanda"]:
        keys = get_api_keys(broker)
        masked = {k: v[:4] + "..." + v[-4:] if len(v) > 8 else "***" 
                  for k, v in keys.items() if v}
        print(f"\n{broker.upper()} keys: {masked if masked else 'NOT SET'}")
    
    print(f"\nRisk limits: {get_risk_limits()}")
    print(f"Capital: {get_capital()}")
    print(f"Optimization: {get_optimization_config()}")
