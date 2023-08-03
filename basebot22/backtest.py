from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Tuple

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
    
    def getWorthOfBaseline(self, baselineAmounts, crntRow):
        worth = 0
        for ticker, amount in baselineAmounts.items():
            if ticker == "USD":
                worth += amount
                continue
            worth += amount * crntRow[ticker]["Close"]
        return worth
    
    def oneRun(self) -> Tuple[List[float], List[float]]:
        portfolio = []
        baseline = []
        baselineAmounts = {}
        for stockname in self.data.keys():
            baselineAmounts[stockname] = self.startMoney / len(self.data.keys()) / self.data[stockname].iloc[0]["Close"]
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
            decisions: List[Order] = self.decisionFunction(crntRowSub, datasSub, self.portfolio, self.portfolioWorth)
            assert isinstance(decisions, list), "Decision function must return a list of orders or empty list"
            
            for order in decisions:
                assert isinstance(order, Order), "Decision function must return a list of orders or empty list"
                if order.buy:
                    if order.amountInUSD == -1:
                        # all we have
                        amount = self.portfolio["USD"]
                    else:
                        amount = order.amountInUSD
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
                        else:
                            amount = order.amountInUSD
                        # sell regular
                        fees = amount * self.commission
                        self.fees += fees
                        self.portfolio["USD"] += amount - fees
                        self.portfolio[order.stockname] = 0
                    elif self.portfolio.get(order.stockname,0) == 0 and order.amountInUSD < 0:
                        # short
                        if order.amountInUSD == -1:
                            # all we have
                            amount = self.portfolio["USD"]
                        else:
                            amount = order.amountInUSD
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
                baseline.append(self.getWorthOfBaseline(baselineAmounts, crntRow))
        return portfolio, baseline


if __name__ == "__main__":

    startPriceDiff = 15.05
    def decisionFunction(row, all_data, portfolio, portfolioWorth):
        crntDiff = row["RWL"]["Adj Close"] - row["FNDX"]["Adj Close"]
        orders = []
        if crntDiff > startPriceDiff * 1.2:
            print(f"the price difference is bigger {crntDiff} and the start price difference is {startPriceDiff}")
            for ticker, amount in portfolio.items():
                if ticker == "USD": 
                    continue
                if amount != 0:
                    # sell short, or sell long
                    orders.append(Order(buy=False, stockname=ticker, amount=-1))
            # then proceed to buy
            # they are going away from each other, short top one, long bottom one
            print("they are extending, short top one, long bottom one")
            orders.append(Order(buy=False, stockname="RWL", amount=-portfolioWorth/2))
            orders.append(Order(buy=True, stockname="FNDX", amount=portfolioWorth/2))
        elif crntDiff < startPriceDiff * 0.8:
            # they are going clother together
            print(f"the price difference is smaller {crntDiff} and the start price difference is {startPriceDiff}")
            for ticker, amount in portfolio.items():
                if ticker == "USD": 
                    continue
                if amount != 0:
                    # sell short, or sell long
                    orders.append(Order(buy=False, stockname=ticker, amount=-1))
            # then proceed to buy
            print("they are going closer, long top one, short bottom one")
            orders.append(Order(buy=True, stockname="RWL", amount=portfolioWorth/2))
            orders.append(Order(buy=False, stockname="FNDX", amount=-portfolioWorth/2))
        return orders

    bt = Backtest(["RWL", "FNDX"], decisionFunction)
    portfolio, baseline = bt.oneRun()
    print("win: ", portfolio[-1] - portfolio[0])
    print(f"just buy and hold would have given you: ", baseline[-1] - baseline[0])
