from datetime import date, datetime, time, timedelta
from math import sqrt
from random import randint
from typing import List
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
from requests import Session
from scipy.signal import argrelextrema, savgol_filter


class BaseBot:
    def __init__(
        self, name: str, backendurl: str = "http://127.0.0.1:8000", live: bool = False
    ):
        user, password = None, None
        if "@" in backendurl:
            user, password = backendurl.split("@")[0].split("//")[1].split(":")
            backendurl = "https://" + backendurl.split("@")[1]
        self.backendurl: str = backendurl
        self.session = Session()
        if user is not None and password is not None:
            self.session.auth = (user, password)

        self.headers: dict = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        self.live: bool = live
        self.name: str = self.checkOrCreate(name, live)

    def checkOrCreate(self, name: str, live: bool = False) -> str:
        response = self.session.get(
            self.backendurl + "/bots/" + quote_plus(name), headers=self.headers
        )
        if response.status_code != 200:
            # create
            json_data = {
                "name": name,
                "description": "created in basebot",
                "portfolio": {"USD": 10000},
                "live": live,
            }
            response = self.session.put(
                self.backendurl + "/bots", json=json_data, headers=self.headers
            )
        return name

    def getPortfolio(self) -> dict:
        response = self.session.get(
            self.backendurl + "/portfolio/" + quote_plus(self.name),
            headers=self.headers,
        )
        if response.status_code != 200:
            raise Exception("Error getting portfolio: ", response.text)
        portfolio = response.json()
        # only keep portfolio values that are not 0
        portfolio = {k: v for k, v in portfolio.items() if v != 0}
        if "USD" not in portfolio:
            portfolio["USD"] = 0
        return portfolio

    def getPortfolioWorth(self) -> float:
        response = self.session.get(
            self.backendurl + "/portfolio/worth/%s" % quote_plus(self.name),
            headers=self.headers,
        )
        if response.status_code != 200:
            raise Exception("Error getting portfolio worth: ", response.text)
        return float(response.text)

    def buy(
        self,
        ticker: str,
        amount: float = 0,
        amountInUSD: bool = True,
        short: bool = False,
    ):
        if short:
            raise NotImplementedError("Shorting not implemented")
        params = {}
        if not amountInUSD:
            params["amountInUSD"] = False
        response = self.session.post(
            self.backendurl
            + "/buysell/buy/%s/%s/%s"
            % (quote_plus(self.name), quote_plus(ticker), quote_plus(str(amount))),
            headers=self.headers,
            params=params,
        )
        if response.status_code != 200:
            raise Exception("Error buying: ", ticker, response.text)

    def sell(
        self,
        ticker: str,
        amount: float = 0,
        amountInUSD: bool = True,
        short: bool = False,
    ):
        if short:
            raise NotImplementedError("Shorting not implemented")
        params = {}
        if not amountInUSD:
            params["amountInUSD"] = False
        response = self.session.post(
            self.backendurl
            + "/buysell/sell/%s/%s/%s"
            % (quote_plus(self.name), quote_plus(ticker), quote_plus(str(amount))),
            headers=self.headers,
            params=params,
        )
        if response.status_code != 200:
            raise Exception("Error selling %s of %s " % (str(amount), ticker), response.text)

    def getCurrentPrice(self, ticker: str):
        response = self.session.get(
            self.backendurl + "/pricing/" + quote_plus(ticker),
            headers=self.headers,
        )
        if response.status_code != 200:
            raise Exception(
                "Error getting current price data for %s: " % ticker, response.text
            )
        return float(response.text)

    def getTrend(self, df: pd.DataFrame) -> pd.DataFrame:
        # see tradingbot22-tradingbots/jupyternotebooks/signalsmoothing.ipynb
        if "adj_close" not in df:
            raise ValueError("adj_close not in dataframe: " + str(df.columns))
        price = df["adj_close"]

        windowsize = int(len(df) / 5)  # 151 turned out to be quite good
        yhat = savgol_filter(price, windowsize, 3)  # window size 51, polynomial order 3
        ## get minima maxima,
        maxima = argrelextrema(yhat, np.greater)[0]
        minima = argrelextrema(yhat, np.less)[0]

        # calculate the signal, taking into account minimum distances to ignore changes that are tiny
        newMinima = []
        newMaxima = []
        signal = []
        # we need an initial guess at the breakpoints, so
        num_breakpoints = 0
        minimumDistance = len(df) / 15  # trial and error value
        crntDistance = 0
        # set last signal
        min_min = min(minima)
        min_max = min(maxima)
        if min_min < min_max:
            lastSignal = -1
        elif min_min > min_max:
            lastSignal = 1

        for i in range(len(df)):
            if (i in minima or i in maxima) and crntDistance > minimumDistance:
                if i in minima and lastSignal == -1:
                    newMinima.append(i)
                    lastSignal = 1  # because we have been at minima, moving to maxima
                    num_breakpoints += 1
                    crntDistance = 0
                elif i in maxima and lastSignal == 1:
                    newMaxima.append(i)
                    lastSignal = -1  # because we have been at maxima, moving to minima
                    num_breakpoints += 1
                    crntDistance = 0

            crntDistance += 1
            signal.append(lastSignal)

        assert num_breakpoints > 2, "Not enough breakpoints found: %d" % num_breakpoints

        df["signal"] = signal
        return df


if __name__ == "__main__":
    bot = BaseBot("testbot")
    print(bot.getPortfolio())
    bot.buy("AAPL", 2000)
    print("portfolio after buy")
    print(bot.getPortfolio())
    print("portfolio after sell")
    bot.sell("AAPL", 1500)
    print(bot.getPortfolio())
    print("portfolio worth is: %.2f dollars" % bot.getPortfolioWorth())
