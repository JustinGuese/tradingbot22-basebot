from datetime import date, datetime, timedelta
from math import sqrt
from random import randint
from typing import List
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
from requests import get, post, put
from scipy.signal import argrelextrema


class BaseBot:

    def __init__(self, name: str, backendurl: str = "http://127.0.0.1:8000"):
        self.backendurl: str = backendurl
        self.headers: dict = { 'accept': 'application/json', 'Content-Type': 'application/json'}
        self.name: str = self.checkOrCreate(name)
    
    def checkOrCreate(self, name: str) -> str:
        response = get(self.backendurl + '/bot/' + quote_plus(name), headers=self.headers)
        if response.status_code != 200:
            # create
            json_data = {
                'name': name,
                'description': 'created in basebot',
            }
            response = put(self.backendurl + "/bot", json=json_data, headers=self.headers)
        return name

    def getPortfolio(self) -> dict:
        response = get(self.backendurl + '/bot/' + quote_plus(self.name), headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting portfolio: ", response.text)
        return response.json()["portfolio"]

    def getPortfolioWorth(self) -> float:
        response = get(self.backendurl + '/bot/%s/portfolioworth' % quote_plus(self.name), headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting portfolio worth: ", response.text)
        return float(response.text)
    
    def buy(self, ticker: str, amount: float = -1, amountInUSD: bool = False, short: bool = False):
        params = {
            "botname": self.name,
            'ticker': ticker,
            'amount': amount,
            "amountInUSD": amountInUSD,
            "short": short,
        }
        response = put(self.backendurl + '/buy/', params=params, headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error buying: ", response.text)

    def sell(self, ticker: str, amount: float = -1, amountInUSD: bool = False, short: bool = False):
        params = {
            "botname": self.name,
            'ticker': ticker,
            'amount': amount,
            "amountInUSD": amountInUSD,
            "short": short,
        }
        response = put(self.backendurl + '/sell/', params=params, headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error selling: ", ticker, response.text)

    def getData(self, ticker: str, start_date: date = (datetime.utcnow() - timedelta(7)).date(), 
        end_date: date = datetime.utcnow().date(), technical_indicators: list = []):
        json_data = {
            'ticker': ticker,
            'start_date': start_date.strftime("%Y-%m-%d"),
            'end_date': end_date.strftime("%Y-%m-%d"),
            'technical_analysis_columns': technical_indicators,
        }
        response = post(self.backendurl + '/data/', json=json_data, headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting data: ", response.text)
        df = pd.DataFrame(response.json())
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        # somehow index gets converted to string
        df.index = pd.to_datetime(df.index)
        # df = df[::-1]
        return df
    
    def getCurrentPrice(self, ticker: str):
        response = get(self.backendurl + '/data/current_price/' + quote_plus(ticker), headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting current price data for %s: " % ticker, response.text)
        return float(response.text)
    
    def getTrend(self, df: pd.DataFrame) -> pd.DataFrame:
        if "adj_close" not in df:
            raise ValueError("adj_close not in dataframe: " + str(df.columns))
        price = df["adj_close"]
        # moving average
        price = price.rolling(window=20).mean()
        price = price.fillna(method='bfill')
        # for local maxima
        maxima = argrelextrema(price.values, np.greater)

        # for local minima
        minima = argrelextrema(price.values, np.less)
        # convert that to a target variable
        signal = np.zeros(len(price))
        ## if maxima contains the smallest i lastSignal is 1, else if minima contains the smallest i lastSignal is -1
        min_min = min(minima[0])
        min_max = min(maxima[0])
        if min_min < min_max:
            lastSignal = -1
        elif min_min > min_max:
            lastSignal = 1
        else:
            raise ValueError("minima and maxima are equal")
        
        for i in range(len(price)):
            if i in maxima[0]:
                lastSignal = -1
            elif i in minima[0]:
                lastSignal = 1
            signal[i] = lastSignal
        df["signal"] = signal
        return df
        
    def __fixTimeStampEarnings(self, responses: list):
        if responses is None:
            return []
        # fixing the timestamp field
        if len(responses) == 0:
            return responses
        
        # else
        for i,d in enumerate(responses):
            responses[i]["timestamp"] = pd.to_datetime(responses[i]["timestamp"])
        return responses
        
    ## basic backtest functionality
    def getDecision(self, row: pd.Series, ticker: str = "") -> int:
        # raise NotImplementedError("getDecision not implemented")
        return randint(-1, 1)
    
    def getEarningsCalendar(self, only_now: bool = True):
        response = get(self.backendurl + '/data/earnings/calendar?now=%s' % str(only_now).lower() , headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting current earnings: ", response.text)
        response = response.json()
        return self.__fixTimeStampEarnings(response)
    
    def getEarningsFinancials(self, ticker: str, only_now: bool = True):
        response = get(self.backendurl + '/data/earnings/financials?ticker=%s&now=%s' % (ticker, str(only_now).lower()) , headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting current earnings financials: ", response.text)
        response = response.json()
        return self.__fixTimeStampEarnings(response)
    
    def getEarningsEffect(self, ticker: str):
        response = get(self.backendurl + '/data/earnings/effect?ticker=%s' % (ticker) , headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting current earnings effects: ", response.text)
        response = response.json()
        return self.__fixTimeStampEarnings(response)
    
    def updateEarnings(self, ticker: str):
        response = get(self.backendurl + '/update/earnings/?ticker=%s' % (ticker) , headers=self.headers)
        if response.status_code != 200:
            raise Exception("Error getting current earnings effects: ", response.text)
        response = response.json()
        return self.__fixTimeStampEarnings(response)

if __name__ == "__main__":
    bot = BaseBot("testbot")
    print(bot.getPortfolio())
    bot.buy("AAPL", 2000, amountInUSD=True)
    print("portfolio after buy")
    print(bot.getPortfolio())
    print("portfolio after sell")
    bot.sell("AAPL", 1500, amountInUSD=True)
    print(bot.getPortfolio())
    print("portfolio worth is: %.2f dollars" % bot.getPortfolioWorth())
    print("next earnings calendar events:")
    print(bot.getEarnings(only_now=True))
