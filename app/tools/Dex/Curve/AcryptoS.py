from tools import DecimalMath, Database
from concurrent.futures import ThreadPoolExecutor
from typing import List
from tools import Schema
from enum import Enum
from web3 import Web3
import rapidjson
import os


class AcryptoS(Schema.Pair):
    '''
    Has More than one pool But Since Curve algo is shit im denying it
    look though thier doc for underlying :*
    
    For Now Only Use EllipsisPair Module TY :)
    
    '''
    _abi_pair = [{"name":"A","outputs":[{"type":"uint256","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":5199},{"name":"fee","outputs":[{"type":"uint256","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":2111},{"name":"balances","outputs":[{"type":"uint256","name":""}],"inputs":[{"type":"uint256","name":"arg0"}],"stateMutability":"view","type":"function","gas":2190},{"name":"lp_token","outputs":[{"type":"address","name":""}],"inputs":[],"stateMutability":"view","type":"function","gas":2231}]
    
    A: int
    N_COINS: int = 4
    rates: List[int] = [10 ** 18] * 4

    def sync(self, partial=True, N_COINS=0):
        if os.getenv('OFFLINE_MODE'):
            return 
        if not self._w3:
            self._w3 = Web3(Web3.HTTPProvider(Schema.RPC_GATEWAY))
        _c = self._w3.eth.contract(
            self.address, abi=self._abi_pair)
        if N_COINS:
            self.N_COINS = N_COINS
        if not partial:
            self.A = _c.functions.A().call()
            self.lp_fee = _c.functions.fee().call() // 10 ** 10
        if len(self.reserves) < self.N_COINS:
            self.reserves = [0 for i in range(self.N_COINS)]
        for i in range(self.N_COINS):
            self.reserves[i] = _c.functions.balances(i).call()
        self.save()

    def sync_threaded(self, partial=True):
        '''
        Attention since all ellipsis_pools have tokens with 18 decimal i dont check it ......
        '''
        if not self._w3:
            w3 = Web3(Web3.HTTPProvider(Schema.RPC_GATEWAY))
        _funs = {}
        _c = w3.eth.contract(
            self.address, abi=Database.get_abi("EllipsisFinancePool"))
        if len(self.reserves) < self.N_COINS:
            self.reserves = [0 for i in range(self.N_COINS)]

        def task(_fun):
            if isinstance(_fun[0], int):
                self.reserves[_fun[0]] = _fun[1].call()
            else:
                setattr(self, _fun[0], _fun[1].call())

        for i in range(self.N_COINS):
            _funs.update({i: _c.functions.balances(i)})

        if not partial:
            _funs.update({"lp_fee": _c.functions.fee()})
            _funs.update({"A": _c.functions.A()})

        with ThreadPoolExecutor() as e:
            for fun in _funs.items():
                e.submit(task, fun)
        self.fee /= 10 ** 10

    def amount_out(self, index_of_from_token, index_of_to_token, amount_in):
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
                    D_P = D_P * D / (_x * self.N_COINS)
                Dprev = D
                D = (Ann * S + D_P * self.N_COINS) * D / \
                    ((Ann - 1) * D + (self.N_COINS + 1) * D_P)
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

            amp = self._A
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
                c = c * D / (_x * self.N_COINS)
            c = c * D / (Ann * self.N_COINS)
            b = S_ + D / Ann  # - D
            y_prev = 0
            y = D
            for _i in range(255):
                y_prev = y
                y = (y*y + c) / (2 * y + b - D)
                # Equality with the precision of 1
                if y > y_prev:
                    if y - y_prev <= 1:
                        break
                else:
                    if y_prev - y <= 1:
                        break
            return y

        def get_dy(i, j, dx):

            dx = dx * self.rates[i]
            _balances = list(
                map(lambda x, rate: x * rate, self.rates, balances))
            x = _balances[i] + dx
            y = get_y(i, j, x, _balances)

            dy = (_balances[j] - y)
            _fee = self.lp_fee * dy
            return dy - _fee

        # if amount_in > 10**10 :
        #     amount_in / 10**self.decimals[index_of_from_token]
        return get_dy(index_of_from_token, index_of_to_token, amount_in)
