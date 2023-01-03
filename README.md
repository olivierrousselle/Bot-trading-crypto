# Bot Trading Crypto
This repository contains trading bots for spot and futures crypto markets; more precisely backtesting and live strategies for Binance exchange. The code is linked to Binance via API; the API Key and Secret Key must be provided by the user. The technical indicators used can be the stochastic RSI, the moving averages, the TRIX,... 
It must be launched for example each hour in a server (like AWS). 
The following packages must be installed: python-binance, pandas_ta, ta. 

Description of the different files:
- backtest_futures: backtest of a strategy with short and long orders based on Binance futures data (prices, volumes,...); 
- live_binance_futures: live trading strategy on futures for Binance exchange (long/short orders, take profit, stop loss); 
- live_binance_multicoin_spot: live trading stategy on spot for Binance exchange; the strategy allows to have several positions on different coins at the same time. 
