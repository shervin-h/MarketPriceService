from dotenv import load_dotenv
load_dotenv()
from Network import Chain
from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError
from datetime import datetime
from decimal import Decimal
from tools import SyncRedis as Redis
import requests
import logging
import json
import time

UPDATE_INTERVAL = 60
BINANCE_URL = "http://api.binance.com/api/v3/ticker/price"
REFRENCE_CURRENCY = "USDT"
USDT_PRICE = 1
PRICE_PERCISION = 1
USD_PRICE = 1
CMC_API_KEY = "6122b1c4-1873-47b4-9ef6-d407ad672d6d"
PREFERED_BASES_ADDRESS = [
    "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83" , ## WFTM
]
USD_ADDRESSES = [
    "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E",  # DAI
    "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # USDC
]
NETWORK_VALUE_SYMBOL = 'FTM'
NETWORK_VALUE_WRAPPED_SYMBOL = 'WFTM'
global _CACHE_
_CACHE_ = {}
_CACHE_TIMEOUT = 100000000000 # seconds

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
            for token in _tkns:
                token.value_list["binance"] = 0
                for item in _response.json():
                    if(item["symbol"] == token.symbol + REFRENCE_CURRENCY):
                        token.value_list["binance"] = item["price"] * USDT_PRICE
                        break
                    elif(item["symbol"] == REFRENCE_CURRENCY + token.symbol):
                        try:
                            token.value_list["binance"] = (1/item["price"]) * USDT_PRICE
                            break
                        except:
                            pass
                    if(token.value_list["binance"] == 0):
                        for str in _allpairs:
                            if((token.symbol in str) & (token.value_list["binance"] == 0)):
                                _midPrice = 0
                                _mid2Price = 0
                                if(str.index(token.symbol) == 0):
                                    _tempSymbol = str[len(token.symbol):]
                                    for item in _response.json():
                                        if(item["symbol"] == token.symbol + _tempSymbol):
                                            _midPrice = float(item["price"])
                                            break
                                    for item in _response.json():
                                        if(item["symbol"] == _tempSymbol + REFRENCE_CURRENCY):
                                            _mid2Price = float(item["price"])
                                            break
                                        elif(item["symbol"] == REFRENCE_CURRENCY + _tempSymbol):
                                            _mid2Price = 1/float(item["price"])
                                            break
                                    token.value_list["binance"] = _midPrice * _mid2Price * USDT_PRICE

                                else:
                                    _tempSymbol = str[:len(token.symbol)]
                                    for item in _response.json():
                                        if(item["symbol"] == _tempSymbol + token.symbol):
                                            _midPrice = 1/float(item["price"])
                                            break
                                    for item in _response.json():
                                        if(item["symbol"] == _tempSymbol + REFRENCE_CURRENCY):
                                            _mid2Price = float(item["price"])
                                            break
                                        elif(item["symbol"] == REFRENCE_CURRENCY + _tempSymbol):
                                            _mid2Price = 1/float(item["price"])
                                            break
                                    token.value_list["binance"] = _midPrice * _mid2Price * USDT_PRICE
                if(token.value_list["binance"]):
                    token.save()
        else:
            logging.info("BinanceApi data fetch error!")
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
                    tkn.value_list["cionmarketcap"] = float(token["quote"]["USD"]["price"] * PRICE_PERCISION)
                    if(tkn.value_list["cionmarketcap"]):
                        tkn.save()
    except Exception as e:
        logging.exception(e)
        return 0

def getMPOnline(token):
    res = []
    MPB = 0
    MPC = 0
    if token.value_list["binance"]:
        MPB = token.value_list["binance"]
    if token.value_list["cionmarketcap"]:
        MPC = token.value_list["cionmarketcap"]
    if MPC:
        res.append(MPC)
    if MPB:
        res.append(MPB)
    if res:
        return sum(res) / len(res)
    if not res and token.symbol == 'WETH':
        return getMPOnline('ETH') 
    if not res and token.symbol == 'WBNB':
        return getMPOnline('BNB') 
    if not res and token.symbol == 'WFTM':
        return getMPOnline('FTM')     
    
def getMPAMMDexes(tokens,chain, base=PREFERED_BASES_ADDRESS, usd_addresses=USD_ADDRESSES):
    for tkn in tokens:
        my_prices = []
        for _pair in tkn.pairs:
            pair = Redis.get_obj(_pair,tkn.chain.redis_db, is_pair=True)
            for _token in pair.tokens:
                if _token == tkn.address:
                    continue
                if _token in usd_addresses:
                    my_prices.append(pair.token_price(tkn)[_token] * USD_PRICE)
                if _token in base:
                    if chain.wrapped_token == _token:
                        _p = pair.token_price(tkn)[_token] * getMPOnline(Redis.get_obj(_token ,tkn.chain.redis_db, is_token=True))
                        my_prices.append(_p)
                    else:
                        _p = pair.token_price(tkn)[
                            _token] * getMPOnline(Redis.get_obj(_token ,tkn.chain.redis_db, is_token=True))
                        my_prices.append(_p)
        if my_prices:
            tkn.value_list["pmmdex"] = sum(my_prices) / len(my_prices)
            tkn.save()
    else:
        logging.error(f"Can't Fetch on chain price of token {tkn}  X_X")
        return 0 
    
        
def market_price(token):
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
    for chain in Chain.chains():
        ti = time.time()
        all_token_objs = Redis.get_obj_all_tokens(chain)
        getMPBinance(all_token_objs)
        getMPCoinmarketCap(all_token_objs)
        getMPAMMDexes(all_token_objs, chain, PREFERED_BASES_ADDRESS, USD_ADDRESSES)
        ti -= time.time()
        print(ti)
while True:            
    update_market_price()
    time.sleep(UPDATE_INTERVAL)