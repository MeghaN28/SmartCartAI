"""Single source of demand forecasting: ETS (Holt-Winters) only.

Used by Inventory Agent and Chat Agent so the same forecast is used whenever
demand is needed (monitoring, /query, chat-driven recommendations).
"""
import os
from pathlib import Path
from typing import List

# Optional .env load for ETS_* and FORECAST_*
try:
    from dotenv import load_dotenv
    for _path in [
        Path(__file__).parent.parent / "inventory-agent" / ".env",
        Path(__file__).parent.parent / "decision-orchestration-agent" / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]:
        if _path.exists():
            load_dotenv(_path)
            break
except ImportError:
    pass

FORECAST_PAST_DAYS = 7
ETS_ALPHA = float(os.getenv("ETS_ALPHA", "0.3"))
ETS_BETA = float(os.getenv("ETS_BETA", "0.1"))
ETS_GAMMA = float(os.getenv("ETS_GAMMA", "0.1"))
ETS_PERIOD = int(os.getenv("ETS_PERIOD", "7"))


def _exponential_smoothing(history: List[float], alpha: float = 0.3) -> float:
    if not history:
        return 0.0
    if len(history) == 1:
        return history[0]
    forecast = history[0]
    for value in history[1:]:
        forecast = alpha * value + (1 - alpha) * forecast
    return forecast


def _ets_forecast(
    history: List[float],
    alpha: float = 0.3,
    beta: float = 0.1,
    gamma: float = 0.1,
    period: int = 7,
) -> float:
    """ETS (Holt-Winters) demand forecast. Returns expected daily rate."""
    if not history:
        return 0.0
    if len(history) == 1:
        return history[0]
    if len(history) < 2 * period:
        if len(history) < 2:
            return _exponential_smoothing(history, alpha)
        level = history[0]
        trend = history[1] - history[0]
        for y in history[2:]:
            level_prev, level = level, alpha * y + (1 - alpha) * (level + trend)
            trend = beta * (level - level_prev) + (1 - beta) * trend
        return max(0.0, level + trend)
    m = period
    seasonal = [0.0] * m
    for i in range(m):
        seasonal[i] = sum(history[i + k * m] for k in range(len(history) // m) if i + k * m < len(history))
    n_cycles = len(history) // m
    seasonal = [s / n_cycles if n_cycles else 0.0 for s in seasonal]
    level = sum(history[:m]) / m - sum(seasonal) / m
    trend = (sum(history[m : 2 * m]) / m - sum(history[:m]) / m) / m if len(history) >= 2 * m else 0.0
    for i in range(m, len(history)):
        y = history[i]
        s_old = seasonal[i % m]
        level_new = alpha * (y - s_old) + (1 - alpha) * (level + trend)
        trend = beta * (level_new - level) + (1 - beta) * trend
        seasonal[i % m] = gamma * (y - level_new) + (1 - gamma) * s_old
        level = level_new
    next_seasonal = seasonal[len(history) % m]
    return max(0.0, level + trend + next_seasonal)


def forecast_demand(consumption_history: List[dict]) -> float:
    """Forecast demand using ETS (Holt-Winters) only.

    consumption_history: list of dicts with 'quantity_consumed' (last N days, newest first).
    Returns expected daily demand rate; next-week total = rate * 7.
    """
    if not consumption_history:
        return 0.0
    recent = consumption_history[:FORECAST_PAST_DAYS]
    consumptions = [float(row.get("quantity_consumed", 0)) for row in recent if row.get("quantity_consumed") is not None]
    if not consumptions:
        return 0.0
    consumptions.reverse()  # oldest first for ETS
    return _ets_forecast(
        consumptions,
        alpha=ETS_ALPHA,
        beta=ETS_BETA,
        gamma=ETS_GAMMA,
        period=ETS_PERIOD,
    )
