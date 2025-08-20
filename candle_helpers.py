from events import OHLCVEvent
import datetime as dt

def _get_timedelta(period: int, unit: str) -> dt.timedelta:
    if unit == "s":
        return dt.timedelta(seconds=period)
    if unit == "m":
        return dt.timedelta(minutes=period)
    elif unit == "h":
        return dt.timedelta(hours=period)
    elif unit == "d":
        return dt.timedelta(days=period)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")


def normalize_timestamp(timestamp: dt.datetime, period: int, unit: str) -> dt.datetime:
    if unit == "s":
        return timestamp.replace(microsecond=0) - dt.timedelta(seconds=timestamp.minute % period)
    elif unit == "m":
        return timestamp.replace(second=0, microsecond=0) - dt.timedelta(minutes=timestamp.minute % period)
    elif unit == "h":
        return timestamp.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=timestamp.hour % period)
    elif unit == "d":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")


def aggregate_ohlcv(
        new_candle: OHLCVEvent,
        current_aggregated_candle: OHLCVEvent or None,
        target_period: int,
        target_unit: str,
) -> tuple[bool, OHLCVEvent or None]:
    """
    Aggregates smaller OHLCV candles into larger ones.

    Args:
        new_candle: The incoming smaller OHLCV candle.
        current_aggregated_candle: The candle being built for the larger period.
        target_period: The desired period for the aggregated candle (e.g., 1).
        target_unit: The desired unit for the aggregated candle (e.g., "h" for hour).

    Returns:
        A tuple containing (is_complete_candle, updated_current_aggregated_candle).
    """

    normalized_new_candle_timestamp = normalize_timestamp(new_candle.start_time, target_period, target_unit)

    if current_aggregated_candle is not None and normalized_new_candle_timestamp > current_aggregated_candle.end_time:
        current_aggregated_candle = None

    if current_aggregated_candle is None:
        # Initialize the aggregated candle with the first incoming candle
        # Normalize its timestamp to the start of the target period
        current_aggregated_candle = OHLCVEvent(
            start_time=normalized_new_candle_timestamp,
            end_time=normalized_new_candle_timestamp + _get_timedelta(target_period, target_unit) - dt.timedelta(seconds=1),  # assume no more than second precision
            symbol=new_candle.symbol,
            period=target_period,
            unit=target_unit,
            open=new_candle.open,
            high=new_candle.high,
            low=new_candle.low,
            close=new_candle.close,
            volume=0,
            num_trades=0,
        )

    current_aggregated_candle.high = max(current_aggregated_candle.high, new_candle.high)
    current_aggregated_candle.low = min(current_aggregated_candle.low, new_candle.low)
    current_aggregated_candle.close = new_candle.close
    current_aggregated_candle.volume += new_candle.volume
    current_aggregated_candle.num_trades += new_candle.num_trades

    is_completed = new_candle.end_time >= current_aggregated_candle.end_time

    return (
        is_completed,
        current_aggregated_candle
    )
