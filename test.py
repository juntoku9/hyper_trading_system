import logging
from hyperliquid.info import Info  
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
import example_utils
from hyperliquid.utils import constants
import datetime as dt
import pprint

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

address, info, exchange = example_utils.setup(base_url=constants.MAINNET_API_URL, skip_ws=False)

pprint.pprint(info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05"))

order_result = exchange.order("HYPE", False, 1, 42.4, {"limit": {"tif": "Gtc"}})
print(order_result)

open_orders = info.open_orders(address)
pprint.pprint(open_orders)