#!/usr/bin/env python3
import time
import requests
import re
from datetime import datetime
from web3 import Web3
import math

##########################################################
# 1) Web3 / Gnosis Setup
##########################################################
GNOSIS_RPC_URL = "https://rpc.gnosischain.com"
web3 = Web3(Web3.HTTPProvider(GNOSIS_RPC_URL))

if not web3.is_connected():
    raise Exception("Could not connect to Gnosis Chain.")

# Addresses on Gnosis for MPS and WXDAI
MPS_ADDRESS   = Web3.to_checksum_address("0xfa57aa7beed63d03aaf85ffd1753f5f6242588fb")  # MPS (0 decimals)
WXDAI_ADDRESS = Web3.to_checksum_address("0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d")  # WXDAI (18 decimals)

# SushiSwap Router on Gnosis
SUSHISWAP_ROUTER_ADDRESS = Web3.to_checksum_address("0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506")

# Minimal router ABI for getAmountsOut
ROUTER_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path",     "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "type": "function",
    },
]

# Instantiate the router
router = web3.eth.contract(
    address=SUSHISWAP_ROUTER_ADDRESS,
    abi=ROUTER_ABI
)

##########################################################
# 2) Telegram Config
##########################################################
BOT_TOKEN = "<bot token>"
CHAT_ID = "<your telegram ID>"

BASE_TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SEND_MESSAGE_URL = f"{BASE_TELEGRAM_URL}/sendMessage"
GET_UPDATES_URL = f"{BASE_TELEGRAM_URL}/getUpdates"

##########################################################
# 3) Helper Functions
##########################################################
def get_timestamp():
    """Return a formatted current timestamp."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram_text(text):
    """
    Send a generic text message to Telegram.
    Logs success/failure to console.
    """
    try:
        response = requests.get(
            SEND_MESSAGE_URL,
            params={
                'chat_id': CHAT_ID,
                'text': text
            }
        )
        response.raise_for_status()
        print(f"{get_timestamp()} - Telegram message sent: {text}")
    except requests.exceptions.RequestException as e:
        print(f"{get_timestamp()} - Error sending message: {e}")

def send_telegram_alert(price):
    """
    Send a specific 'ALERT' message to Telegram when price is out of limits.
    """
    message = f"ALERT! MPS token out of limits: {price}"
    send_telegram_text(message)

def get_token_price():
    """
    On-chain fetch of MPS price in xDAI (via WXDAI) using SushiSwap on Gnosis.
    Returns a float, or None if there's an error.
    
    Since MPS has 0 decimals, "1" on-chain is 1 MPS.
    WXDAI has 18 decimals, so we convert the output to float xDAI.
    """
    try:
        # 1 MPS in raw units
        amount_in_mps = 1

        # Path: [MPS -> WXDAI]
        path = [MPS_ADDRESS, WXDAI_ADDRESS]

        # Ask the router how many WXDAI for 1 MPS
        amounts_out = router.functions.getAmountsOut(amount_in_mps, path).call()
        wxdai_raw = amounts_out[-1]  # amounts_out is a list; last element is the WXDAI amount

        # Convert from 1e18 to a float
        mps_price_in_xdai = wxdai_raw / (10**18)
        return mps_price_in_xdai

    except Exception as e:
        print(f"{get_timestamp()} - Error fetching on-chain MPS price: {e}")
        return None

def get_telegram_updates(offset=None):
    """
    Poll Telegram for new updates. If `offset` is provided,
    Telegram will return only messages with update_id >= offset.
    Returns the list of updates (each is a dict).
    """
    params = {}
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(GET_UPDATES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if "result" in data:
            return data["result"]
    except requests.exceptions.RequestException as e:
        print(f"{get_timestamp()} - Error fetching updates: {e}")

    return []

##########################################################
# 4) Main Script Logic
##########################################################
if __name__ == "__main__":
    lower_limit = None
    upper_limit = None

    # To avoid spamming repeated alerts once out of range
    alert_sent = False

    # Track last_update_id to avoid duplicating
    last_update_id = None

    # Send initial message so user knows the bot is running
    start_message = (
        "Monitor started. Please send me a command in the format:\n"
        "monitor-mps <lower_limit> <upper_limit>\n"
        "to set or update the limits.\n\n"
        "Example: monitor-mps 0.5 2.0"
    )
    send_telegram_text(start_message)
    print(f"{get_timestamp()} - Script started. Waiting for limits...")

    while True:
        # 1. Check Telegram for new commands
        updates = get_telegram_updates(offset=last_update_id)
        if updates:
            print(f"{get_timestamp()} - Received {len(updates)} Telegram update(s).")
            for upd in updates:
                # We only process messages with update_id
                if 'update_id' in upd:
                    current_update_id = upd['update_id']

                    if 'message' in upd and 'text' in upd['message']:
                        text = upd['message']['text'].strip()

                        # Use a simple regex: "monitor-mps <lower> <upper>"
                        match = re.match(r"^monitor-mps\s+([\d\.]+)\s+([\d\.]+)$", text)
                        if match:
                            new_lower = float(match.group(1))
                            new_upper = float(match.group(2))
                            lower_limit = new_lower
                            upper_limit = new_upper
                            alert_sent = False  # reset alert

                            msg = (f"Limits updated:\n"
                                   f"Lower limit = {lower_limit}\n"
                                   f"Upper limit = {upper_limit}")
                            send_telegram_text(msg)
                            print(f"{get_timestamp()} - {msg}")

                    # Advance the offset so we don't re-process
                    last_update_id = current_update_id + 1
        else:
            # No new messages
            time.sleep(1)  # short delay

        # 2. If we have valid limits, check price
        if (lower_limit is not None) and (upper_limit is not None):
            price = get_token_price()
            if price is not None:
                # Overwrite the console line with current price
                print(f"\r{get_timestamp()} - Current Token Price: {price}   ", end="")

                # If out of bounds
                if price < lower_limit or price > upper_limit:
                    if not alert_sent:
                        send_telegram_alert(price)
                        alert_sent = True
                        print(f"\n{get_timestamp()} - Price out of limits. Alert sent.")
                else:
                    # Price is within range
                    if alert_sent:
                        print(f"\n{get_timestamp()} - Price back in limits. Resetting alert.")
                    alert_sent = False
            else:
                print(f"\n{get_timestamp()} - Unable to retrieve price.")

        # 3. Sleep
        time.sleep(10)
