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
        async def ipocal(ctx, _from: str, to: str):
            try:
                ipo_list = self.finnhub_handler.get_ipo_calendar(_from, to)
                if ipo_list is not None:
                    msg = "IPO Calendar:\n"
                    for ipo in ipo_list:
                        msg += f"{ipo['date']}: (${ipo['symbol']}) {ipo['name'].lower().title()} expected at ${ipo['price']}\n"
                    await ctx.send(ctx.author.mention + "\n" + msg)
                else:
                    await ctx.send(ctx.author.mention + "\n" + f"No IPOs found {_from} - {to}")
            except Exception as exc:
                msg = f'Error occurred when attempting to fetch the IPO calendar ({_from} - {to})'
                log('ERROR', msg + f' - Error: {exc}')
                await ctx.send(ctx.author.mention + "\n" + msg)

        @self.command()
        async def sentiment(ctx, symbol):
            _sentiment = self.finnhub_handler.get_sentiment(symbol)
            await ctx.send(ctx.author.mention + "\n" + _sentiment)

        @self.command()
        async def quote(ctx, symbol):
            symbol = symbol.upper()
            try:
                quote_r = self.finnhub_handler.get_quote(symbol)
                if quote_r is not None:
                    msg = f"{quote_r['symbol']} Quote:\nDay Open: ${quote_r['day_open']} | " \
                          f"Day High: ${quote_r['day_high']} | " \
                          f"Day Low: ${quote_r['day_low']} | " \
                          f"Current Price: ${quote_r['current_price']}"
                    await ctx.send(ctx.author.mention + "\n" + msg)
                else:
                    await ctx.send(ctx.author.mention + "\n" + f"Could not find a quote for {symbol}")
            except Exception as exc:
                msg = f"Error has occurred when attempting to fetch a quote for {symbol}"
                log("ERROR", msg + f" - Error: {exc}")
                await ctx.send(ctx.author.mention + "\n" + msg)

        @self.command()
        async def info(ctx):
            await ctx.send(f"Hello {ctx.author.mention}! Here are my commands:\n"
                           f"\n$quote SYMBOL"
                           f"\n$ipocal YYYY-MM-DD YYYY-MM-DD (or) today tomorrow"
                           f"\n$sentiment SYMBOL (Finnhub Premium)")

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
        log("INFO", f"Initializing Discord bot as {self.user}...")

        log("INFO", f"Registering channel IDs with bot")

        self.channels = [self.get_channel(int(channel_id)) for channel_id in DISCORD_BOT_CHANNEL_IDS]

        if all(channel is None for channel in self.channels):
            log("CRITICAL", f"Could not register channel IDs... Fatal Error in Program, PROGRAM QUITTING -"
                            f"Channels Returned: {self.channels}")
            await self.close()
        else:
            log("INFO", f"Channels Registered: {self.channels}")
            await self.change_presence(status=discord.Status.online,
                                       activity=discord.Activity(type=discord.ActivityType.listening, name="$info"))
            self.get_quotes.start()

    @loop(seconds=IPO_POLLING_PERIOD)
    async def get_quotes(self):
        if datetime.datetime.now() >= self.tomorrow:
            self.today = self.tomorrow
            self.tomorrow = self.today + datetime.timedelta(days=1)
            log("INFO", f"Day change detected, registering IPO data for {self.today} to {self.tomorrow}...")
            await self.change_presence(status=discord.Status.idle, activity=discord.Game('Registering New IPOs...'))
            self.finnhub_handler.set_daily_ipo_data()
            await self.change_presence(status=discord.Status.online,
                                       activity=discord.Activity(type=discord.ActivityType.listening, name="$info"))

        quote_count = len(self.finnhub_handler.expected_ipos)
        if quote_count == 0:
            return

        log("INFO", f'Fetching price quotes for {quote_count} expected IPO(s) today...')
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
                            log("INFO", f"{symbol} HAS OPENED FOR TRADING!")
                            self.finnhub_handler.opened_ipos.append(ipo)
                            self.finnhub_handler.expected_ipos.remove(ipo)
                            log("INFO", f"Expected IPOs: {self.finnhub_handler.expected_ipos}")
                            log("INFO", f"Opened IPOs: {self.finnhub_handler.opened_ipos}")
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
                                    log("ERROR", "Bot failed to send to a channel... Check channel IDs in credentials.")
                    else:
                        log("ERROR", f"Could not fetch quote for {symbol}. Finnhub Status Code: {quote.status}")

        log("INFO", f"{quote_count} IPO checks complete in {round(time.time() - start, 1)} seconds.")

    @get_quotes.before_loop
    async def before_start_loop(self):
        await self.wait_until_ready()

    def run_bot(self):
        try:
            self.run(DISCORD_BOT_TOKEN)
        except Exception as exc:
            # LOG.CRITICAL
            log("CRITICAL", f"Could not initialize the discord bot. Error Code: {exc}")
