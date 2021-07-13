from tools import DecimalMath, Database, SyncRedis as Redis
from concurrent.futures import ThreadPoolExecutor
from typing import List
from tools import Schema
from enum import Enum
from web3 import Web3
import os
import time
import asyncio
import logging
import rapidjson

CONCURRENCT_NODE_CALLS = 5
MAX_RETRIES = 10


class UniswapPair(Schema.Pair):
    '''
    Most of Dexs in BSC are a clone of uniswap hence the name
    Dexs include [Pancake , Burger , Cake , Jul , ...]

    '''
    _abi_factory = [{"constant": True, "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "name": "allPairs", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view",
                     "type": "function"}, {"constant": True, "inputs": [], "name":"allPairsLength", "outputs":[{"internalType": "uint256", "name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}]
    _abi_pair = [{"constant": True, "inputs": [], "name":"getReserves", "outputs":[{"internalType": "uint112", "name": "_reserve0", "type": "uint112"}, {"internalType": "uint112", "name": "_reserve1", "type": "uint112"}, {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}], "payable": False, "stateMutability": "view", "type": "function"}, {
        "constant": True, "inputs": [], "name":"token0", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}, {"constant": True, "inputs": [], "name":"token1", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}]

    @classmethod
    def my_pairs(cls, chain ,factory_address, fee, start_index=0):
        '''
        if possible goes through factory for all pairs
        returns listOf(pair_obj)
        '''
        try:
            _c = chain.w3.eth.contract(factory_address, abi=cls._abi_factory)
        
            _result_pairs = []
            if _c:
                if cls._ENABLED:
                    try:
                        def retrive_pair(i, _r_p, fee):
                            try:
                                time.sleep(Redis.rpc_request(
                                    chain, count=3))
                                _addr = _c.functions.allPairs(i).call()
                                _c_pair = chain.w3.eth.contract(
                                    _addr, abi=cls._abi_pair)
                                t0 = _c_pair.functions.token0().call()
                                t1 = _c_pair.functions.token1().call()

                                _data = {
                                    "chain":chain,
                                    "address": _addr,
                                    "reserves": [0, 0],
                                    "tokens": [t0, t1],
                                    "type": Schema.DEX_TYPE.UNISWAP.value,
                                    "lp_fee": fee,
                                    "dex": factory_address
                                }
                                _succes = False
                                _pairs = Redis.all_pair(chain.redis_db)
                                if t0 in _pairs or t1 in _pairs:
                                    Redis.dex_pairs_retrival(factory_address,chain.redis_db, i)
                                    logging.error(f'----LP-as-token-found->{_addr}')
                                    return

                                for i in range(MAX_RETRIES):

                                    _t0 = Schema.Token.detail(t0 , chain)
                                    _t0.add_pair(_addr)

                                    _t1 = Schema.Token.detail(t1,chain)
                                    _t1.add_pair(_addr)

                                    _t1 = Schema.Token.detail(t1,chain)
                                    _t0 = Schema.Token.detail(t0,chain)
                                    if _addr in _t0.pairs and _addr in _t1.pairs:
                                        _succes = True
                                        break

                                if _succes:
                                    _r_p.append(cls(**_data))

                                    Redis.dex_pairs_retrival(factory_address,chain.redis_db, i)
                                    logging.info(
                                        f'added---->{_addr} - {factory_address} - UNIFORKS')

                            except Exception as e:
                                logging.exception(e)

                        time.sleep(Redis.rpc_request(chain))
                        pair_count = _c.functions.allPairsLength().call()
                        _retrived_so_far = Redis.dex_pairs_retrival(factory_address,chain.redis_db)
                        not_checked = {i: False for i in range(pair_count)}

                        removed_ = []
                        for i in range(len(_retrived_so_far)):
                            if not_checked.get(i, None) == None:
                                Redis.remove_badly_added_pair(factory_address,chain.redis_db, i)
                                removed_.append(i)
                                continue
                            not_checked[i] = True
                        logging.info(f'----deleted--->{removed_}')

                        with ThreadPoolExecutor(CONCURRENCT_NODE_CALLS) as executor:
                            for index, checked in not_checked.items():
                                if checked:
                                    continue
                                executor.submit(retrive_pair, index,
                                                _result_pairs, fee)
                    except Exception as e:
                        logging.exception(e)
        except Exception as e:
            logging.exception(e)
        return _result_pairs

    @property
    def tolerance(self):
        return 0
        # self.PI

    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return
        _c = self._w3.eth.contract(self.address, abi=self._abi_pair)
        # if not partial or not self.lp_fee:
        #     self.lp_fee =  Database.get_lp_fee(self.dex)
        self.reserves[0], self.reserves[1], block_time = _c.functions.getReserves().call()
        self.save()

    def amount_out(self, index_of_from_token, index_of_to_token, amount_in, no_lp=False):

        if not no_lp:
            amount_in *= self.lp_fee
        _res = (amount_in * self.reserves[index_of_to_token]) // ((self.reserves[index_of_from_token] * self._LP_PERSICION) + amount_in)
        return _res

    def price(self, from_index, to_index):
        _from_decimal = Redis.get_obj(
            self.tokens[from_index],db = self.chain.redis_db, is_token=True).decimal
        _to_decimal = Redis.get_obj(
            self.tokens[to_index],db = self.chain.redis_db, is_token=True).decimal
        if self.reserves[from_index]:
            res =  (self.reserves[to_index] * 10 ** _from_decimal)/ (self.reserves[from_index] * 10 ** _to_decimal)
            return res
        else:
            return 0

    def token_price(self, token) -> dict:
        '''
        Returns a dict which is price base on possible tokens :)
        '''
        _res = {}
        token_addr = token.address
        # if isinstance(token, Token):
        #     token_addr = token.address
        # elif token.startswith("0x"):
        #     token_addr = token
        # else:
        #     raise ValueError("Bad input")
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
