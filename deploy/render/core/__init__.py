"""Core utilities — minimal init for Render deployment.
Only imports modules actually used by the live trading bot.
"""

# Don't import costs/validation/optimizer — not needed for paper trading
# and those subpackages are not deployed to Render.
