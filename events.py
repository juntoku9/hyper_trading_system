import datetime as dt
from dataclasses import dataclass

@dataclass
class OHLCVEvent:
    start_time: dt.datetime
    end_time: dt.datetime
    symbol: str
    period: int
    unit: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    num_trades: int

    @classmethod
    def from_hyperliquid_message(cls, message):
        return OHLCVEvent(
            start_time=dt.datetime.fromtimestamp(message["t"] / 1000.0),
            end_time=dt.datetime.fromtimestamp(message["T"] / 1000.0),
            symbol=message["s"],
            period=int(message["i"][:-1]),
            unit=message["i"][-1],
            open=float(message["o"]),
            high=float(message["h"]),
            low=float(message["l"]),
            close=float(message["c"]),
            volume=float(message["v"]),
            num_trades=int(message["n"]),
        )


@dataclass
class FillEvent:
    symbol: str
    price: float
    size: float
    side: str
    time: dt.datetime
    hash: str
    oid: int
    crossed: str
    fee: str
    tid: int
    liquidation: str
    feeToken: str
    builderFee: str

    @classmethod
    def from_hyperliquid_message(cls, message):
        return FillEvent(
            symbol=message["coin"],
            price=float(message["px"]),
            size=float(message["sz"]),
            side=message["side"],
            time=dt.datetime.fromtimestamp(message["time"] / 1000.0),
            hash=message["hash"],
            oid=message["oid"],
            crossed=message["crossed"],
            fee=message["fee"],
            tid=message["tid"],
            liquidation=message["liquidation"],
            feeToken=message["feeToken"],
            builderFee=message["builderFee"]
        )
