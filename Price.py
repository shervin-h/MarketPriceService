
from os import wait
from dotenv import load_dotenv
load_dotenv()
from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError
from datetime import datetime
from decimal import Decimal
import SyncRedis as Redis
import Schema 
import requests
import logging
import json

BINANCE_URL = "http://api.binance.com/api/v3/ticker/price"
REFRENCE_CURRENCY = "USDT"
PRICE_PERCISION = 1
USD_PRICE = 1
CMC_API_KEY = "6122b1c4-1873-47b4-9ef6-d407ad672d6d"
PREFERED_BASES_ADDRESS = [
    "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83" , ## WFTM
]
USD_ADDRESSES = [
    "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E",  # DAI
    # "0xAd84341756Bf337f5a0164515b1f6F993D194E1f",  # fUSD
    # "0x049d68029688eAbF473097a2fC38ef61633A3C7A",  # fUSDT
    "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # USDC
]
NETWORK_VALUE_SYMBOL = 'FTM'
NETWORK_VALUE_WRAPPED_SYMBOL = 'WFTM'
global _CACHE_
_CACHE_ = {}
_CACHE_TIMEOUT = 100 # seconds


'''
Some How Add Task to celery :)
'''
def trigger_price_task(token):
    pass

def _cache(what , func , *args, **kwargs):
    global _CACHE_
    
    if _CACHE_.get(what) :
        if datetime.now().timestamp() - _CACHE_.get(what).get("_CACHE_TIMEOUT") < _CACHE_TIMEOUT:
            return _CACHE_[what]['response'] 
    # _cache[what] = requests.get(url=BINANCE_URL)
    else:
        _CACHE_[what]= {'response': func(*args , **kwargs)}
    _CACHE_[what]["_CACHE_TIMEOUT"] = datetime.now().timestamp()
    return _CACHE_[what]['response'] 
    
def getMPBinance(_tkns):
    try:
        _allpairs = []
        _response = _cache("binance" , requests.get  , url=BINANCE_URL)
        if(_response.status_code == 200):
            for item in _response.json():
                _allpairs.append(item["symbol"])
            for _symbol in _tkns:
                _symbol.value = 0
                for item in _response.json():
                    if(item["symbol"] == _symbol.symbol + REFRENCE_CURRENCY):
                        _symbol.value = item["price"]
                        break
                    elif(item["symbol"] == REFRENCE_CURRENCY + _symbol.symbol):
                        try:
                            _symbol.value = 1/item["price"]
                            break
                        except:
                            pass
                if(_symbol.value == 0):
                    for str in _allpairs:
                        if((_symbol.symbol in str) & (_symbol.value == 0)):
                            _midPrice = 0
                            _mid2Price = 0
                            if(str.index(_symbol.symbol) == 0):
                                _tempSymbol = str[len(_symbol.symbol):]
                                for item in _response.json():
                                    if(item["symbol"] == _symbol.symbol + _tempSymbol):
                                        _midPrice = float(item["price"])
                                        break
                                for item in _response.json():
                                    if(item["symbol"] == _tempSymbol + REFRENCE_CURRENCY):
                                        _mid2Price = float(item["price"])
                                        break
                                    elif(item["symbol"] == REFRENCE_CURRENCY + _tempSymbol):
                                        _mid2Price = 1/float(item["price"])
                                        break
                                _symbol.value = _midPrice * _mid2Price

                            else:
                                _tempSymbol = str[:len(_symbol.symbol)]
                                for item in _response.json():
                                    if(item["symbol"] == _tempSymbol + _symbol.symbol):
                                        _midPrice = 1/float(item["price"])
                                        break
                                for item in _response.json():
                                    if(item["symbol"] == _tempSymbol + REFRENCE_CURRENCY):
                                        _mid2Price = float(item["price"])
                                        break
                                    elif(item["symbol"] == REFRENCE_CURRENCY + _tempSymbol):
                                        _mid2Price = 1/float(item["price"])
                                        break
                                _symbol.value = _midPrice * _mid2Price * PRICE_PERCISION
            _symbol.save()
        else:
            pass
    except Exception as e:
        logging.exception(e)
        return 0


def getMPCoinmarketCap(_tkns):
    try:
        cmc = CoinMarketCapAPI(f'{CMC_API_KEY}')
        # r = cmc.tools_priceconversion()
        tokenInfoList = _cache("CMC" , cmc.cryptocurrency_listings_latest )
        for tkn in _tkns:
            for token in tokenInfoList.data:
                if(token["symbol"] == tkn.symbol):
                    tkn.value = float(token["quote"]["USD"]["price"] * PRICE_PERCISION)
                    tkn.save()
    except Exception as e:
        logging.exception(e)
        return 0


def getMPOnline(symbol):
    res = []
    MPB = float(getMPBinance(symbol))
    MPC = getMPCoinmarketCap(symbol) 
    if MPC:
        res.append(MPC)
    if MPB:
        res.append(MPB)
    if res:
        return sum(res) / len(res)
    if not res and symbol == 'WETH':
        return getMPOnline('ETH') 
    if not res and symbol == 'WBNB':
        return getMPOnline('BNB') 
    if not res and symbol == 'WFTM':
        return getMPOnline('FTM') 
    
    
def getMPAMMDexes(token, base=PREFERED_BASES_ADDRESS, usd_addresses=USD_ADDRESSES):
    _symbol = token.symbol

    my_prices = []
    for _pair in token.pairs:
        pair = Redis.get_obj(_pair,token.chain.redis_db, is_pair=True)
        for _token in pair.tokens:
            if _token == token.address:
                continue
            if _token in usd_addresses:
                my_prices.append(pair.token_price(token)[_token] * USD_PRICE)
            if _token in base:
                if "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83" == _token:
                    _p = pair.token_price(token)[_token]  * getMPOnline("FTM")
                    my_prices.append(_p)
                else:
                    _p = pair.token_price(token)[
                        _token] * getMPOnline(Redis.get_obj(_token ,token.chain.redis_db, is_token=True).symbol)
                    my_prices.append(_p)
    if my_prices:
        return sum(my_prices) / len(my_prices)
    else:
        logging.error(f"Can't Fetch on chain price of token {token}  X_X")
        return 0 
    
        
def market_price(token ):
    _res =[]
    try:
        price_ = getMPAMMDexes(token)
        if price_:
            _res.append(price_)
    except Exception as e:
        logging.exception(e)
        pass
    try:
        _price = getMPOnline(token.symbol)
        if _price:
            _res.append(_price)
    except Exception as e:
        logging.exception(e)
        pass
    if _res:
        return sum(_res) / len(_res)
    else:
        return 0


def update_market_price():
    all_token_objs = Redis.get_obj_all_tokens(1, from_file=True)
    getMPBinance(all_token_objs)
    getMPCoinmarketCap(all_token_objs)        
while True:            
    update_market_price()
    wait(10)