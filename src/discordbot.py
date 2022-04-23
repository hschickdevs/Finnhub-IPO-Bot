import datetime
import time

from ._config import FINNHUB_APIKEY, DISCORD_BOT_TOKEN, DISCORD_BOT_CHANNEL_IDS, IPO_POLLING_PERIOD
from .finnhubhandler import FinnhubIPOHandler
from ._logger import log

import aiohttp
import discord
from discord.ext import commands
from discord.ext.tasks import loop


class IpoBot(commands.Bot):
    def __init__(self, command_prefix):
        super().__init__(command_prefix=command_prefix, help_command=None)

        self.today = datetime.datetime.now()
        self.tomorrow = self.today + datetime.timedelta(days=1)

        self.channels = []

        self.finnhub_handler = FinnhubIPOHandler(FINNHUB_APIKEY)

        @self.command()
        async def ipocal(ctx, _from, to):
            ipo_list = self.finnhub_handler.get_ipo_calendar(_from, to)
            await ctx.send(ctx.author.mention + "\n" + ipo_list)

        @self.command()
        async def sentiment(ctx, symbol):
            _sentiment = self.finnhub_handler.get_sentiment(symbol)
            await ctx.send(ctx.author.mention + "\n" + _sentiment)

        @self.command()
        async def quote(ctx, symbol):
            quote = self.finnhub_handler.get_quote(symbol.upper())
            await ctx.send(ctx.author.mention + "\n" + quote)

        @self.command()
        async def info(ctx):
            await ctx.send(f"Hello {ctx.author.mention}! Here are my commands:\n\n$quote symbol\n$sentiment "
                           f"symbol\n$ipocal yyyy-mm-dd yyyy-mm-dd")

        @self.command()
        async def forcestatus(ctx):
            await self.change_presence(status=discord.Status.online,
                                       activity=discord.Activity(type=discord.ActivityType.listening, name="$info"))

        # Moved to on_ready:
        # self.get_quotes.start()

    # # IPO ALERT: Needs to have embed
    # def ipo_alert_embed(channel):
    #     pass

    async def on_ready(self):
        await self.change_presence(status=discord.Status.idle, activity=discord.Game('Initializing Bot...'))
        print(f"Initializing Discord bot as {self.user}...\n")

        print(f"Registering channel IDs with bot...")

        self.channels = [self.get_channel(channel_id) for channel_id in DISCORD_BOT_CHANNEL_IDS]

        if all(channel is None for channel in self.channels):
            print(
                f"Could not register channel IDs... Fatal Error in Program, PROGRAM QUITTING.\nChannels Returned: {self.channels}")
            await self.close()
        else:
            await self.change_presence(status=discord.Status.online,
                                       activity=discord.Activity(type=discord.ActivityType.listening, name="$info"))
            self.get_quotes.start()

    @loop(seconds=IPO_POLLING_PERIOD)
    async def get_quotes(self):
        if datetime.datetime.now() >= self.tomorrow:
            self.today = self.tomorrow
            self.tomorrow = self.today + datetime.timedelta(days=1)
            print(f"\nDay change detected, registering IPO data for {self.today} to {self.tomorrow}...")
            await self.change_presence(status=discord.Status.idle, activity=discord.Game('Registering New IPOs...'))
            self.finnhub_handler.set_daily_ipo_data()
            await self.change_presence(status=discord.Status.online,
                                       activity=discord.Activity(type=discord.ActivityType.listening, name="$info"))

        quote_count = len(self.finnhub_handler.expected_ipos)
        print(f'\nFetching price quotes for {quote_count} expected IPO(s)...')
        start = time.time()

        # SPEED UP CHECKS WITH AIOHTTP:
        # https://discordpy.readthedocs.io/en/latest/faq.html#what-does-blocking-mean - USE AIOHTTP INSTEAD OF REQUESTS
        endpoint = "https://finnhub.io/api/v1/quote?symbol={}"
        headers = {"X-Finnhub-Token": FINNHUB_APIKEY}
        # print(f"\nChecking {len(symbols)} symbols for price:")
        for ipo in self.finnhub_handler.expected_ipos:
            symbol = ipo['symbol']
            date = ipo['date']
            expected_price = ipo['expected_price']
            company_name = ipo['company_name']
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint.format(symbol), headers=headers) as quote:
                    if quote.status == 200:
                        quote_data = await quote.json()
                        current_price = quote_data['c']

                        # --- For testing: --- #
                        # print(f"{symbol} current price: {current_price}")
                        # current_price = random.randint(0, 1000)

                        # Check if the stock has a valid price:
                        if current_price > 0:
                            print(f"{symbol} HAS OPENED FOR TRADING!")
                            self.finnhub_handler.opened_ipos.append(ipo)
                            self.finnhub_handler.expected_ipos.remove(ipo)
                            print(f"Expected IPOs: {self.finnhub_handler.expected_ipos}")
                            print(f"Opened IPOs: {self.finnhub_handler.opened_ipos}")
                            for channel in self.channels:
                                if channel is not None:
                                    await channel.send(
                                        f"IPO ALERT:\n{company_name} (${symbol}) OPEN FOR TRADING!\nCurrent Price: "
                                        f"${current_price} | Expected Open Price: ${expected_price}\n")
                                    if len(self.finnhub_handler.expected_ipos) == 0:
                                        await channel.send(
                                            f"\nALL SCHEDULED IPO ARE FINISHED FOR {self.today.strftime('%Y-%m-%d')} - "
                                            f"{self.tomorrow.strftime('%Y-%m-%d')}.")
                                else:
                                    print("\nBot failed to send to a channel... Check channel IDs in credentials.")
                    else:
                        print(f"Could not fetch quote for {symbol}. Finnhub Status Code: {quote.status}")

        print(f"{quote_count} IPO checks complete in {round(time.time() - start, 1)} seconds.")

    @get_quotes.before_loop
    async def before_start_loop(self):
        await self.wait_until_ready()

    def run_bot(self):
        try:
            self.run(DISCORD_BOT_TOKEN)
        except Exception as exc:
            # LOG.CRITICAL
            print(f"Could not initialize the discord bot. Error Code:\n{exc}")
