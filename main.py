import logging
from hyperliquid.info import Info  
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
import example_utils
from hyperliquid.utils import constants
import datetime as dt
import pprint

from mv_bb import MeanReversionBB

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def callback(msg):  
    logger.debug("callback")
    logger.debug(f"Received: {msg}")  


address, info, exchange = example_utils.setup(base_url=constants.MAINNET_API_URL, skip_ws=False)
pprint.pprint(info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05"))

strategy = MeanReversionBB(exchange, info, address, "HYPE")

# Subscribe with the callback  
subscription1 = { "type": "candle", "coin": "HYPE", "interval": "1m" }
subscription2 = { "type": "userFills", "user": address }

result1 = info.subscribe(subscription1, strategy.process_message)
result2 = info.subscribe(subscription2, strategy.process_message)

logger.debug(f"Subscribe result: {result1}")
logger.debug(f"Subscribe result: {result2}")
logger.debug("subscribed")
logger.debug(f"Active subscriptions: {info.ws_manager.active_subscriptions}")
logger.debug(f"WS ready: {info.ws_manager.ws_ready}")
