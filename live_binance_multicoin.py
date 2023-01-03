from binance import Client
import pandas as pd
import numpy as np
import ta
from datetime import datetime
import time
import matplotlib.pyplot as plt

now = datetime.now()
print(now.strftime("%d-%m %H:%M:%S"))

client = Client('', '')

pairList = [
    'AVAXUSDT',
    'SOLUSDT',
    'MATICUSDT',
    'MANAUSDT',
    'SANDUSDT',
    'CHZUSDT',
    'ATOMUSDT',    
    'VETUSDT' 
    ]


timeframe = '1h'

# -- Indicator variable --
trixLength = 9
trixSignal = 21
stochWindow = 14

# -- Hyper parameters --
maxOpenPosition = 3
stochOverBought = 0.95
stochOverSold = 0.05
TpPct = 0.15

def getHistorical(symbol):
    klinesT = client.get_historical_klines(
        symbol, Client.KLINE_INTERVAL_1HOUR, "5 day ago UTC")
    dataT = pd.DataFrame(klinesT, columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore' ])
    dataT['close'] = pd.to_numeric(dataT['close'])
    dataT['high'] = pd.to_numeric(dataT['high'])
    dataT['low'] = pd.to_numeric(dataT['low'])
    dataT['open'] = pd.to_numeric(dataT['open'])
    dataT['volume'] = pd.to_numeric(dataT['volume'])
    return dataT

dfList = {}
for pair in pairList:
    #print(pair)
    df = getHistorical(pair)
    dfList[pair.replace('USDT','')] = df

for coin in dfList:
    # -- Drop all columns we do not need --
    dfList[coin].drop(columns=dfList[coin].columns.difference(['open','high','low','close','volume']), inplace=True)

    # -- Indicators, you can edit every value --
    dfList[coin]['TRIX'] = ta.trend.ema_indicator(ta.trend.ema_indicator(ta.trend.ema_indicator(close=dfList[coin]['close'], window=trixLength), window=trixLength), window=trixLength)
    dfList[coin]['TRIX_PCT'] = dfList[coin]["TRIX"].pct_change()*100
    dfList[coin]['TRIX_SIGNAL'] = ta.trend.sma_indicator(dfList[coin]['TRIX_PCT'], trixSignal)
    dfList[coin]['TRIX_HISTO'] = dfList[coin]['TRIX_PCT'] - dfList[coin]['TRIX_SIGNAL']
    dfList[coin]['STOCH_RSI'] = ta.momentum.stochrsi(close=dfList[coin]['close'], window=stochWindow)
        
print("Data and Indicators loaded 100%")

# -- Condition to BUY market --
def buyCondition(row, previousRow=None):
    if row['TRIX_HISTO'] > 0 and row['STOCH_RSI'] < 0.05:
        return True
    else:
        return False

# -- Condition to SELL market --
def sellCondition(row, previousRow=None):
    if row['TRIX_HISTO'] < 0 and row['STOCH_RSI'] > 0.95:
        return True
    else:
        return False
    

def getBalance(myclient, coin):
    jsonBalance = myclient.get_balances()
    if jsonBalance == []:
        return 0
    pandaBalance = pd.DataFrame(jsonBalance)
    if pandaBalance.loc[pandaBalance['coin'] == coin].empty:
        return 0
    else:
        return float(pandaBalance.loc[pandaBalance['coin'] == coin]['free'])

def get_step_size(symbol):
    stepSize = None
    for filter in client.get_symbol_info(symbol)['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            stepSize = float(filter['stepSize'])
    return stepSize

def get_price_step(symbol):
    stepSize = None
    for filter in client.get_symbol_info(symbol)['filters']:
        if filter['filterType'] == 'PRICE_FILTER':
            stepSize = float(filter['tickSize'])
    return stepSize

def convert_amount_to_precision(symbol, amount):
    stepSize = get_step_size_futures(symbol)
    amount = Decimal(str(amount))
    return float(amount - amount % Decimal(str(stepSize)))

def convert_price_to_precision(symbol, price):
    stepSize = get_price_step(symbol)
    price = Decimal(str(price))
    return float(price - price % Decimal(str(stepSize)))

usdtBalance = float(client.get_asset_balance(asset='USDT')['free'])
coinBalance = {}
coinInUsdt = {}
for coin in dfList:
    #print(coin)
    actualPrice = dfList[coin]['close'].iloc[-1]
    coinAmount = float(client.get_asset_balance(asset=coin)['free']) + float(client.get_asset_balance(asset=coin)['locked'])
    coinBalance[coin] = coinAmount
    coinInUsdt[coin] = coinAmount * actualPrice

totalBalanceInUsdt = usdtBalance + sum(coinInUsdt.values())
coinPositionList = []
for coin in coinInUsdt:
    if coinInUsdt[coin] > 0.05 * totalBalanceInUsdt:
        coinPositionList.append(coin)
openPositions = len(coinPositionList)
        
#Sell
for coin in coinPositionList:
        if sellCondition(dfList[coin].iloc[-1], dfList[coin].iloc[-2]) == True:
            openPositions -= 1
            symbol = coin + 'USDT'
            orders = client.get_open_orders(symbol=symbol)    
            for order in orders:
                client.cancel_order(symbol=symbol, orderId=order['orderId'])     
            time.sleep(1)
            sellAmount = convert_amount_to_precision(symbol, coinBalance[coin])
            sell = client.order_market_sell(symbol=symbol, quantity=sellAmount)
            print("Sell", coinBalance[coin], coin, sell)
        else:
            print("Keep", coin)

#Buy
if openPositions < maxOpenPosition:
    for coin in dfList:
        if coin not in coinPositionList:
            if buyCondition(dfList[coin].iloc[-1], dfList[coin].iloc[-2]) == True and openPositions < maxOpenPosition:
                time.sleep(1)
                usdtBalance = float(client.get_asset_balance(asset='USDT')['free'])
                actualPrice = dfList[coin]['close'].iloc[-1]
                symbol = coin + 'USDT'

                tpPrice = convert_price_to_precision(symbol, actualPrice + TpPct * actualPrice)
                buyQuantityInUsdt = usdtBalance * 1/(maxOpenPosition-openPositions)

                if openPositions == maxOpenPosition - 1:
                    buyQuantityInUsdt = 0.95 * buyQuantityInUsdt

                buyAmount = convert_amount_to_precision(symbol, buyQuantityInUsdt/actualPrice)

                buy = client.order_market_buy(symbol=symbol, quantity=buyAmount)
                print("Buy", buyAmount, coin, 'at', actualPrice, buy)

                time.sleep(1)
                try:
                    time.sleep(1)
                    tp = client.order_limit_sell(symbol=symbol, quantity=buyAmount, price=tpPrice)
                    print("Place", buyAmount, coin, "TP at", tpPrice, tp)
                except:
                    pass
                
                openPositions += 1
