import time
import datetime
import asyncio
from typing import Union

from ._logger import log

from finnhub import Client as FinnhubClient


class FinnhubIPOHandler(FinnhubClient):
    def __init__(self, api_key):
        super().__init__(api_key=api_key)
        self.expected_ipos = []
        self.opened_ipos = []
        # self.set_daily_ipo_data()

    def get_headlines(self, symbol: str, from_date: str, to_date: str) -> list[dict]:
        """
        :param symbol: stock SYMBOL
        :param from_date: headline news from YYYY-MM-DD
        :param to_date: headline news to YYYY-MM-DD
        :return: A list of dictionaries containing the headline news data
        """
        log.info(f"Fetching headline news for {symbol} from {from_date} to {to_date}")
        return self.company_news(symbol, _from=from_date, to=to_date)

    def get_ipo_calendar(self, from_date: str = 'today', to_date: str = 'tomorrow') -> Union[list[dict], None]:
        """
        Fetches the IPO calendar for the given date range.

        :param from_date: IPOs from YYYY-MM-DD
        :param to_date: IPOs to YYYY-MM-DD
        :return: List of dictionaries containing the IPO calendar data if successful, otherwise None
        """

        log.info(f"Fetching IPO calendar from {from_date} to {to_date}")
        if from_date == "today":
            from_date = datetime.datetime.now().strftime("%Y-%m-%d")
        if to_date == "tomorrow":
            to_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        calendar = self.ipo_calendar(_from=from_date, to=to_date)
        if len(calendar['ipoCalendar']) > 0:
            return calendar['ipoCalendar']
            # ipo_list = "IPO Calendar:\n"
            # for ipo in calendar['ipoCalendar']:
            #     ipo_list += f"{ipo['date']}: (${ipo['symbol']}) {ipo['name'].lower().title()} expected at ${ipo['price']}\n"
            # return ipo_list
        else:
            return None

    def get_sentiment(self, symbol) -> str:
        """REQUIRES FINNHUB PREMIUM MEMBERSHIP"""
        u_symbol = symbol.upper()
        # News sentiment
        print("\nNEWS SENTIMENT:")
        sentiment_response = self.news_sentiment(u_symbol)
        print(sentiment_response)
        try:
            sentiment = sentiment_response['sentiment']
            buzz = sentiment_response['buzz']['articlesInLastWeek']
            bullish_percent = f"{round(float(sentiment['bullishPercent']) * 100, 1)}%"
            bearish_percent = f"{round(float(sentiment['bearishPercent']) * 100, 1)}%"
            return f"{u_symbol} News Sentiment:\nBulls: {bullish_percent} | Bears: {bearish_percent}\nAcross {buzz} Articles."
        except Exception as e:
            print(e)
            return f"Could not get sentiment for {u_symbol}"

    def get_quote(self, symbol) -> Union[dict, None]:
        """
        Fetches the quote data for the given stock symbol.

        :param symbol: Ticker SYMBOL
        :return: Dictionary containing the quote data if successful, otherwise None
        """
        log.info(f"Fetching quote for {symbol}")

        quote_response = self.quote(symbol)

        day_open = quote_response['o']
        day_high = quote_response['h']
        day_low = quote_response['l']
        current_price = quote_response['c']
        if current_price != 0:
            return {"symbol": symbol, "day_open": day_open, "day_high": day_high, "day_low": day_low,
                    "current_price": current_price}
            # return f"{symbol} Quote:\nDay Open: ${day_open} | Day High: ${day_high} | Day Low: ${day_low} | Current Price: ${current_price}"
        else:
            # return f"Ticker symbol '{symbol}' has not yet opened for trading."
            return None

    def get_earnings_calendar(self, symbol: str = None, from_date: str = 'today', to_date: str = 'tomorrow') -> None:
        """
        Fetches the earnings calendar for the given date range.
        API Reference: https://finnhub.io/docs/api/earnings-calendar

        :param symbol: Filter by ticker SYMBOL (e.g. AAPL), leave as default (None) to get all earnings announcements
        :param from_date: Earning Calendar from YYYY-MM-DD
        :param to_date: Earning Calendar to YYYY-MM-DD
        :return: List of dictionaries containing the earnings calendar data if successful, otherwise None
        """

        log.info(f"Fetching earnings calendar from {from_date} to {to_date}")
        if from_date == "today":
            from_date = datetime.datetime.now().strftime("%Y-%m-%d")
        if to_date == "tomorrow":
            to_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        calendar = self.earnings_calendar(_from=from_date, to=to_date, symbol=symbol, international=False)
        if len(calendar['earningsCalendar']) > 0:
            return calendar['earningsCalendar']
        else:
            return None

    def set_daily_ipo_data(self) -> None:
        """Sets the handler's IPO data for the day"""
        self.expected_ipos.clear()
        self.opened_ipos.clear()

        today = datetime.datetime.now()
        tomorrow = today + datetime.timedelta(days=1)
        today_formatted = today.strftime("%Y-%m-%d")
        tomorrow_formatted = tomorrow.strftime("%Y-%m-%d")

        log.info(f'Registering IPOs from {today_formatted} to {tomorrow_formatted}...')

        cal_response = self.ipo_calendar(_from=today_formatted, to=tomorrow_formatted)
        for ipo in cal_response['ipoCalendar']:
            price_data = self.quote(ipo['symbol'])
            if price_data['c'] == 0:
                self.expected_ipos.append({'date': ipo['date'], 'symbol': ipo['symbol'], 'expected_price': ipo['price'],
                                           "company_name": ipo['name']})
            else:
                self.opened_ipos.append({'date': ipo['date'], 'symbol': ipo['symbol'], 'expected_price': ipo['price'],
                                         "company_name": ipo['name']})

        log.info(f'Successfully registered IPOs: {len(self.expected_ipos)} expected | {len(self.opened_ipos)} opened.')
