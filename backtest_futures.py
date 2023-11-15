# -- Import --
import pandas as pd
import pandas_ta as pda
from binance.client import Client
import ta
import matplotlib.pyplot as plt
import numpy as np
from binance.enums import HistoricalKlinesType
import datetime
import warnings
warnings.filterwarnings('ignore')

# -- Define Binance Client --
client = Client()

# -- You can change the crypto pair ,the start date and the time interval below --
pairName = "ETHUSDT"
startDate = "01 november 2021"
timeInterval = '1h'

# -- Hyper parameters --
stochOverBought = 0.8
stochOverSold = 0.2
SlPct = 0.05
TpPct = 0.1
maWindow = 500

# -- You can change variables below --
leverage = 1
wallet = 1000
makerFee = 0.0002
takerFee = 0.0004
maxDrawdown = -0.3

# -- Rules --
stopLossActivation = True
takeProfitActivation = True

# -- Load all price data from binance API --
klinesT = client.get_historical_klines(pairName, timeInterval, startDate, klines_type=HistoricalKlinesType.FUTURES)

# -- Define your dataset --
df = pd.DataFrame(klinesT, columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore' ])
df['close'], df['high'], df['low'], df['open'] = pd.to_numeric(df['close']), pd.to_numeric(df['high']), pd.to_numeric(df['low']), pd.to_numeric(df['open'])

# -- Set the date to index --
df = df.set_index(df['timestamp'])
df.index = pd.to_datetime(df.index, unit='ms')
del df['timestamp']

print("Data loaded 100%")

# -- Drop all columns we do not need --
df.drop(df.columns.difference(['open','high','low','close','volume']), 1, inplace=True)

# -- TRIX --
df['TRIX'] = ta.trend.ema_indicator(ta.trend.ema_indicator(ta.trend.ema_indicator(close=df['close'], window=9), window=9), window=9)
df['TRIX_PCT'] = df["TRIX"].pct_change()*100
df['TRIX_SIGNAL'] = ta.trend.sma_indicator(df['TRIX_PCT'], 21)
df['TRIX_HISTO'] = df['TRIX_PCT'] - df['TRIX_SIGNAL']

# -- Stochasitc RSI --
df['STOCH_RSI'] = ta.momentum.stochrsi(close=df['close'], window=14)

# EMA
df['EMA'] = ta.trend.ema_indicator(close=df['close'], window=maWindow)
df['MA'] = ta.trend.sma_indicator(close=df['close'], window=maWindow)

print("Indicators loaded 100%")

# -- If you want to run your BackTest on a specific period, uncomment the line below --
dfTest = df['2021-12-01':'2022-12-01']

# -- Definition of dt, that will be the dataset to do your trades analyses --
dt = None
dt = pd.DataFrame(columns=['date', 'position', 'reason',
                           'price', 'frais', 'wallet', 'drawBack'])

# -- Do not touch these values --
initialWallet = wallet
lastAth = wallet
previousRow = dfTest.iloc[0]
stopLoss = 0
takeProfit = 500000
orderInProgress = ''
longIniPrice = 0
shortIniPrice = 0
longLiquidationPrice = 500000
shortLiquidationPrice = 0


# -- Condition to open Market LONG --
def openLongCondition(row, previousRow):
    if (row['close'] > row['MA'] 
        and row['TRIX_HISTO'] > 0 
        and row['STOCH_RSI'] < stochOverBought
    ):
        return True
    else:
        return False

# -- Condition to close Market LONG --
def closeLongCondition(row, previousRow):
    if (row['TRIX_HISTO'] < 0 and row['STOCH_RSI'] > stochOverSold):
        return True
    else:
        return False

# -- Condition to open Market SHORT --
def openShortCondition(row, previousRow):
    if (row['close'] < row['MA'] 
        and row['TRIX_HISTO'] < 0 
        and row['STOCH_RSI'] > stochOverSold
    ):
        return True
    else:
        return False

# -- Condition to close Market SHORT --
def closeShortCondition(row, previousRow):
    if (row['TRIX_HISTO'] > 0 and row['STOCH_RSI'] < stochOverBought):
        return True
    else:
        return False

# -- Iteration on all your price dataset (df) --
for index, row in dfTest[1:].iterrows():
    stopTrades = (wallet-initialWallet)/initialWallet < maxDrawdown and dfTest.index[-1].day > 15
    if stopTrades:
        print("no trading")
    proportionTrading = 1
    # -- If there is an order in progress --
    if orderInProgress != '':
        closePosition = False
        # -- Check if there is a LONG order in progress --
        if orderInProgress == 'LONG':
            # -- Check Liquidation --
            if row['low'] < longLiquidationPrice:
                print('/!\ YOUR LONG HAVE BEEN LIQUIDATED the',index)
                break
            # -- Check Stop Loss --
            if row['low'] < stopLoss and stopLossActivation:
                orderInProgress = ''
                closePrice = stopLoss
                #closePriceWithFee = closePrice - takerFee * closePrice
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Stop Loss Long'
                closePosition = True
            # -- Check Take Profit --
            elif row['high'] > takeProfit and takeProfitActivation:
                orderInProgress = ''
                closePrice = takeProfit
                #closePriceWithFee = closePrice - takerFee * closePrice
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Take Profit Long'
                closePosition = True
            # -- Check If you have to close the LONG --
            elif closeLongCondition(row, previousRow):
                orderInProgress = ''
                closePrice = row['close']
                #closePriceWithFee = row['close'] - takerFee * row['close']
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Close Market Long'
                closePosition = True
                
        # -- Check if there is a SHORT order in progress --
        elif orderInProgress == 'SHORT':
            # -- Check Liquidation --
            if row['high'] > shortLiquidationPrice:
                print('/!\ YOUR SHORT HAVE BEEN LIQUIDATED the',index)
                break

            # -- Check stop loss --
            if row['high'] > stopLoss and stopLossActivation :
                orderInProgress = ''
                closePrice = stopLoss
                #closePriceWithFee = closePrice + takerFee * closePrice
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Stop Loss Short'
                closePosition = True
            # -- Check take profit --
            elif row['low'] < takeProfit and takeProfitActivation:
                orderInProgress = ''
                closePrice = takeProfit
                #closePriceWithFee = closePrice + takerFee * closePrice
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Take Profit Short'
                closePosition = True
            # -- Check If you have to close the SHORT --
            elif closeShortCondition(row, previousRow):
                orderInProgress = ''
                closePrice = row['close']
                #closePriceWithFee = row['close'] + takerFee * row['close']
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Close Market Short'
                closePosition = True        
                
        if closePosition:
            #fee = wallet * (1+pr_change) * leverage * takerFee
            #wallet = wallet * (1+pr_change*leverage) - fee
            fee = wallet * proportionTrading * (1+pr_change) * leverage * takerFee
            wallet = wallet * (1-proportionTrading) + wallet * proportionTrading * (1+pr_change*leverage) - fee
            # -- Check if your wallet hit a new ATH to know the drawBack --
            if wallet > lastAth:
                lastAth = wallet
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': position, 'reason': reason, 'price': round(closePrice, 2),
                     'frais': round(fee, 3), 'wallet': round(wallet, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3),}
            dt = dt.append(myrow, ignore_index=True) 

    # -- If there is NO order in progress --
    if orderInProgress == '' and not stopTrades:
        # -- Check If you have to open a LONG --
        if openLongCondition(row, previousRow):
            orderInProgress = 'LONG'
            closePrice = row['close']
            longIniPrice = row['close'] 
            fee = wallet * proportionTrading * leverage * takerFee
            amount = wallet * proportionTrading * leverage - fee            
            wallet -= fee
            tokenAmount = amount / row['close']
            longLiquidationPrice = longIniPrice - (wallet/tokenAmount)
            if stopLossActivation:
                stopLoss = closePrice - SlPct * closePrice
                #stopLoss = closePrice - row['ATR']
            if takeProfitActivation:
                takeProfit = closePrice + TpPct * closePrice
                #takeProfit = closePrice + 2*row['ATR']
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': 'Open Long', 'reason': 'Open Long Market', 'price': round(closePrice, 2),
                     'frais': round(fee, 3), 'wallet': round(wallet+fee, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3)}
            dt = dt.append(myrow, ignore_index=True)
        
        # -- Check If you have to open a SHORT --
        if openShortCondition(row, previousRow):
            orderInProgress = 'SHORT'
            closePrice = row['close']
            shortIniPrice = row['close'] 
            fee = wallet * proportionTrading * leverage * takerFee
            amount = wallet * proportionTrading * leverage - fee     
            wallet -= fee
            tokenAmount = amount / row['close']
            shortLiquidationPrice = shortIniPrice + (wallet/tokenAmount)
            if stopLossActivation:
                stopLoss = closePrice + SlPct * closePrice
            if takeProfitActivation:
                takeProfit = closePrice - TpPct * closePrice
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': 'Open Short', 'reason': 'Open Short Market', 'price': round(closePrice, 2),
                     'frais': round(fee, 3), 'wallet':round(wallet+fee, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3)}
            dt = dt.append(myrow, ignore_index=True)
    previousRow = row

