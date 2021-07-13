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

_FACTORY_ADDRESS = "0xD41B24bbA51fAc0E4827b6F94C0D6DDeB183cD64"


class MoonSwapPair(Schema.Pair):
    '''
    AKA 1inch swap pool 
    It`s an amm with a small twisted amount out
    you`ll see
    YET UNDER DEVELOPMENT
    TODO
    - MAKE SURE OF OUT PUT -> is 0.01 % less the amount should be
    - HOW DOES IT EXACTLY WORKS
    - TOLERANCE
    POINTS
    - since token0 can be network token i change it to WBNB in graph but concider it as BNB here :)))))))) fuck this
    '''
    slip_fee: int
    _FEE_PERSICION = 18

    _abi_pair = [{"constant": True, "inputs": [], "name":"token0", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}, {"constant": True, "inputs": [], "name":"token1", "outputs":[{"internalType": "address", "name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"}, {"inputs": [], "name":"fee", "outputs":[{"internalType": "uint256", "name": "",
                                                                                                                                                                                                                                                                                                                                                                                                                                                  "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name":"slippageFee", "outputs":[{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "contract IERC20", "name": "token", "type": "address"}], "name": "getBalanceForAddition", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
    _abi_factory = [{"inputs": [], "name":"isActive", "outputs":[{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name":"getAllPools", "outputs":[
        {"internalType": "contract Mooniswap[]", "name": "", "type": "address[]"}], "stateMutability": "view", "type": "function"}]

    @classmethod
    def my_pairs(cls,chain, factory_address=_FACTORY_ADDRESS):
        '''
        if possible goes through factory for all pairs
        '''
        time.sleep(Redis.rpc_request(chain))
        _c = chain.w3.eth.contract(factory_address, abi=cls._abi_factory)
        _pairs_res = []

        if _c:
            time.sleep(Redis.rpc_request(chain))

            cls._ENABLED = _c.functions.isActive().call()
            if cls._ENABLED:
                time.sleep(Redis.rpc_request(chain))
                _pairs = _c.functions.getAllPools().call()
                _retrived_so_far = Redis.dex_pairs_retrival(factory_address,chain.redis_db)
                for _addr in _pairs:
                    if _addr not in _pairs:

                        time.sleep(Redis.rpc_request(
                            chain, count=4))

                        _c_pair = chain.w3.eth.contract(
                            _addr, abi=cls._abi_pair)

                        t0 = _c_pair.functions.token0().call()
                        t1 = _c_pair.functions.token1().call()

                        if t0 == chain.value_token_address:
                            t0 = chain.wrapped_token
                        if t1 == chain.value_token_address:
                            t1 = chain.wrapped_token

                        _t0 = Redis.get_obj(t0,chain.redis_db, is_token=True)
                        _t1 = Redis.get_obj(t1,chain.redis_db, is_token=True)

                        if not _t0:
                            _t0 = Schema.Token.detail(t0, chain)
                        if not _t1:
                            _t1 = Schema.Token.detail(t1,chain)

                        _data = {
                            "chain":chain,
                            "address": _addr,
                            "reserves": [0, 0],
                            "tokens": [t0, t1],
                            "type": Schema.DEX_TYPE.MOONSWAP.value,
                            "lp_fee": _c_pair.functions.fee().call(),
                            "slip_fee": _c_pair.functions.slippageFee().call(),
                            "dex": factory_address,
                        }
                        _pairs_res.append(cls(**_data))
                        Redis.dex_pairs_retrival(factory_address,chain.redis_db, _addr)
                        _t0.add_pair(_addr)
                        _t1.add_pair(_addr)
                        logging.info(
                            f'added---->{_addr} - {factory_address} - MOON')
        return _pairs_res

    @property
    def tolerance(self):
        return 0
        # self.PI

    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return 
        _c = self._w3.eth.contract(self.address, abi=self._abi_pair)

        if not partial:
            time.sleep(Redis.rpc_request(self.chain,count = 2))
            self.fee = _c.functions.fee().call()
            self.slip_fee = _c.functions.slippageFee().call()
        
        time.sleep(Redis.rpc_request(self.chain,count = 2))
            
        self.reserves = [
            _c.functions.getBalanceForAddition(self.tokens[0]).call(),
            _c.functions.getBalanceForAddition(self.tokens[1]).call(),
        ]
        self.save()

    def amount_out(self, index_of_from_token, index_of_to_token, amount_in):
        x = self.reserves[index_of_from_token]
        y = self.reserves[index_of_to_token]

        amount = amount_in

        taxedAmount = amount - ((amount * self.lp_fee) //
                                10 ** self._FEE_PERSICION)
        srcBalancePlusTaxedAmount = x + taxedAmount
        ret = (taxedAmount * y) // srcBalancePlusTaxedAmount
        feeNumerator = (10 ** self._FEE_PERSICION *
                        srcBalancePlusTaxedAmount) - (self.slip_fee * taxedAmount)
        feeDenominator = 10 ** self._FEE_PERSICION * srcBalancePlusTaxedAmount
        return (ret * feeNumerator) // feeDenominator
