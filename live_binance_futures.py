from binance.client import Client
import pandas as pd
import time
from datetime import datetime
import ta
import numpy as np
from binance.helpers import round_step_size
from decimal import Decimal
import sys

now = datetime.now()
print(now.strftime("%y-%d-%m %H:%M:%S"))

fiatSymbol = 'USDT'
coin = 'ETH'
pairSymbol = coin + fiatSymbol
timeInterval = '1h'

# -- Wallet -- 
initialWallet = 100
maxDrawdown = -0.15
proportionTrading = 1

# -- Hyper parameters --
leverage = 1
TpPct = 0.1
SlPct = 0.05

# -- Indicator variables --
trixLength = 9
trixSignal = 21
stochWindow = 14
stochOverBought = 0.8
stochOverSold = 0.2
emaWindow = 500

# API
binance_api_key = ''  # Enter your own API-key here
binance_api_secret = ''  # Enter your own API-secret here
client = Client(api_key=binance_api_key, api_secret=binance_api_secret)

klinesT = client.get_historical_klines(pairSymbol, timeInterval, "30 day ago UTC")
df = pd.DataFrame(klinesT, columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore' ])
df['close'] = pd.to_numeric(df['close'])
df['high'] = pd.to_numeric(df['high'])
df['low'] = pd.to_numeric(df['low'])
df['open'] = pd.to_numeric(df['open'])
df = df.set_index(df['timestamp'])
df.index = pd.to_datetime(df.index, unit='ms')
del df['timestamp']

df['TRIX'] = ta.trend.ema_indicator(ta.trend.ema_indicator(ta.trend.ema_indicator(close=df['close'], window=trixLength), window=trixLength), window=trixLength)
df['TRIX_PCT'] = df["TRIX"].pct_change()*100
df['TRIX_SIGNAL'] = ta.trend.sma_indicator(df['TRIX_PCT'],trixSignal)
df['TRIX_HISTO'] = df['TRIX_PCT'] - df['TRIX_SIGNAL']
df['STOCH_RSI'] = ta.momentum.stochrsi(close=df['close'], window=stochWindow)
df['EMA'] = ta.trend.ema_indicator(close=df['close'], window=emaWindow)


# -- Condition to open Market LONG --
def openLongCondition(row, previousRow):
    if row['close'] > row['EMA'] and row['TRIX_HISTO'] > 0 and row['STOCH_RSI'] < stochOverBought:
        return True
    else:
        return False

# -- Condition to close Market LONG --
def closeLongCondition(row, previousRow):
    if row['TRIX_HISTO'] < 0 and row['STOCH_RSI'] > stochOverSold:
        return True
    else:
        return False

# -- Condition to open Market SHORT --
def openShortCondition(row, previousRow):
    if row['close'] < row['EMA'] and row['TRIX_HISTO'] < 0 and row['STOCH_RSI'] > stochOverSold:
        return True
    else:
        return False

# -- Condition to close Market SHORT --
def closeShortCondition(row, previousRow):
    if row['TRIX_HISTO'] > 0 and row['STOCH_RSI'] < stochOverBought:
        return True
    else:
        return False

def get_price_step(symbol):
    stepSize = None
    for filter in client.get_symbol_info(symbol)['filters']:
        if filter['filterType'] == 'PRICE_FILTER':
            stepSize = float(filter['tickSize'])
    return stepSize

def get_step_size(symbol):
    stepSize = None
    for filter in client.get_symbol_info(symbol)['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            stepSize = float(filter['stepSize'])
    return stepSize

def get_step_size_futures(symbol):
    data = client.futures_exchange_info()
    info = data['symbols'] 
    for x in range(len(info)): 
        if info[x]['symbol'] == symbol:
            stepSize = info[x]["filters"][0]['tickSize'] 
            return float(stepSize)

def convert_amount_to_precision(symbol, amount):
    stepSize = get_step_size_futures(symbol)
    #return (amount//stepSize)*stepSize
    #return round_step_size(amount, stepSize)
    amount = Decimal(str(amount))
    return float(amount - amount % Decimal(str(stepSize)))

def convert_price_to_precision(symbol, price):
    stepSize = get_price_step(symbol)
    #return (price//stepSize)*stepSize
    #return round_step_size(price, stepSize)
    price = Decimal(str(price))
    return float(price - price % Decimal(str(stepSize)))

def get_balance(symbol):
    for liste in client.futures_account_balance():
        if liste['asset']==symbol:
            return float(liste['balance'])
    return 0
               
def get_position_balance(symbol):
    for liste in client.futures_account()['positions']:
        if liste['symbol']==symbol and float(liste['initialMargin'])>0:
            return float(liste['initialMargin']), float(liste['entryPrice'])
    return 0, 1

wallet = get_balance(fiatSymbol)
usdtBalance = wallet
coinInUsdt, entryPrice = get_position_balance(pairSymbol)
coinBalance = coinInUsdt / entryPrice
usdtBalance -= coinInUsdt
print("Wallet:", round(wallet, 1), "$")
stopTrades = (wallet-initialWallet)/initialWallet < maxDrawdown and df.index[-1].day > 15
if stopTrades:
    print("no trading")
longPosition = False
shortPosition = False
for liste in client.futures_account()['positions']:
    if liste['symbol']==pairSymbol:
        if float(liste['initialMargin'])>0.05*wallet and float(liste['notional']) > 0:
            longPosition = True
            print("Long Position")
        elif float(liste['initialMargin'])>0.05*wallet and float(liste['notional']) < 0:
            shortPosition = True
            print("Short Position")
openOrders = client.futures_get_open_orders(symbol=pairSymbol)
actualPrice = df['close'].iloc[-1]
price = convert_price_to_precision(pairSymbol, actualPrice)

if (not shortPosition and not longPosition and not stopTrades):
    if wallet > initialWallet:
        algoBenefit = ((wallet - initialWallet)/initialWallet)
        proportionTrading = (initialWallet*(1+algoBenefit*0.5))/wallet * 0.2
    else:
        proportionTrading = 1 * 0.2
    if openLongCondition(df.iloc[-1], df.iloc[-2]):
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(5)
        longQuantityInUsdt = usdtBalance * proportionTrading
        longAmount = convert_amount_to_precision(pairSymbol, longQuantityInUsdt*leverage/actualPrice)
        try:
            long = client.futures_create_order(symbol=pairSymbol, side='BUY', type='MARKET', quantity=longAmount, isolated=True, leverage=leverage)
            print("Long", longAmount, coin, 'at', actualPrice, long)
        except:
            print("Unexpected error:", sys.exc_info()[0])
        time.sleep(5)
        try:
            tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+TpPct))
            client.futures_create_order(symbol=pairSymbol, side='SELL', type='TAKE_PROFIT_MARKET', stopPrice=tpPrice, closePosition=True)
            time.sleep(5)
            slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-SlPct))
            client.futures_create_order(symbol=pairSymbol, side='SELL', type='STOP_MARKET', stopPrice=slPrice, closePosition=True)
        except:
            print("Unexpected error:", sys.exc_info()[0])
    elif openShortCondition(df.iloc[-1], df.iloc[-2]): 
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(5)
        shortQuantityInUsdt = usdtBalance * proportionTrading
        shortAmount = convert_amount_to_precision(pairSymbol, shortQuantityInUsdt*leverage/actualPrice)
        try:
            short = client.futures_create_order(symbol=pairSymbol, side='SELL', type='MARKET', quantity=shortAmount, isolated=True, leverage=leverage)
            print("Short", shortAmount, coin, 'at', actualPrice, short)
        except: 
            print("Unexpected error:", sys.exc_info()[0])  
        time.sleep(5)
        try:
            tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-TpPct))
            client.futures_create_order(symbol=pairSymbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tpPrice, closePosition=True)
            time.sleep(5)
            slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+SlPct))
            client.futures_create_order(symbol=pairSymbol, side='BUY', type='STOP_MARKET', stopPrice=slPrice, closePosition=True)
        except:
            print("Unexpected error:", sys.exc_info()[0])       
else:
    if longPosition and closeLongCondition(df.iloc[-1], df.iloc[-2]):   
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(5)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance)
        try:
            closeLong = client.futures_create_order(symbol=pairSymbol, side='SELL', type='MARKET', quantity=closeAmount, reduceOnly='true')
            print("Close long position", coinBalance, coin, closeLong)
        except:
            print("Unexpected error:", sys.exc_info()[0]) 
    elif shortPosition and closeShortCondition(df.iloc[-1], df.iloc[-2]):
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(5)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance)
        try:
            closeShort = client.futures_create_order(symbol=pairSymbol, side='BUY', type='MARKET', quantity=closeAmount, reduceOnly='true')
            print("Close short position", coinBalance, coin, closeShort)
        except:
            print("Unexpected error:", sys.exc_info()[0])  