# -- BackTest Analyses --
dt = dt.set_index(dt['date'])
dt.index = pd.to_datetime(dt.index)
dt['resultat%'] = dt['wallet'].pct_change()*100

dt['tradeIs'] = ''
dt.loc[dt['resultat%'] > 0, 'tradeIs'] = 'Good'
dt.loc[dt['resultat%'] < 0, 'tradeIs'] = 'Bad'

iniClose = dfTest.iloc[0]['close']
lastClose = dfTest.iloc[len(dfTest)-1]['close']
holdPercentage = ((lastClose - iniClose)/iniClose)
holdWallet = (1+holdPercentage) * initialWallet
algoPercentage = ((wallet - initialWallet)/initialWallet)
vsHoldPercentage = ((wallet - holdWallet)/holdWallet) * 100

try:
    tradesPerformance = round(dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].sum()
            / dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].count(), 2)
except:
    tradesPerformance = 0
    print("/!\ There is no Good or Bad Trades in your BackTest, maybe a problem...")

try:
    TotalGoodTrades = dt.groupby('tradeIs')['date'].nunique()['Good']
    AveragePercentagePositivTrades = round(dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].count(), 2)
    idbest = dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].idxmax()
    bestTrade = str(
        round(dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].max(), 2))
except:
    TotalGoodTrades = 0
    AveragePercentagePositivTrades = 0
    idbest = ''
    bestTrade = 0
    print("/!\ There is no Good Trades in your BackTest, maybe a problem...")

