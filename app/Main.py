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
CMC_API_KEY = "6122b1c4-1873-47b4-9ef6-d407ad672d6d"
PREFERED_BASES_ADDRESS = {
    "FANTOM" : 
    {
        "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83" , # WFTM
        "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E" , # DAI
        "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75" , # USDC
        "0x049d68029688eAbF473097a2fC38ef61633A3C7A" , # FUSDT
    },
    "BINANCE":
    {
        "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c" , # WBNB
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d" , # USDC
        "0x55d398326f99059fF775485246999027B3197955" , # USDT
        "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3" , # DAI

    },
    "ETHERUM":
    {
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" , # WETH
        "0xdAC17F958D2ee523a2206206994597C13D831ec7" , # USDT
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" , # USDC
        "0x6B175474E89094C44Da98b954EedeAC495271d0F" , # DAI
    }
}

NETWORK_VALUE_SYMBOL = {'FANTOM':'FTM','ETHEREUM':'ETH','BINANCE':'BNB'}
NETWORK_VALUE_WRAPPED_SYMBOL = {'FANTOM':'WFTM','ETHEREUM':'WETH','BINANCE':'WBNB'}
global _CACHE_
_CACHE_ = {}
_CACHE_TIMEOUT = 100000000000 # seconds

def _cache(what , func , *args, **kwargs):
    global _CACHE_
    
    # if _CACHE_.get(what) :
    #     if datetime.now().timestamp() - _CACHE_.get(what).get("_CACHE_TIMEOUT") < _CACHE_TIMEOUT:
    #         return _CACHE_[what]['response'] 
    # # _cache[what] = requests.get(url=BINANCE_URL)
    # else:
    #     _CACHE_[what]= {'response': func(*args , **kwargs)}
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
                if token.symbol == NETWORK_VALUE_WRAPPED_SYMBOL[token.chain.name]:
                    for item in _response.json():
                        if(item["symbol"] == token.chain.value_token_symbol + REFRENCE_CURRENCY):
                            token.value_list["binance"] = item["price"] * USDT_PRICE
                            break
                        elif(item["symbol"] == REFRENCE_CURRENCY + token.chain.value_token_symbol):
                            try:
                                token.value_list["binance"] = (1/item["price"]) * USDT_PRICE
                                break
                            except:
                                pass
                else:
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
                if(token.value_list["binance"]):
                    token.value_list["binance"] = float(token.value_list["binance"])
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
            if tkn.symbol == NETWORK_VALUE_WRAPPED_SYMBOL[tkn.chain.name]:
                for token in tokenInfoList.data:
                    if(token["symbol"] == tkn.chain.value_token_symbol):
                        tkn.value_list["cionmarketcap"] = float(token["quote"]["USD"]["price"] * PRICE_PERCISION)
                        if(tkn.value_list["cionmarketcap"]):
                            tkn.value_list["cionmarketcap"] = float(tkn.value_list["cionmarketcap"])
                            tkn.save()
                            break
            else:
                for token in tokenInfoList.data:
                    if(token["symbol"] == tkn.symbol):
                        tkn.value_list["cionmarketcap"] = float(token["quote"]["USD"]["price"] * PRICE_PERCISION)
                        if(tkn.value_list["cionmarketcap"]):
                            tkn.value_list["cionmarketcap"] = float(tkn.value_list["cionmarketcap"])
                            tkn.save()
                            break
    except Exception as e:
        logging.exception(e)
        return 0

   
    
def getMPAMMDexes(tokens,chain):
    for tkn in tokens:
        if tkn.symbol == NETWORK_VALUE_SYMBOL[tkn.chain.name]:
            for z in tokens:
                if z.symbol == NETWORK_VALUE_WRAPPED_SYMBOL[tkn.chain.name]:
                    wrapped=z
                    break
            my_prices = []
            for _pair in wrapped.pairs:
                pair = Redis.get_obj(_pair,wrapped.chain.redis_db, is_pair=True)
                for _token in pair.tokens:
                    pass
                    if _token == wrapped.address:
                        continue
                    if _token in PREFERED_BASES_ADDRESS[tkn.chain.name]:
                        _p = pair.token_price(wrapped)[_token] * (Redis.get_obj(_token , chain.redis_db, is_token=True).average_price)
                        if _p>0:
                            my_prices.append(_p)
            if my_prices:
                tkn.value_list["pmmdex"] = float(sum(my_prices) / len(my_prices))
                tkn.save()
            else:
                logging.info(f"Can't Fetch on chain price of token {tkn}  X_X")
        else:
            my_prices = []
            for _pair in tkn.pairs:
                pair = Redis.get_obj(_pair,tkn.chain.redis_db, is_pair=True)
                for _token in pair.tokens:
                    pass
                    if _token == tkn.address:
                        continue
                    if _token in PREFERED_BASES_ADDRESS[tkn.chain.name]:
                        _p = pair.token_price(tkn)[_token] * (Redis.get_obj(_token , chain.redis_db, is_token=True).average_price)
                        my_prices.append(_p)
            if my_prices:
                tkn.value_list["pmmdex"] = float(sum(my_prices) / len(my_prices))
                tkn.save()
            else:
                logging.info(f"Can't Fetch on chain price of token {tkn}  X_X")
    
        
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
        all_token_objs = Redis.get_obj_all_tokens(chain)
        getMPCoinmarketCap(all_token_objs)
        getMPBinance(all_token_objs)
        getMPAMMDexes(all_token_objs, chain)
        logging.info(chain.name," Chain updated!")
while True:            
    update_market_price()
    time.sleep(UPDATE_INTERVAL)
