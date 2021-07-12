'''
TYPES .....
Token -> token:
address :str :{
    name :str,
    symbol:str,
    decimal :int,
    # pairs which has this token on at least on end ....
    (pair addrress):str : (How Good is this path ) : float (default is one)
}

Pair -> pair:
address : str :{
    reserve0 :float,
    reserve1 :float,
    token0 : str,
    token1 : str,
    dex :int,
    type :int,
    # [optionals]
    _A : float,
    _N_COINS : int,
    _RATES_1 : int,
    _RATES_2 : int,
    _RATES_3 : int,
    _lp_fee : float,
    _tr_fee : float,
    _k: float,
    _R : float,
    _mid_price,
    amount_out : float,
    amount_in : float,
}

Path -> path:(token0address):(token1address):(index){
    value : float (dafault = 1),
    1:str (pair address),
    2:str (pair address),
    3:str (pair address),
    ....
}
'''

from pydantic import BaseModel, Field, validator , PrivateAttr
from concurrent.futures import ThreadPoolExecutor
# from .. Main import get_market_price
from typing import Optional, List, Dict
from tools import SyncRedis as Redis
from threading import Thread
from Network import Chain
from hashlib import md5
from web3 import Web3
import rapidjson
import logging
import asyncio
import json
import enum
import time
import os
import re


DEXES = {
}
try:
    for chainId , dexes in json.load(open(os.getenv("ADDRESS_BOOK_DIR"))).items():
        if chainId not in DEXES:
            DEXES[chainId] = {}
        for dex in dexes.values():
            DEXES[chainId].update(
                {
                    dex['factory'] : {
                    "name" : dex['name'],
                    "index" : dex['index'],
                    "lp_fee" : dex.get('lp_fee' , 10000)
                    }
                }
            )
except Exception as e:
    raise ValueError("Bad Address book")

class Address(str):
    """
    # * This can change base on the chain you are in but in general this means
    # * addresses not starting with 0x and are invalid
    # * address are converted via web3.tochecksum :)
    """
    address_Eth_like = re.compile(r'^0x[\s\S]{40}$')

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            pattern='^0x[\s\S]{40}$',
            examples=['0xEF45d134b73241eDa7703fa787148D9C9F4950b0',
                      '0x152eE697f2E276fA89E96742e9bB9aB1F2E61bE3'],
        )

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        m = cls.address_Eth_like.fullmatch(v.upper())
        if not m:
            raise ValueError('invalid address format')
        return cls(f'{m.group(1)} {m.group(2)}')

    def __repr__(self):
        return f'Address({super().__repr__()})'


class DEX_TYPE(enum.Enum):
    UNISWAP = 1  # Direct Uniswap Clones
    MDEX = 2  # "Factory Contract can generate multiple fees"
    MOONSWAP = 3  # 1inch as always beeing diffrent you know :)
    SPARTAN = 4
    ELLIPSIS = 5
    VALUE_LIQUIDITY_POOL = 6
    AcryptoS = 7
    DODOV2 = 8
    DODOV1 = 9

    # def create(self, data):
    #     from tools.Dex.AMM import (UniSwap, MDEX, Spartan, MoonSwap)
    #     from tools.Dex.Curve import (EllipsisFinance, AcryptoS, ValueLiquidity)
    #     from tools.Dex.PMM import DODO
    #     _ROUTER = {
    #         1: UniSwap.UniswapPair,
    #         2: MDEX.MDEXPair,
    #         3: MoonSwap.MoonSwapPair,
    #         4: Spartan.SpartanPair,
    #         5: EllipsisFinance.EllipsisPair,
    #         6: ValueLiquidity.ValueLiquidityVPeg,
    #         7: EllipsisFinance.EllipsisPair,
    #         8: DODO.DODOPairV2,
    #         9: DODO.DODOPairV1,
    #     }
    #     return _ROUTER[self.value](**data, save=False)

# class ChainType(Chain):
#     def __init__(self,name:int):
#         self.name = Chain(name)
class FasterBaseModel(BaseModel):

    chain : Chain = None
    
    def __init__(self, chainId =None,save=True, **data):
        super().__init__(**data)
        if chainId : 
            self.chain = Chain(chainId)
        else:
            self.chain = Chain(self.chain)
        if save:
            self.save()
            
    # @property
    # def _db(self):
    #     return self.chain.redis_db
    @property
    def _w3(self):
        return self.chain.w3
    
    class Config:
        json_loads = json.loads
        json_dumps = json.dumps
        env_file = ".env"
        arbitrary_types_allowed = True