try:
    TotalBadTrades = dt.groupby('tradeIs')['date'].nunique()['Bad']
    AveragePercentageNegativTrades = round(dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].count(), 2)
    idworst = dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].idxmin()
    worstTrade = round(dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].min(), 2)
except:
    TotalBadTrades = 0
    AveragePercentageNegativTrades = 0
    idworst = ''
    worstTrade = 0
    print("/!\ There is no Bad Trades in your BackTest, maybe a problem...")

TotalTrades = TotalGoodTrades + TotalBadTrades
winRateRatio = (TotalGoodTrades/TotalTrades) * 100

reasons = dt['reason'].unique()

print("BackTest finished, final wallet :", round(wallet,2), "$")

print("Pair Symbol :",pairName,)
print("Period : [" + str(dfTest.index[0]) + "] -> [" + str(dfTest.index[len(dfTest)-1]) + "]")
print("Starting balance :", initialWallet, "$")

print("\n----- General Informations -----")
print("Final balance :", round(wallet, 2), "$")
print("Performance vs US Dollar :", round(algoPercentage*100, 2), "%")
print("Buy and Hold Performence :", round(holdPercentage*100, 2), "%")
print("Performance vs Buy and Hold :", round(vsHoldPercentage, 2), "%")
print("Best trade : +"+bestTrade, "%, the ", idbest)
print("Worst trade :", worstTrade, "%, the ", idworst)
print("Worst drawBack :", str(round(100*dt['drawBack'].min(), 2)), "%")
print("Total fees : ", round(dt['frais'].sum(), 2), "$")

print("\n----- Trades Informations -----")
print("Total trades on period :", TotalTrades)
print("Number of positive trades :", TotalGoodTrades)
print("Number of negative trades : ", TotalBadTrades)
print("Trades win rate ratio :", round(winRateRatio, 2), '%')
print("Average trades performance :",tradesPerformance,"%")
print("Average positive trades :", AveragePercentagePositivTrades, "%")
print("Average negative trades :", AveragePercentageNegativTrades, "%")

print("\n----- Trades Reasons -----")
reasons = dt['reason'].unique()
for r in reasons:
    print(r+" number :", dt.groupby('reason')['date'].nunique()[r])

dt[['wallet', 'price']].plot(subplots=True, figsize=(20, 10))

del dt['date']
dt.to_csv('trades.csv')
