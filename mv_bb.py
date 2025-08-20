from enum import Enum
import datetime as dt

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange

from candle_helpers import aggregate_ohlcv
from events import OHLCVEvent, FillEvent
from indicators import BollingerBands
from utils import round_values


class MVBBState(Enum):
    NEUTRAL = 1
    LONG = 2
    SHORT = 3

    def __eq__(self, other):
        return self.value == other.value


class MeanReversionBB:

    def __init__(
            self,
            exchange: Exchange,
            info: Info,
            address: str,
            symbol: str,
            trade_size_usd: float = 1.0,
            ma_lookback_periods=20,
            bb_std_dev=2.5,
            stop_loss_multiplier=0.5,
            take_profit_multiplier=0.5,
            input_candle_periods: int = 1,
            input_candle_unit: str = "m",
            target_candle_periods: int = 1,
            target_candle_unit: str = "h",
            max_decimals: int = 2,
    ):
        self.hl_info = info
        self.hl_exchange = exchange
        self.address = address
        self.max_decimals = max_decimals

        self.symbol = symbol
        self.bollinger_bands = BollingerBands(ma_lookback_periods, bb_std_dev)
        self.current_candle = None
        self.latest_candle_watermark = dt.datetime(1970, 1, 1)

        self.trade_size_usd = trade_size_usd

        self.startup_complete = False
        self.open_orders = {}

        self.stop_loss_multiplier = stop_loss_multiplier
        self.take_profit_multiplier = take_profit_multiplier

        self.strategy_state = MVBBState.NEUTRAL

        self.input_candle_periods = input_candle_periods
        self.input_candle_unit = input_candle_unit
        self.target_candle_periods = target_candle_periods
        self.target_candle_unit = target_candle_unit

        self._start_up()

    def _get_state(self, timestamp):
        return {
            "timestamp": timestamp,
            "strategy_state": self.strategy_state,
            "bb_upper": self.bollinger_bands.upper_band,
            "bb_middle": self.bollinger_bands.middle_band,
            "bb_lower": self.bollinger_bands.lower_band,
        }

    def _start_up(self):
        startup_candles = self.hl_info.candles_snapshot(
            self.symbol,
            f"{self.input_candle_periods}{self.input_candle_unit}",
            int((dt.datetime.now() - dt.timedelta(hours=24)).timestamp() * 1000),
            int(dt.datetime.now().timestamp() * 1000)
        )
        print(len(startup_candles))
        for candle in startup_candles:
            event = OHLCVEvent.from_hyperliquid_message(candle)
            if event.start_time <= self.latest_candle_watermark:
                print("Skipping candle with start time before latest watermark.")
                continue
            self.latest_candle_watermark = event.start_time
            is_complete, self.current_candle = aggregate_ohlcv(event, self.current_candle, self.target_candle_periods,
                                                               self.target_candle_unit)

            if is_complete:
                self.bollinger_bands.update(self.current_candle.close)
        self.startup_complete = True
        print("Startup complete. Bollinger Bands initialized.")
        print(f"Current Bollinger Bands: {self.bollinger_bands.bands}")
        print(f"Latest message: {self.latest_candle_watermark}")

    def _cancel_all_open_orders(self):
        open_orders = self.hl_info.open_orders(self.address)
        for open_order in open_orders:
            print(f"cancelling order {open_order}")
            self.hl_exchange.cancel(open_order["coin"], open_order["oid"])

    def _get_current_asset_quantity(self):
        us = self.hl_info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05")
        for asset in us["positions"][0]:
            if asset["position"]["coin"] == self.symbol:
                return asset["position"]["szi"]
        return 0

    def process_message(self, message: dict):
        """
        Processes a new market event.
        """
        print(message)
        if message['channel'] == 'candle':
            event = OHLCVEvent.from_hyperliquid_message(message['data'])
            if event.start_time <= self.latest_candle_watermark:
                print("Skipping candle with start time before latest watermark.")
                return
            self.latest_candle_watermark = event.start_time
            is_complete, self.current_candle = aggregate_ohlcv(event, self.current_candle, self.target_candle_periods,
                                                               self.target_candle_unit)

            if is_complete:
                self.bollinger_bands.update(self.current_candle.close)

                if self.bollinger_bands.is_ready:
                    self.startup_complete = True

                if self.startup_complete:
                    # handle case where we have no open positions - set limit orders
                    if self.strategy_state == MVBBState.NEUTRAL:
                        self._cancel_all_open_orders()

                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=True,
                            sz=round_values(self.trade_size_usd / self.bollinger_bands.lower_band, self.max_decimals),
                            limit_px=round_values(self.bollinger_bands.lower_band, self.max_decimals),
                            order_type={"limit": {"tif": "Gtc"}},
                        )
                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=False,
                            sz=round_values(self.trade_size_usd / self.bollinger_bands.upper_band, self.max_decimals),
                            limit_px=round_values(self.bollinger_bands.upper_band, self.max_decimals),
                            order_type={"limit": {"tif": "Gtc"}},
                        )

                    # handle case where we are long - set limit orders / stop loss orders
                    elif self.strategy_state == MVBBState.LONG:
                        bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
                        self._cancel_all_open_orders()

                        # Place a stop order
                        stop_order_type = {
                            "trigger": {
                                "triggerPx": round_values(
                                    self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                                    self.max_decimals
                                ),
                                "isMarket": True,
                                "tpsl": "sl"
                            }
                        }
                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=False,
                            sz=self._get_current_asset_quantity(),
                            limit_px=round_values(
                                self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                                self.max_decimals
                            ),
                            order_type=stop_order_type,
                        )

                        # Place a tp order
                        tp_order_type = {
                            "trigger": {
                                "triggerPx": round_values(
                                    self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                                    self.max_decimals
                                ),
                                "isMarket": True,
                                "tpsl": "tp"
                            }
                        }
                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=False,
                            sz=self._get_current_asset_quantity(),
                            limit_px=round_values(
                                self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                                self.max_decimals
                            ),
                            order_type=tp_order_type,
                        )

                    # handle case where we are short - set limit / stop loss orders
                    elif self.strategy_state == MVBBState.SHORT:
                        bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)

                        self._cancel_all_open_orders()

                        # Place a stop order
                        stop_order_type = {
                            "trigger": {
                                "triggerPx": round_values(
                                    self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                                    self.max_decimals
                                ),
                                "isMarket": True,
                                "tpsl": "sl"
                            }
                        }
                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=True,
                            sz=self._get_current_asset_quantity(),
                            limit_px=round_values(
                                self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                                self.max_decimals),
                            order_type=stop_order_type,
                        )

                        # Place a tp order
                        tp_order_type = {
                            "trigger": {
                                "triggerPx": round_values(
                                    self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier)
                                ),
                                "isMarket": True,
                                "tpsl": "tp"
                            }
                        }
                        self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=True,
                            sz=self._get_current_asset_quantity(),
                            limit_px=round_values(
                                self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier),
                                self.max_decimals),
                            order_type=tp_order_type,
                        )
                    else:
                        raise ValueError(f"Unknown strategy state: {self.strategy_state}")
        elif message['channel'] == 'userFills':
            event = FillEvent.from_hyperliquid_message(message['data'])
            symbol = event.symbol

            # if strategy neutral
            if self.strategy_state == MVBBState.NEUTRAL:
                if event.order.quantity > 0:
                    self.strategy_state = MVBBState.LONG

                    bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
                    self._cancel_all_open_orders()

                    # Place a stop order
                    stop_order_type = {
                        "trigger": {
                            "triggerPx": round_values(
                                self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                                self.max_decimals
                            ),
                            "isMarket": True,
                            "tpsl": "sl"
                        }
                    }
                    self.hl_exchange.order(
                        name=self.symbol,
                        is_buy=False,
                        sz=self._get_current_asset_quantity(),
                        limit_px=round_values(
                            self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                            self.max_decimals
                        ),
                        order_type=stop_order_type,
                    )

                    # Place a tp order
                    tp_order_type = {
                        "trigger": {
                            "triggerPx": round_values(
                                self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                                self.max_decimals
                            ),
                            "isMarket": True,
                            "tpsl": "tp"
                        }
                    }
                    self.hl_exchange.order(
                        name=self.symbol,
                        is_buy=False,
                        sz=self._get_current_asset_quantity(),
                        limit_px=round_values(
                            self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                            self.max_decimals
                        ),
                        order_type=tp_order_type,
                    )

                elif event.order.quantity < 0:
                    self.strategy_state = MVBBState.SHORT

                    bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)

                    self._cancel_all_open_orders()

                    # Place a stop order
                    stop_order_type = {
                        "trigger": {
                            "triggerPx": round_values(
                                self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                                self.max_decimals
                            ),
                            "isMarket": True,
                            "tpsl": "sl"
                        }
                    }
                    self.hl_exchange.order(
                        name=self.symbol,
                        is_buy=True,
                        sz=self._get_current_asset_quantity(),
                        limit_px=round_values(
                            self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                            self.max_decimals),
                        order_type=stop_order_type,
                    )

                    # Place a tp order
                    tp_order_type = {
                        "trigger": {
                            "triggerPx": round_values(
                                self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier)
                            ),
                            "isMarket": True,
                            "tpsl": "tp"
                        }
                    }
                    self.hl_exchange.order(
                        name=self.symbol,
                        is_buy=True,
                        sz=self._get_current_asset_quantity(),
                        limit_px=round_values(
                            self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier),
                            self.max_decimals),
                        order_type=tp_order_type,
                    )
                else:
                    raise ValueError(f"Fill event with zero quantity: {event}")
            # if strategy long
            elif self.strategy_state == MVBBState.LONG:
                self.strategy_state = MVBBState.NEUTRAL
                self._cancel_all_open_orders()
            # if strategy short
            elif self.strategy_state == MVBBState.SHORT:
                self.strategy_state = MVBBState.NEUTRAL
                self._cancel_all_open_orders()
            else:
                raise ValueError(f"Unknown strategy state: {self.strategy_state}")
        else:
            raise ValueError(f"Message type {message['channel']} not supported.")
