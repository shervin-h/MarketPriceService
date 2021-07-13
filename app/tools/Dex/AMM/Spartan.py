from tools import DecimalMath, Database, SyncRedis as Redis
from concurrent.futures import ThreadPoolExecutor
from typing import List
from tools import Schema
from enum import Enum
from web3 import Web3
import os
import time
import logging
import asyncio
import rapidjson


class SpartanPair(Schema.Pair):
    '''
    BASE is tokens[0]
    TOKEN is tokens[1]
    Contract info is located in Base token DAO which can change and should transact a cal to does address as well
    Spartan's lp_fee changes based on requested amount
    '''
    # _abi_factory = [{"inputs":[],"name":"allPools","outputs":[{"internalType":"address[]","name":"_allPools","type":"address[]"}],"stateMutability":"view","type":"function"}]
    _abi_factory = [{"inputs": [], "name":"BASE", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name":"allPools", "outputs":[{"internalType": "address[]", "name": "_allPools",
                                                                                                                                                                                                                        "type": "address[]"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name":"allTokens", "outputs":[{"internalType": "address[]", "name": "_allTokens", "type": "address[]"}], "stateMutability": "view", "type": "function"}]
    _abi_pair = [{"inputs": [], "name":"baseAmountPooled", "outputs":[{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {
        "inputs": [], "name":"tokenAmountPooled", "outputs":[{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]

    @classmethod
    def my_pairs(cls,chain, factory_address):
        '''
        The Pools Excists on utils contract :)
        '''
        _c = chain.w3.eth.contract(factory_address, abi=cls._abi_factory)
        if _c:
            if True:
                _r_p = []
                time.sleep(Redis.rpc_request(chain, count=3))
                _pairs = _c.functions.allPools().call()
                _tokens = _c.functions.allTokens().call()
                _base = _c.functions.BASE().call()
                _retrived_so_far = Redis.dex_pairs_retrival(factory_address,chain.redis_db)
                logging.info(f"---spratan--pairs--->{_retrived_so_far}")
                for _pair, _token in zip(_pairs, _tokens):
                    try:
                        if _pair not in _retrived_so_far:

                            _t0 = Redis.get_obj(_base,chain.redis_db, is_token=True)
                            _t1 = Redis.get_obj(_token,chain.redis_db, is_token=True)

                            if not _t0:
                                time.sleep(Redis.rpc_request(
                                    chain ))
                                _t0 = Schema.Token.detail(_base , chain)
                            if not _t1:
                                time.sleep(Redis.rpc_request(
                                    chain))
                                _t1 = Schema.Token.detail(_token, chain)

                            _data = {
                                "chain":chain,
                                "address": _pair,
                                "reserves": [0, 0],
                                "tokens": [_base, _token],
                                "type": Schema.DEX_TYPE.SPARTAN.value,
                                "lp_fee": 0,
                                "dex": factory_address
                            }
                            _r_p.append(cls(**_data))
                            Redis.dex_pairs_retrival(factory_address,chain.redis_db, _pair)
                            _t0.add_pair(_pair)
                            _t1.add_pair(_pair)
                            logging.info(
                                f'added---->{_pair} - {factory_address} - SPARTAN')
                    except Exception as e:
                        logging.exception(e)
                return _r_p

    @property
    def tolerance(self):
        return 0
        # self.PI

    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return 
        _c = self._w3.eth.contract(self.address, abi=self._abi_pair)
        time.sleep(Redis.rpc_request(self.chain,count = 2))
        self.reserves = [
            _c.functions.baseAmountPooled().call(),
            _c.functions.tokenAmountPooled().call()
        ]
        logging.info(f'--syncing--spartan-->{self.reserves}')
        self.save()

    def amount_out(self, index_of_from_token, index_of_to_token, amount_in):
        '''
        // y = (x * X * Y )/(x + X)^2
        uint numerator = x.mul(X.mul(Y));
        uint denominator = (x.add(X)).mul(x.add(X));
        return numerator.div(denominator);
        '''
        x = self.reserves[index_of_from_token]
        y = self.reserves[index_of_to_token]
        return (amount_in * x * y) // (x + amount_in) ** 2

    def lp_fee(self,index_of_from_token,index_of_to_token,amount_in):
        '''
        // y = (x * x * Y) / (x + X)^2
        uint numerator = x.mul(x.mul(Y));
        uint denominator = (x.add(X)).mul(x.add(X));
        return numerator.div(denominator);
        '''
        x = self.reserves[index_of_from_token]
        y = self.reserves[index_of_to_token]
        return (amount_in * amount_in * y) // (x + amount_in) ** 2
