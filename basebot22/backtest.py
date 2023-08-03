from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from pydantic import BaseModel
from ta import add_all_ta_features


class Interval(Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    SIXTY_MINUTE = "60m"
    NINETY_MINUTE = "90m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    FIVE_DAY = "5d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"
    THREE_MONTH = "3mo"

class Period(Enum):
    ONE_DAY = "1d"
    FIVE_DAY = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTH = "3mo"
    SIX_MONTH = "6mo"
    ONE_YEAR = "1y"
    TWO_YEARS = "2y"
    THREE_YEARS = "3y"
    FIVE_YEAR = "5y"
    TEN_YEAR = "10y"
    YTD = "ytd"
    MAX = "max"

class Order(BaseModel):
    buy: bool
    stockname: str
    amountInUSD: float = -1 # 1 means all

class Backtest:
    def __init__(self, stocknames: List[str], decisionFunction, startMoney: int = 10000, interval: Interval = Interval.ONE_DAY, period: Period = Period.THREE_YEARS):
        assert len(stocknames) > 0, "Stocknames must be a list of stock names"
        self.data = {}
        for stockname in stocknames:
            self.data[stockname] = yf.download(stockname, period=period.value, interval=interval.value, progress=False)
            assert len(self.data) > 0, "No data found, please check your stock name"
            self.data[stockname]["SMA5"] = self.data[stockname]["Close"].rolling(5).mean()
            self.data[stockname]["SMA10"] = self.data[stockname]["Close"].rolling(10).mean()
            self.data[stockname]["SMA20"] = self.data[stockname]["Close"].rolling(20).mean()
            self.data[stockname]["SMA50"] = self.data[stockname]["Close"].rolling(50).mean()
            self.data[stockname]["SMA100"] = self.data[stockname]["Close"].rolling(100).mean()
            self.data[stockname]["SMA200"] = self.data[stockname]["Close"].rolling(200).mean()
            self.data[stockname] = add_all_ta_features(self.data[stockname], open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=True)
        self.decisionFunction = decisionFunction
        self.startMoney = startMoney
        self.datas = {} # datas will be used to get the current data
        self.portfolio = {"USD" : startMoney}
        self.commission = 0.005 # 0.5% commission
        self.fees = 0.
        self.boughtAt = {}
        self.portfolioWorth = self.portfolio["USD"]

    def getValueOfPortfolio(self, crntRow):
        worth = 0
        for ticker, amount in self.portfolio.items():
            if ticker == "USD":
                worth += amount
                continue
            if amount > 0:
                worth += amount * crntRow[ticker]["Close"]
            elif amount < 0:
                worth += amount * (self.boughtAt[ticker] - crntRow[ticker]["Close"]) + amount * self.boughtAt[ticker]
        return worth
    
    def oneRun(self) -> List[float]:
        portfolio = []
        for date in self.data[list(self.data.keys())[0]].index:
            crntRow = {}
            for stockname in self.data.keys():
                self.datas[stockname] = self.data[stockname].loc[:date]
                crntRow[stockname] = self.data[stockname].loc[date]
            datasSub = self.datas
            crntRowSub = crntRow
            if len(crntRow) == 1:
                # simple mode
                crntRowSub = crntRow[list(crntRow.keys())[0]]
                datasSub = self.datas[list(self.datas.keys())[0]]
            decisions: List[Order] = self.decisionFunction(crntRowSub, datasSub, self.portfolio)
            assert isinstance(decisions, list), "Decision function must return a list of orders or empty list"
            
            for order in decisions:
                assert isinstance(order, Order), "Decision function must return a list of orders or empty list"
                if order.buy:
                    if order.amountInUSD == -1:
                        # all we have
                        amount = self.portfolio["USD"]
                    fees = amount * self.commission
                    self.fees += fees
                    howMany = (amount - fees) / crntRow[order.stockname]["Close"]
                    self.portfolio["USD"] -= amount
                    self.portfolio[order.stockname] = howMany
                    
                else:
                    # sell or short
                    if self.portfolio.get(order.stockname,0) > 0:
                        if order.amountInUSD == -1:
                            # all we have
                            amount = self.portfolio.get(order.stockname) * crntRow[order.stockname]["Close"]
                        # sell regular
                        fees = amount * self.commission
                        self.fees += fees
                        self.portfolio["USD"] += amount - fees
                        self.portfolio[order.stockname] = 0
                    elif self.portfolio.get(order.stockname,0) == 0 and order.amount < 0:
                        # short
                        if order.amountInUSD == -1:
                            # all we have
                            amount = self.portfolio["USD"]
                        self.boughtAt[order.stockname] = crntRow[order.stockname]["Close"]
                        fees = amount * self.commission
                        self.fees += fees
                        self.portfolio["USD"] -= amount
                        self.portfolio[order.stockname] = (amount / crntRow[order.stockname]["Close"]) * -1
                    elif self.portfolio.get(order.stockname,0) < 0:
                        # sell a short
                        assert order.amountInUSD == -1, "You can only sell all your short, no partial sell"
                        # all we have
                        amount = -self.portfolio.get(order.stockname)
                        win = (self.boughtAt[order.stockname] - crntRow[order.stockname]["Close"]) * amount + amount * self.boughtAt[order.stockname] * (1-self.commission)
                        self.portfolio["USD"] += win
                        self.portfolio[order.stockname] = 0
                    else:
                        raise ValueError("this combination should not be allowed!!!")
                self.portfolioWorth = self.getValueOfPortfolio(crntRow)
                portfolio.append(self.portfolioWorth)
        return portfolio


if __name__ == "__main__":
    def callback(row, all_data, portfolio):
        if row["SMA50"] > row["SMA200"] and portfolio.get("AAPL", 0) == 0:
            return [Order(buy = True, stockname="AAPL")] # if sma cross buy all
        elif row["SMA50"] < row["SMA200"] and portfolio.get("AAPL", 0) > 0:
            return [Order(buy = False, stockname="AAPL")] # sell all if sma cross down
        return []

    bt = Backtest(["AAPL"], callback)
    portfolio = bt.oneRun()
    print(portfolio[-1])
    plt.plot(portfolio)