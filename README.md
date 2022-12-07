# Bot Trading Crypto
These trading algorithms are bots for spot and futures crypto markets. It contains backtesting and live strategies for Binance exchange. The code is linked to Binance via API; the API Key and Secret Key must be provided by the user. The technical indicators used can be the stochastic RSI, the moving averages, the TRIX,... 
It must be launched for example each hour in a server (like AWS). 
The following packages must be installed: python-binance, pandas_ta, ta. 

Description of the different files:
- backtest_futures: backtest of a strategy using futures data (prices, volumes,...); 
- live_binance: live trading strategy on spot for Binance exchange;  
- live_binance_futures: live trading strategy on futures for Binance exchange. 
