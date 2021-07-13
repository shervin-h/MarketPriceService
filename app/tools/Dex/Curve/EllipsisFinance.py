from concurrent.futures import ThreadPoolExecutor
from tools import SyncRedis as Redis
from tools import DecimalMath,Database
from typing import List
from tools import Schema 
from enum import Enum
from web3 import Web3
import os
import time
import logging
import rapidjson

class EllipsisPair(Schema.Pair):
    A : int
    N_COINS : int
    rates : List[int]
    _PRECISION =  10 ** 18
    _FEE_DENOMINATOR = 10 ** 10
    
    _abi_pair = [{"name":"A","outputs":[{"type":"uint256","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":5199},{"name":"fee","outputs":[{"type":"uint256","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":2111},{"name":"balances","outputs":[{"type":"uint256","name":""}],"inputs":[{"type":"uint256","name":"arg0"}],"stateMutability":"view","type":"function","gas":2190},{"name":"lp_token","outputs":[{"type":"address","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":2231}]

    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return 
        _c = self._w3.eth.contract(self.address , abi =  self._abi_pair)
        if not partial :
            self.A = _c.functions.A().call()
            self.lp_fee = _c.functions.fee().call() // 10 ** 10
        if len(self.reserves) != self.N_COINS:
            self.reserves = [0 for i in range(self.N_COINS)]        
        for i in range(self.N_COINS):
            self.reserves[i] = _c.functions.balances(i).call()
        time.sleep(Redis.rpc_request(self.chain))
        self.save()
        return self
        
    def amount_out(self,index_of_from_token , index_of_to_token , amount_in ):
        balances = self.reserves
        def get_D(xp, amp):
            S = 0
            for _x in xp:
                S += _x
            if S == 0:
                return 0

            Dprev = 0
            D = S
            Ann = amp * self.N_COINS
            for _i in range(255):
                D_P = D
                for _x in xp:
                    # If division by 0, this will be borked: only withdrawal will work. And that is good
                    D_P = D_P * D // (_x * self.N_COINS)
                Dprev = D
                D = (Ann * S + D_P * self.N_COINS) * D // ((Ann - 1) * D + (self.N_COINS + 1) * D_P)
                # Equality with the precision of 1
                if D > Dprev:
                    if D - Dprev <= 1:
                        break
                else:
                    if Dprev - D <= 1:
                        break
            return D


        def get_y(i, j, x, xp_):
            # x in the input is converted to the same price/precision

            assert i != j       # dev: same coin
            assert j >= 0       # dev: j below zero

            # should be unreachable, but good for safety
            assert i >= 0

            amp = self.A
            D = get_D(xp_, amp)
            c = D
            S_ = 0
            Ann = amp * self.N_COINS
            _x = 0
            for _i in range(int(self.N_COINS)):
                if _i == i:
                    _x = x
                elif _i != j:
                    _x = xp_[_i]
                else:
                    continue
                S_ += _x
                c = c * D // (_x * self.N_COINS)
            c = c * D // (Ann * self.N_COINS)
            b = S_ + D // Ann  # - D
            y_prev = 0
            y = D
            for _i in range(255):
                y_prev = y
                y = (y*y + c) // (2 * y + b - D)
                # Equality with the precision of 1
                if y > y_prev:
                    if y - y_prev <= 1:
                        break
                else:
                    if y_prev - y <= 1:
                        break
            return y

        def get_dy(i, j, dx):

            dx = dx * self.rates[i] // self._PRECISION
            _balances = list(map(lambda x , rate : (x * rate) //self._PRECISION , self.rates , balances ))
            x = _balances[i] + dx
            y = get_y(i, j, x, _balances)
            
            dy = (_balances[j] - y)  * self._PRECISION // self.rates[j]
            _fee = self.lp_fee * dy  // self._FEE_DENOMINATOR
            return dy - _fee
        
        # if amount_in > 10**10 :
        #     amount_in / 10**self.decimals[index_of_from_token]      
        return get_dy(index_of_from_token , index_of_to_token , amount_in)

    def token_price(self, token) -> dict:
        '''
        TODO
        - ITS WRONG WHEN THERE ARE NOT USD Tokens 
        # ! change if you switch chain
        '''
        return {_t:1 for _t in self.tokens}
        