class ValueList(BaseModel):
    binance : Optional[float]
    cionmarketcap : Optional[float]
    pmmdex : Optional[float]
    
class Token(FasterBaseModel):
    '''
    TODO
        -   instead of saving token address as key token index is available
            and henece Token:Index should be another namespace
            but for later
    '''

    _abi = [{"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":False,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"payable":True,"stateMutability":"payable","type":"fallback"},{"anonymous":False,"inputs":[{"indexed":True,"name":"owner","type":"address"},{"indexed":True,"name":"spender","type":"address"},{"indexed":False,"name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"name":"from","type":"address"},{"indexed":True,"name":"to","type":"address"},{"indexed":False,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]
    
    name: str
    symbol: str
    address: Address
    decimal: int
    pairs: dict = {}
    value: float = 0
    value_timestamp: float = 0
    value_list: dict = {}

    _SHOW_PRCISION = 10_000 
    _INTIAL_PAIR_VALUE = 1
    _VALUE_TIMEOUT = 10 * 60 # ! 10 minutes
    @ property
    def price(self):
        '''
        #  todo Later should be changed to a namespace in redis
        '''
        return int(self.value * self._SHOW_PRCISION)

    @property
    def deadline(self):
        return self.value_timestamp + self._VALUE_TIMEOUT

    # def sync(self, non_blocking=False):
    #     if os.getenv('OFFLINE_MODE'):
    #         return
    #     if non_blocking:
    #         Thread(target=get_market_price, args=self)
    #     self = get_market_price(self)
    #     self.save()
    #     return self

    def _is_network_value(self):
        return self.address == self.chain.value_token_address

    def save(self, client=None):
        if Redis.update(self, db = self.chain.redis_db):
            return self
        else:
            return None

    def add_pair(self, address):
        # if not self.pairs.get(address, None):
        self.pairs.update({address: self._INTIAL_PAIR_VALUE})
        self.save()
        return self

    def remove_pair(self, address):
        try:
            
            self.pairs.pop(address)
            self.save()        
        except Exception as e:
            pass
        if address in self.pairs.keys():
            logging.error("WTF")
        return self
    
    @ classmethod   
    def my_balances(cls ,wallet , chain):

        res = []
        res.append({
            "address" : chain.value_token_address,
            "balance" : ((chain.w3.eth.get_balance(wallet)* cls._SHOW_PRCISION  )// 10 ** 18) /  cls._SHOW_PRCISION 
        })
        
        def balances_inside_executor(t_addr):
            try:
                token = Redis.get_obj(t_addr ,db = chain.redis_db, is_token=True)
                res.append({
                    "address" : t_addr ,
                    "balance": ((chain.w3.eth.contract(t_addr , abi = cls._abi).functions.balanceOf(wallet).call() * cls._SHOW_PRCISION ) // 10 ** token.decimal ) / cls._SHOW_PRCISION  })
            except :
                pass
            
        with ThreadPoolExecutor(10) as executor:
            for _t in chain.tokens.values():
                t_addr = _t['address']
                if t_addr == chain.value_token_address:
                    continue
                executor.submit(balances_inside_executor,t_addr)
        return res
    
    @ classmethod   
    def detail(cls, _address,chain, save=True):
        t = Redis.get_obj(_address,chain.redis_db, is_token=True)
        if t:
            return t
        _c = chain.w3.eth.contract(_address, abi=cls._abi)
        time.sleep(Redis.rpc_request(chain, count=3))
        try:
            name = _c.functions.name().call()
        except:
            name = ""
        try:
            symbol = _c.functions.symbol().call()
        except:
            symbol = ""
        try:
            decimals = _c.functions.decimals().call()
        except:
            decimals = 0
        data= {
            "address": _address,
            "chain" : chain,
            "name": name,
            "symbol": symbol,
            "decimal": decimals,
        }
        obj = Redis.get_obj(_address,db =chain.redis_db, is_token=True)
        if not obj:
            obj = cls(
                **data)
        logging.info(f"--added--token-->{str(obj)}")
        return obj

    def __str__(self) -> str:
        return f"{self.name} {self.address} "


class Pair(FasterBaseModel):
    address: str
    tokens: List[str]
    reserves: List[int]
    dex: str
    type: int
    # [optionals]
    lp_fee: Optional[int]
    tr_fee: Optional[int]
    # amount_out: Optional[int] = int(0)
    # amount_in: Optional[int] = int(0)

    _ENABLED = True
    _LP_PERSICION = 10000

    def delete(self, client=None):
        for token in self.tokens:
            Redis.get_obj(token,db = self.chain.redis_db, is_token=True).remove_pair(self.address)
        try:
            Redis.doom_it(self.address, db = self.chain.redis_db, is_pair=True)
        except Exception as e:
            # logging.exception(e)
            pass
        return self

    def save(self, client=None):
        if Redis.update(self,db = self.chain.redis_db, cl=client):
            return self
        else:
            return None

    def for_path(self, token):
        if token.address == self.tokens[0]:
            return self.address, 0, 1

        if token.address == self.tokens[1]:
            return self.address, 1, 0

    def end(self, token):
        if token.address == self.tokens[0]:
            return Redis.get_obj(self.tokens[1],db = self.chain.redis_db, is_token=True)

        if token.address == self.tokens[1]:
            return Redis.get_obj(self.tokens[0],db = self.chain.redis_db, is_token=True)

    def lp_fee_value(self,_amount , index_of_sell_token):
        token = Redis.get_obj(self.tokens[index_of_sell_token],db = self.chain.redis_db,is_token=True)
        res = (( token.value * 100000 * _amount * (self._LP_PERSICION - self.lp_fee ) ) // (self._LP_PERSICION * 10 ** token.decimal) )/ 100000
        # print(res , token.symbol, self.dex_name , ((_amount * 100000) // 10**token.decimal) / 100000)
        return res

    @property
    def dex_name(self):
        try:
            return DEXES[str(self.chain._id)][self.dex]['name']
        except:
            return ""

    @property
    def dex_index(self):
        try:
            return DEXES[str(self.chain._id)][self.dex]['index']
        except:
            return ""

    @property
    def k(self):
        '''
        The higher The more stable
        '''
        _r = 1
        for reserve in self.reserves:
            _r *= reserve
        return _r

    def token_price(self, token : Token) -> dict:
        '''
        Returns a dict which is price base on possible tokens :)
        '''
        _res = {}
        if isinstance(token, Token):
            token_addr = token.address
        elif token.startswith("0x"):
            token_addr = token
        else:
            raise ValueError("Bad input")
        for i in range(len(self.tokens)):
            _token = self.tokens[i]
            if _token == token_addr:
                my_index = i
                break

        for i in range(len(self.tokens)):
            _token = self.tokens[i]
            if i == my_index:
                continue
            else:
                _res[_token] = self.price(my_index, i)

        return _res

    def price(self, from_index, to_index):
        _from_decimal = Redis.get_obj(
            self.tokens[from_index],db = self.chain.redis_db, is_token=True).decimal
        _to_decimal = Redis.get_obj(
            self.tokens[to_index],db = self.chain.redis_db, is_token=True).decimal
        return (self.reserves[from_index] * 10 ** _to_decimal) / (self.reserves[to_index] * 10 ** _from_decimal)

    def undelete(self):
        try:
            Redis.get_obj(self.tokens[0],db = self.chain.redis_db, is_token=True).add_pair(self.address)
            Redis.get_obj(self.tokens[1],db = self.chain.redis_db, is_token=True).add_pair(self.address)
            Redis.undoom_it(self.address,db = self.chain.redis_db, is_pair=True)
        except Exception as e:
            logging.exception(e)
        return True

    def __str__(self) -> str:
        return f"( {self.tokens} ) -in-> {self.address} -having->{self.reserves} "


class Path(FasterBaseModel):
    tokens: List[str]
    amount: int = 0
    routes: List
    value: float = 0

    _COUNT = 0

    def save(self, client=None):
        if Redis.update(self,db = self.chain.redis_db, cl=client):
            return self
        else:
            return None

    @classmethod
    def new(cls, data: dict):
        logging.info(cls._COUNT)
        obj = Path(**data)
        cls._COUNT += 1

    @classmethod
    def key_creator(cls, token0, token1, amount, routes: list):
        checksum = md5(routes)
        return f'{token0}:{token1}:{amount}:{checksum}'

    @property
    def checksum(self):
        return md5(str(self.routes).encode('utf-8')).hexdigest()

    @property
    def key(self):
        return f'{self.tokens[0]}:{self.tokens[1]}:{self.amount}:{self.checksum}'

    def __str__(self):
        return f'--{self.key}--->{self.routes}'
