[![Upload Python Package](https://github.com/JustinGuese/tradingbot22-basebot/actions/workflows/main.yaml/badge.svg)](https://github.com/JustinGuese/tradingbot22-basebot/actions/workflows/main.yaml)

Published on: https://pypi.org/project/basebot22-basebot-JustinGuese/

# tradingbot22-basebot

python package to interact with the [tradingbot22-backend](https://github.com/JustinGuese/tradingbot22-backend), used in [tradingbot22-tradingbots](https://github.com/JustinGuese/tradingbot22-tradingbots)

`pip install basebot22-basebot-JustinGuese`

or

`pip install -U git+https://github.com/JustinGuese/tradingbot22-basebot/`

Import with

`from basebot22.basebot import BaseBot`

## usage

```
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
```
