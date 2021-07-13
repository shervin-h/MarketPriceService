from tools import DecimalMath,Database,SyncRedis as Redis
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

CONCURRENCT_NODE_CALLS = 5

class ValueLiquidityVPeg(Schema.Pair):
    '''
    Algo is 
    x_1**2 + x1 * (sum' - (A*n**n - 1) * D / (A * n**n)) = D ** (n + 1) / (n ** (2 * n) * prod' * A)
    x_1**2 + b*x_1 = c
    x_1 = (x_1**2 + c) / (2*x_1 + b)
    '''
    A : int = 200
    N_COINS : int = 3
    rates : List[int] = [10**18] * 3
    _PRECISION =  10 ** 18
    _FEE_DENOMINATOR = 10 ** 10

    
    _abi_factory = [{"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"allPools","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"allPoolsLength","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
    _abi_pair = [{"inputs":[{"internalType":"address","name":"index","type":"uint8"}],"name":"getToken","outputs":[{"internalType":"contract IERC20","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"swapStorage","outputs":[{"internalType":"uint256","name":"initialA","type":"uint256"},{"internalType":"uint256","name":"futureA","type":"uint256"},{"internalType":"uint256","name":"initialATime","type":"uint256"},{"internalType":"uint256","name":"futureATime","type":"uint256"},{"internalType":"uint256","name":"swapFee","type":"uint256"},{"internalType":"uint256","name":"adminFee","type":"uint256"},{"internalType":"uint256","name":"defaultWithdrawFee","type":"uint256"},{"internalType":"contract LPToken","name":"lpToken","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getTokenLength","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getA","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint8","name":"index","type":"uint8"}],"name":"getTokenBalance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getPoolTokens","outputs":[{"internalType":"contract IERC20[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"}]
    
    @classmethod
    def my_pairs(cls ,chain , factory_address):
        '''
        if possible goes through factory for all pairs
        they were deployed incorrectly so not going to be included 
        ["0x0a7E1964355020F85FED96a6D8eB10baaC457645" , "0x31165Ff269f1731610BA3bC691363E37B2A4b4c9" ],
        
        '''
        

        _c = chain.w3.eth.contract(factory_address , abi =cls._abi_factory)
        _result_pairs = []
        if _c :
            if cls._ENABLED:
                def retrive_pair(i,_r_p):
                    '''
                    If saved before there is no need to double check the address
                    '''
                    try:
                        time.sleep( Redis.rpc_request(chain,count=8))
                        _addr =_c.functions.allPools(i).call()
                        # if Redis.get_obj(_addr, is_pair=True):
                        _c_pair =  chain.w3.eth.contract(_addr, abi = cls._abi_pair)

                        A = _c_pair.functions.getA().call()
                        lp_fee = _c_pair.functions.swapStorage().call()[4]  // 10 ** 10
                        try:
                            tokens = _c_pair.functions.getPoolTokens().call()
                            N_COINS = len(tokens)
                        except:
                            N_COINS = _c_pair.functions.getTokenLength().call()
                            tokens = []
                            for i in range(N_COINS):
                                tokens.append(_c_pair.functions.getToken(i).call())
                            
                        _ts = []
                        rates = []
                        for _ti in tokens:
                            _t_tmp =  Redis.get_obj(_ti,chain.redis_db, is_token = True)
                            if not _t_tmp:
                                _t_tmp =  Schema.Token.detail(_ti,chain)
                            _ts.append(_t_tmp)
                            rates.append(10 ** _t_tmp.decimal)
                        
                        _r_p.append( cls(**{
                            "chain":chain,
                            "address":_addr,
                            "N_COINS": N_COINS,
                            "tokens" : tokens,
                            "lp_fee" : lp_fee,
                            "rates" : rates,
                            "reserves" : [0] * N_COINS,
                            "type" : Schema.DEX_TYPE.VALUE_LIQUIDITY_POOL.value,
                            "dex":factory_address,
                            "A" : A,}
                        ))
                        Redis.dex_pairs_retrival(factory_address,chain.redis_db,i)
                        for _ti in _ts:
                            _ti.add_pair(_addr)
                        logging.info(f'added---->{_addr} - {factory_address} - PEG')
                            
                    except Exception as e:
                        logging.info(f'error on ---->{_addr} - {factory_address} in index of {i}- PEG')
                        logging.exception(e)
                        
                
                _retrived_so_far = Redis.dex_pairs_retrival(factory_address,chain.redis_db) + ["0" , "1" ]
                pair_count = _c.functions.allPoolsLength().call()
                not_checked = {i :False for i in range(pair_count) }
                
                removed_ = []
                # for i in range(len(_retrived_so_far)):
                #     if not_checked.get(i , None) == None:
                #         Redis.remove_badly_added_pair(factory_address,chain.redis_db,i)
                #         removed_.append(i)
                #         continue
                #     not_checked[i] = True
                # Redis.remove_badly_added_pairpiped(factory_address,removed_)
                logging.info(f'----deleted--->{removed_}')
                
                with ThreadPoolExecutor(CONCURRENCT_NODE_CALLS) as executor:
                    for index , checked in not_checked.items():
                        if checked:
                            continue
                        executor.submit(retrive_pair , index , _result_pairs) 
                
        return _result_pairs
    
    def sync(self, partial=True):
        if os.getenv('OFFLINE_MODE'):
            return 
        if not self._w3 : 
            self._w3 = Web3(Web3.HTTPProvider(self.chain.rpc))
        _c = self._w3.eth.contract(self.address , abi = self._abi_pair)
        
        
        if not partial :
            time.sleep(Redis.rpc_request(self.chain.rpc,count = 3))
            self.A = _c.functions.getA().call()
            self.lp_fee = _c.functions.swapStorage().call()[4]  // 10 ** 10
            self.N_COINS = _c.functions.getTokenLength().call()

        time.sleep(Redis.rpc_request(self.chain,count = self.N_COINS))
        
        if len(self.reserves) < self.N_COINS:
            self.reserves = [0 for i in range(self.N_COINS)]        
        for i in range(self.N_COINS):
            self.reserves[i] = _c.functions.getTokenBalance(i).call()
        self.save()
        
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
            _x = 1
            for _i in range(int(self.N_COINS)):
                
                if _i == i:
                    _x = x
                elif _i != j:
                    _x = xp_[_i]
                    # if _x  == 0 :
                    #     print("asd")
                else:
                    continue
                S_ += _x
                c = (c * D) // (_x * self.N_COINS)
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
            
            if 0 in _balances:
                # print("asd")
                return 0
            x = _balances[i] + dx
            y = get_y(i, j, x, _balances)
            
            dy = (_balances[j] - y)  * self._PRECISION // self.rates[j]
            _fee = self.lp_fee * dy  // self._FEE_DENOMINATOR
            return dy - _fee
        
        # if amount_in > 10**10 :
        #     amount_in / 10**self.decimals[index_of_from_token]      
        return get_dy(index_of_from_token , index_of_to_token , amount_in)