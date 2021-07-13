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

CONCURRENCT_NODE_CALLS = 10


class MDEXPair(Schema.Pair):
    '''
    Most of Dexs in BSC are a clone of uniswap hence the name
    Dexs include [Pancake , Burger , Cake , Jul , ...]

    '''

    _abi_factory = [{"constant": True, "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "name": "allPairs", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}, {"constant": True, "inputs": [], "name":"allPairsLength", "outputs":[{"internalType": "uint256",
                                                                                                                                                                                                                                                                                                                                                    "name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}, {"constant": True, "inputs": [{"internalType": "address", "name": "pair", "type": "address"}], "name": "getPairFees", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}]
    _abi_pair = [{"constant":True,"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"payable":False,"stateMutability":"view","type":"function"},{"constant": True, "inputs": [], "name":"token0", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}, {
        "constant": True, "inputs": [], "name":"token1", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}]

    @classmethod
    def my_pairs(cls, chain , factory_address, fee=0, start_index=0):
        '''
        Each Pair Can have a diffrent Fee but the max is 9970 so :))))
        '''

        _c = chain.w3.eth.contract(factory_address, abi=cls._abi_factory)
        _result_pairs = []
        if _c:
            if cls._ENABLED:
                def retrive_pair(i, _r_p):
                    try:
                        time.sleep(Redis.rpc_request(
                            chain, count=3))
                        _addr = _c.functions.allPairs(i).call()
                        if not Redis.get_obj(_addr,chain.redis_db, is_pair=True):

                            _c_pair = chain.w3.eth.contract(
                                _addr, abi=cls._abi_pair)
                            _fee = _c.functions.getPairFees(_addr).call()
                            t0 = _c_pair.functions.token0().call()
                            t1 = _c_pair.functions.token1().call()
                            _t0 = Redis.get_obj(t0,chain.redis_db, is_token=True)
                            _t1 = Redis.get_obj(t1,chain.redis_db, is_token=True)
                            if not _t0:
                                _t0 = Schema.Token.detail(t0 , chain)
                            if not _t1:
                                _t1 = Schema.Token.detail(t1, chain)

                            _data = {
                                "address": _addr,
                                "reserves": [0, 0],
                                "tokens": [t0, t1],
                                "type": Schema.DEX_TYPE.MDEX.value,
                                "lp_fee": _fee,
                                "dex": factory_address
                            }
                            _r_p.append(cls(**_data))
                            Redis.dex_pairs_retrival(factory_address,chain.redis_db, i)
                            _t0.add_pair(_addr)
                            _t1.add_pair(_addr)
                            logging.info(
                                f'added---->{_addr} - {factory_address} - MDEX')
                    except Exception as e:
                        logging.exception(e)
                time.sleep(Redis.rpc_request(chain))
                pair_count = int(_c.functions.allPairsLength().call())
                
                _retrived_so_far = Redis.dex_pairs_retrival(factory_address , chain.redis_db)
                
                with ThreadPoolExecutor(CONCURRENCT_NODE_CALLS) as executor:
                    for i in range(start_index, pair_count):
                        if str(i) in _retrived_so_far:
                            continue
                        executor.submit(retrive_pair, i, _result_pairs)
        return _result_pairs

    @property
    def tolerance(self):
        return 0
        # self.PI

    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return 
        _c = self._w3.eth.contract(
            self.address, abi=self._abi_pair)
        # if not partial or not self.lp_fee:
        #     self.lp_fee = Database.get_lp_fee(self.dex)
        self.reserves[0] ,self.reserves[1] , block_time  = _c.functions.getReserves().call()
        self.save()

    def amount_out(self, index_of_from_token, index_of_to_token, amount_in):
        amount_in *= self.lp_fee
        return (amount_in * self.reserves[1]) // ((self.reserves[0] * self._LP_PERSICION) + amount_in)
