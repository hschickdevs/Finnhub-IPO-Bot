import os

from dotenv import load_dotenv

load_dotenv()

# Your Finnhub API key
FINNHUB_APIKEY: str = os.getenv('FINNHUB_APIKEY', 'your_finnhub_apikey')
assert FINNHUB_APIKEY != 'your_finnhub_apikey'

# Your discord bot token (e.g. abcdefg.hijklmnop.qrstuvwxyz)
DISCORD_BOT_TOKEN: str = os.getenv('DISCORD_BOT_TOKEN', 'your_discord_bot_token')
assert DISCORD_BOT_TOKEN != 'your_discord_bot_token'

# Input the channel IDs that you want the bot to post IPO alerts in, no-space comma delimited:
DISCORD_BOT_CHANNEL_IDS: list = [int(_id.strip()) for _id in os.getenv('DISCORD_BOT_CHANNEL_IDS', '1234,1234').split(",")]
assert DISCORD_BOT_CHANNEL_IDS != [1234, 1234]

# The time period for checking IPO statuses (in seconds)
IPO_POLLING_PERIOD = 30