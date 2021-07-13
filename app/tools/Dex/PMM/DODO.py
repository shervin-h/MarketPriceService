from typing import List
from concurrent.futures import ThreadPoolExecutor
from tools import  SyncRedis as Redis , Schema
from tools.DecimalMath import DecimalMath
from enum import Enum
from web3 import Web3
from tools import Database
import os
import time
import logging
import asyncio
CONCORENT_CALLLS = 8
class Equilibrium(Enum):
    '''
    Same as _R_STATUS
    '''
    ONE = 0
    ABOVE_ONE = 1
    BELOW_ONE = 2

class DODOPairV1(Schema.Pair):
    '''
    Base is always token0 and Quote is token1
    Threre are only a handfull of em so no need to call rpc_node
    '''
    mid_price: int = 0
    oracle_price: int = 0 
    K : int = 0
    R : Equilibrium = Equilibrium.ONE
    reserves_init  : List[int] = []
    lpFeeRate : int = 3000000000000000
    mtFeeRate : int = 0
    _abi_factory = [{"inputs":[],"name":"getDODOs","outputs":[{"internalType":"address[]","name":"","type":"address[]"}],"stateMutability":"view","type":"function"}]
    _abi_pair = [{"inputs":[],"name":"_K_","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_R_STATUS_","outputs":[{"internalType":"enum Types.RStatus","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_BASE_BALANCE_","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_QUOTE_BALANCE_","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_LP_FEE_RATE_","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_MT_FEE_RATE_","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getMidPrice","outputs":[{"internalType":"uint256","name":"midPrice","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getOraclePrice","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getExpectedTarget","outputs":[{"internalType":"uint256","name":"baseTarget","type":"uint256"},{"internalType":"uint256","name":"quoteTarget","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_BASE_TOKEN_","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"_QUOTE_TOKEN_","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]
    
    
    @classmethod
    def pair_detail(cls,chain , _pair , factory_address):
        contract = chain.w3.eth.contract(_pair , abi = cls._abi_pair)
                    
        time.sleep( Redis.rpc_request(chain , count = 9))
        
        quote_token = contract.functions._QUOTE_TOKEN_().call()
        base_token = contract.functions._BASE_TOKEN_().call()
        _t0 =  Redis.get_obj(base_token,chain.redis_db, is_token = True)
        _t1 =  Redis.get_obj(quote_token,chain.redis_db, is_token = True)
        if not _t0 :
            _t0 =   Schema.Token.detail(base_token, chain)
        if not _t1 :
            _t1 =   Schema.Token.detail(quote_token, chain)
        
        return cls(**{
            "chain": chain,
            "address" : _pair,
            "K" : contract.functions._K_().call(),
            "R" : contract.functions._R_STATUS_().call(),
            "reserves_init" : contract.functions.getExpectedTarget().call(),
            "lp_fee" : contract.functions._LP_FEE_RATE_().call(),
            "mtFeeRate" : contract.functions._MT_FEE_RATE_().call(),
            "mid_price" : contract.functions.getMidPrice().call(),
            "oracle_price" : contract.functions.getOraclePrice().call(),
            "tokens" : [base_token , quote_token],
            "reserves" : [0,0],
            "type": Schema.DEX_TYPE.DODOV1.value,
            "dex":factory_address,
            }
        )

        _t0.add_pair(_pair)
        _t1.add_pair(_pair)
        Redis.dex_pairs_retrival(factory_address,chain.redis_db,_pair)
        
    @classmethod
    def my_pairs(cls ,chain, factory_address ):
        '''
        FYI DODOzoo contract is the factory of dodos :)))
        '''
        
        res_pairs = []
        _c = chain.w3.eth.contract(factory_address, abi=cls._abi_factory)
        time.sleep( Redis.rpc_request(chain))
        
        _pairs = _c.functions.getDODOs().call() 
        _retrived_so_far = Redis.dex_pairs_retrival(factory_address,chain.redis_db)
        for _pair  in _pairs:
            if _pair in _retrived_so_far:
                continue
            if not Redis.get_obj(_pair, is_pair=True) and _pair not in ["0x8d078451a63D118bACC9Cc46698cc416f81C93E2" ,
                                                                        "0x89E5015ff12E4536691aBfe5f115B1cB37a35465",
                                                                        "0xC64a1d5C819B3c9113cE3DB32B66D5D2b05B4CEf"] :
                try:
                    logging.info(f'tying to add---->{_pair} - {factory_address} - DODOV1')
                    
                    res_pairs.append(
                    cls.pair_detail(chain, _pair , factory_address)
                    )
                    logging.info(f'added---->{_pair} - {factory_address} - DODOV1')
                except Exception as e:
                    logging.exception(e)
        return res_pairs
    
    
    def sync(self , partial = None): 
        if os.getenv('OFFLINE_MODE'):
            return 
        contract = self._w3.eth.contract(self.address , abi = self._abi_pair)
        
        time.sleep( Redis.rpc_request(self.chain , count = 2))
        
        self.reserves[0] = contract.functions._BASE_BALANCE_().call()
        self.reserves[1] = contract.functions._QUOTE_BALANCE_().call()
        
        if not partial:
            time.sleep( Redis.rpc_request(self.chain , count = 7))
            self.K = contract.functions._K_().call()
            self.R = contract.functions._R_STATUS_().call()
            self.reserves_init[0] , self.reserves_init[1] = contract.functions.getExpectedTarget().call()
            self.lp_fee = contract.functions._LP_FEE_RATE_().call()
            self.mtFeeRate = contract.functions._MT_FEE_RATE_().call()
            self.mid_price = contract.functions.getMidPrice().call()
            self.oracle_price = contract.functions.getOraclePrice().call()
        self.save()
    
    def getExpectedTarget(self):
        bB = self.reserves[0]
        qB = self.reserves[1]
        if (self.R == Equilibrium.ONE):
            return (self.reserves_init[0], self.reserves_init[1])
        elif(self.R == Equilibrium.BELOW_ONE):
            payQuoteToken = self._RBelowBackToOne()
            return(self.reserves_init[0], qB + payQuoteToken)
        elif(self.R == Equilibrium.ABOVE_ONE):
            payBaseToken = self._RAboveBackToOne()
            return(bB+payBaseToken, self.reserves_init[1])

    def _SolveQuadraticFunctionForTarget(self,V1, k, fairAmount):
        #V0 = V1+V1*(sqrt-1)/2k
        logging.info(V1)
        logging.info(k)
        logging.info(fairAmount)
        logging.info(self)
        sqrt = DecimalMath.divCeil((DecimalMath.mul(k, fairAmount))*4 , V1)
        sqrt = DecimalMath.sqrt((sqrt + (DecimalMath.ONE)) * (DecimalMath.ONE))
        premium = DecimalMath.divCeil(sqrt - DecimalMath.ONE, k*2)
        #V0 is greater than or equal to V1 according to the solution
        return DecimalMath.mul(V1, DecimalMath.ONE + premium)

    def _RBelowBackToOne(self):#DANGER! Decimals might be wrong!
            #important: carefully design the system to make sure spareBase always greater than or equal to 0
            spareBase = self.reserves[0] - self.reserves_init[0]
            price = self.oracle_price 
            fairAmount = DecimalMath.mul(spareBase, price) # //10**(self.token0.decimal)
            # fairAmount = spareBase * price //10**(self.token0.decimal)
            newTargetQuote = self._SolveQuadraticFunctionForTarget(self.reserves[1],self.K,fairAmount)
            return newTargetQuote - self.reserves[1]

    def _RAboveBackToOne(self):#DANGER! Decimals might be wrong!
            #important: carefully design the system to make sure spareBase always greater than or equal to 0
            spareQuote = self.reserves[1] - self.reserves_init[1]
            price = self.oracle_price
            fairAmount = DecimalMath.divFloor(spareQuote, price)
            # fairAmount = (spareQuote * 10**(self.token0.decimal))//price
            newTargetBase = self._SolveQuadraticFunctionForTarget(self.reserves[0],self.K,fairAmount)
            return newTargetBase - self.reserves[0]

    def _RAboveSellBaseToken(self,amount,baseBalance,targetBaseAmount):
        #here we don't require B1 <= targetBaseAmount
        #Because it is limited at upper function
        #See Trader.querySellBaseToken
         B1 = baseBalance + amount
         return self._RAboveIntegrate(targetBaseAmount, B1, baseBalance)

    def _RAboveIntegrate(self,B0, B1, B2):
        i = self.oracle_price #DANGER! Decimals might be wrong!
        return self._GeneralIntegrate(B0, B1, B2, i)
    
    def _GeneralIntegrate(self,V0, V1, V2, i):#DANGER! Decimals might be wrong!
         fairAmount = DecimalMath.mul(i, V1-V2) #i*delta
         V0V0V1V2 = DecimalMath.divCeil((V0*V0)//V1, V2)
         penalty = DecimalMath.mul(self.k, V0V0V1V2) #k(V0^2/V1/V2)
         return DecimalMath.mul(fairAmount, DecimalMath.ONE - self.k + penalty)

    def _ROneSellBaseToken(self,amount, targetQuoteTokenAmount):
         i = self.oracle_price #DANGER! Decimals might be wrong!
         Q2 = self._SolveQuadraticFunctionForTrade(targetQuoteTokenAmount,targetQuoteTokenAmount,DecimalMath.mul(i, amount),False,self.K)
        # in theory Q2 <= targetQuoteTokenAmount
        # however when amount is close to 0, precision problems may cause Q2 > targetQuoteTokenAmount
         return targetQuoteTokenAmount - Q2

    def _SolveQuadraticFunctionForTrade(self,Q0,Q1,ideltaB,deltaBSig,k):
        # calculate -b value and sig
        # -b = (1-k)Q1-kQ0^2/Q1+i*deltaB
         kQ02Q1 = ((DecimalMath.mul(k, Q0)) * Q0) // Q1 # kQ0^2/Q1
         b = DecimalMath.mul(DecimalMath.ONE - k, Q1) # (1-k)Q1
         minusbSig = True
         if(deltaBSig):
            b = b + ideltaB # (1-k)Q1+i*deltaB
         else:
            kQ02Q1 = kQ02Q1 + ideltaB # i*deltaB+kQ0^2/Q1
         if(b >= kQ02Q1):
            b = b - kQ02Q1
            minusbSig = True
         else:
            b = kQ02Q1 - b
            minusbSig = False
         # calculate sqrt   
         squareRoot = DecimalMath.mul((DecimalMath.ONE - k) * 4, (DecimalMath.mul(k, Q0)) * Q0) # 4(1-k)kQ0^2
         squareRoot = DecimalMath.sqrt((b*b) + squareRoot) # sqrt(b*b+4(1-k)kQ0*Q0)
        # final res
         denominator = (DecimalMath.ONE - k ) * 2 # 2(1-k)
         if(minusbSig):
            numerator = b + squareRoot
         else:
            numerator = squareRoot - b

         if(deltaBSig):
            return DecimalMath.divFloor(numerator, denominator)
         else:
            return DecimalMath.divCeil(numerator, denominator)

    def _RBelowSellBaseToken(self, amount, quoteBalance, targetQuoteAmount):
        i = self.oracle_price #DANGER! Decimals might be wrong!
        Q2 = self._SolveQuadraticFunctionForTrade(targetQuoteAmount,quoteBalance, DecimalMath.mul(i, amount), False, self.K)
        return quoteBalance - Q2

    def querysellBaseToken(self, sellBaseAmount):
        (newBaseTarget, newQuoteTarget) = self.getExpectedTarget()
        # case 1: R=1
        # R falls below one
        if(self.R == Equilibrium.ONE):
            newRStatus= Equilibrium.BELOW_ONE
        elif(self.R == Equilibrium.ABOVE_ONE):
            backToOnePayBase = newBaseTarget - self.reserves[0]
            backToOneReceiveQuote = self.reserves[1] - newQuoteTarget
            # case 2: R>1
            # complex case, R status depends on trading amount
            if (sellBaseAmount < backToOnePayBase):
                # case 2.1: R status do not change
                receiveQuote = self._RAboveSellBaseToken(sellBaseAmount, self.reserves[0], newBaseTarget)
                newRStatus = Equilibrium.ABOVE_ONE
                if (receiveQuote > backToOneReceiveQuote):
                    # [Important corner case!] may enter this branch when some precision problem happens. And consequently contribute to negative spare quote amount
                    # to make sure spare quote>=0, mannually set receiveQuote=backToOneReceiveQuote
                    receiveQuote = backToOneReceiveQuote
            elif (sellBaseAmount == backToOnePayBase):
                # case 2.2: R status changes to ONE
                receiveQuote = backToOneReceiveQuote
                newRStatus = Equilibrium.ONE
            else:
                # case 2.3: R status changes to BELOW_ONE
                receiveQuote = backToOneReceiveQuote + (self._ROneSellBaseToken(sellBaseAmount - backToOnePayBase, newQuoteTarget))
                newRStatus = Equilibrium.BELOW_ONE
        else:
            # _R_STATUS_ == Types.RStatus.BELOW_ONE
            # case 3: R<1
            receiveQuote = self._RBelowSellBaseToken(sellBaseAmount, self.reserves[1], newQuoteTarget)
            newRStatus = Equilibrium.BELOW_ONE
        # count fees
        lpFeeQuote = DecimalMath.mul(receiveQuote, self.lpFeeRate)
        mtFeeQuote = DecimalMath.mul(receiveQuote, self.mtFeeRate)
        receiveQuote = receiveQuote - (lpFeeQuote) - (mtFeeQuote)

        if (self.R != newRStatus): #Update R might be wrong HERE!
            self.R = newRStatus

        # print(f'receiveQuote={receiveQuote}, lpFeeQuote={lpFeeQuote}, mtFeeQuote={mtFeeQuote}, newRStatus={newRStatus}, newQuoteTarget={newQuoteTarget}, newBaseTarget={newBaseTarget}')
        return (receiveQuote, lpFeeQuote, mtFeeQuote, newRStatus, newQuoteTarget, newBaseTarget)

    def _ROneBuyBaseToken(self, amount, targetBaseTokenAmount):
        if(amount < targetBaseTokenAmount):
            B2 = targetBaseTokenAmount - amount
            payQuoteToken = self._RAboveIntegrate(targetBaseTokenAmount, targetBaseTokenAmount, B2)
            return payQuoteToken
        else:
            return "DODO_BASE_BALANCE_NOT_ENOUGH"

    def _RAboveBuyBaseToken(self, amount, baseBalance, targetBaseAmount):
        if(amount < baseBalance):
            B2 = baseBalance - amount
            return self._RAboveIntegrate(targetBaseAmount, baseBalance, B2)
        else:
            return "DODO_BASE_BALANCE_NOT_ENOUGH"

    def _RBelowBuyBaseToken(self, amount, quoteBalance, targetQuoteAmount):
        # Here we don't require amount less than some value
        # Because it is limited at upper function
        # See Trader.queryBuyBaseToken
        i = self.oracle_price #DANGER! Decimals might be wrong!
        Q2 = self._SolveQuadraticFunctionForTrade(targetQuoteAmount, quoteBalance, DecimalMath.mul(i, amount), True, self.K)
        return Q2 - quoteBalance

    def _queryBuyBaseToken(self, amount):
        (newBaseTarget, newQuoteTarget) = self.getExpectedTarget()

        #charge fee from user receive amount
        lpFeeBase = DecimalMath.mul(amount, self.lpFeeRate)
        mtFeeBase = DecimalMath.mul(amount, self.mtFeeRate)
        buyBaseAmount = amount + lpFeeBase + mtFeeBase

        if(self.R == Equilibrium.ONE):
            # case 1: R=1
            payQuote = self._ROneBuyBaseToken(buyBaseAmount, newBaseTarget)
            newRStatus = Equilibrium.ABOVE_ONE
        elif(self.R == Equilibrium.ABOVE_ONE):
            # case 2: R>1
            payQuote = self._RAboveBuyBaseToken(buyBaseAmount, self.reserves[0], newBaseTarget)
            newRStatus = Equilibrium.ABOVE_ONE
        elif(self.R == Equilibrium.BELOW_ONE):
            backToOnePayQuote = newQuoteTarget - self.reserves[1]
            backToOneReceiveBase = self.reserves[0] - newBaseTarget
            # case 3: R<1
            # complex case, R status may change
            if (buyBaseAmount < backToOneReceiveBase):
                # case 3.1: R status do not change
                # no need to check payQuote because spare base token must be greater than zero
                payQuote = self._RBelowBuyBaseToken(buyBaseAmount, self.reserves[1], newQuoteTarget)
                newRStatus = Equilibrium.BELOW_ONE
            elif(buyBaseAmount == backToOneReceiveBase):
                # case 3.2: R status changes to ONE
                payQuote = backToOnePayQuote
                newRStatus = Equilibrium.ONE
            else:
                # case 3.3: R status changes to ABOVE_ONE
                payQuote = backToOnePayQuote + self._ROneBuyBaseToken(buyBaseAmount - backToOneReceiveBase, newBaseTarget)
                newRStatus = Equilibrium.ABOVE_ONE
        if (self.R != newRStatus): #Update R might be wrong HERE!
            self.R = newRStatus
        print(f'payQuote={payQuote}, lpFeeBase={lpFeeBase}, mtFeeBase={mtFeeBase}, newRStatus={newRStatus}, newQuoteTarget={newQuoteTarget}, newBaseTarget={newBaseTarget}')
        return (payQuote, lpFeeBase, mtFeeBase, newRStatus, newQuoteTarget, newBaseTarget)
    
    def amount_out(self,index_of_from_token , index_of_to_token , amount_in ):
        if index_of_from_token == 1:
            # _queryBuyBaseToken()
            return 0
        if index_of_from_token == 0 and index_of_to_token == 1:
            return self.querysellBaseToken(amount_in)

class DODOPairV2(DODOPairV1):
    
    _abi_factory = {"CPfactory":[{"inputs":[{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"}],"name":"getCrowdPoolingBidirection","outputs":[{"internalType":"address[]","name":"baseToken0Pools","type":"address[]"},{"internalType":"address[]","name":"baseToken1Pools","type":"address[]"}],"stateMutability":"view","type":"function"}]
             ,"Dfactory":[{"inputs":[{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"}],"name":"getDODOPoolBidirection","outputs":[{"internalType":"address[]","name":"baseToken0Pool","type":"address[]"},{"internalType":"address[]","name":"baseToken1Pool","type":"address[]"}],"stateMutability":"view","type":"function"}]}
    # _abi_pair = {"inputs":[],"name":"getPMMStateForCall","outputs":[{"internalType":"uint256","name":"i","type":"uint256"},{"internalType":"uint256","name":"K","type":"uint256"},{"internalType":"uint256","name":"B","type":"uint256"},{"internalType":"uint256","name":"Q","type":"uint256"},{"internalType":"uint256","name":"B0","type":"uint256"},{"internalType":"uint256","name":"Q0","type":"uint256"},{"internalType":"uint256","name":"R","type":"uint256"}],"stateMutability":"view","type":"function"}
    _abi_pair = [{"inputs":[],"name":"getPMMStateForCall","outputs":[{"internalType":"uint256","name":"i","type":"uint256"},{"internalType":"uint256","name":"K","type":"uint256"},{"internalType":"uint256","name":"B","type":"uint256"},{"internalType":"uint256","name":"Q","type":"uint256"},{"internalType":"uint256","name":"B0","type":"uint256"},{"internalType":"uint256","name":"Q0","type":"uint256"},{"internalType":"uint256","name":"R","type":"uint256"}],"stateMutability":"view","type":"function"}]
    @classmethod
    def my_pairs(cls,chain,factory_address={} ,base_tokens=[]):
        '''
        Since DoDo has three types of pools we go through all possibilities :)
        For getting pairs contract asks for pairs address so make sure to provide this method
        with needed information.
        factories : [DSPFactory , DVMFactory ,DPPFactory ,UpCrowdPoolingFactory,CrowdPoolingFactory] :count is 5
        factory_address = {
            name : _address
        }
        basetokens = list[tokenobjs]
        '''
        res_pairs = []

        def add_pair(func ,t0, t1 ,dex_addr):
            
            try:
                _retrived_so_far = Redis.dex_pairs_retrival(dex_addr,chain.redis_db)
                time.sleep( Redis.rpc_request(chain))
                _pairs = func(t0,t1).call()
                _t0 =  Redis.get_obj(t0,chain.redis_db, is_token = True)
                _t1 =  Redis.get_obj(t1,chain.redis_db, is_token = True)
                if not _t0 :
                    _t0 =   Schema.Token.detail(t0, chain)
                if not _t1 :
                    _t1 =   Schema.Token.detail(t1, chain)

                data = {
                    "chain":chain,
                    "type":Schema.DEX_TYPE.DODOV2.value,
                    "dex" : dex_addr
                }
                ## Base is t0
                for _pair in _pairs[0]:
                    if _pair in _retrived_so_far:
                        continue
                    _data = chain.w3.eth.contract(_pair , abi = cls._abi_pair).functions.getPMMStateForCall().call()
                    res_pairs.append(cls(
                        **{ "tokens": [t0,t1],
                            "address": _pair,
                            "reserves" : [_data[2],_data[3]],
                            "reserves_init" : [_data[4],_data[5]],
                            "mid_price" :_data[0],
                            "K" : _data[1],
                            "R" : _data[6],
                           **data}
                    ))
                    _t0.add_pair(_pair)
                    _t1.add_pair(_pair)
                    Redis.dex_pairs_retrival(dex_addr,chain.redis_db,_pair)
                    logging.info(f'added---->{_pair} - {dex_addr} - DODOV2')
                    
                # Base is t1
                for _pair in _pairs[1]:
                    if _pair in _retrived_so_far:
                        continue
                    _data = chain.w3.eth.contract(_pair , abi = cls._abi_pair).functions.getPMMStateForCall().call()
                    res_pairs.append(cls(**{"tokens": [t1,t0],
                                            "address": _pair,
                                            "reserves" : [_data[3],_data[2]],
                                            "reserves_init" : [_data[5],_data[4]],
                                            "mid_price" :_data[0],
                                            "K" : _data[1],
                                            "R" : _data[6],
                                            **data}))
                    _t0.add_pair(_pair)
                    _t1.add_pair(_pair)
                    Redis.dex_pairs_retrival(dex_addr,chain.redis_db,_pair)
                    logging.info(f'added---->{_pair} - {dex_addr} - DODOV2')
                
            except Exception as e:
                logging.exception(e)
                
        for _name , _addr in factory_address.items():
            if _name in ["CrowdPoolingFactory" , "UpCrowdPoolingFactory"]:
                _func = chain.w3.eth.contract(_addr , abi = cls._abi_factory["CPfactory"]).functions.getCrowdPoolingBidirection
            else:
                _func = chain.w3.eth.contract(_addr , abi = cls._abi_factory["Dfactory"]).functions.getDODOPoolBidirection
                
            with ThreadPoolExecutor(CONCORENT_CALLLS) as executor:
                _prev_token = base_tokens[0]
                for i in range(1, len(base_tokens)):
                    executor.submit(add_pair , _func ,_prev_token, base_tokens[i] , _addr )
                    _prev_token = base_tokens[i]
            return res_pairs


 
    def sync(self , partial = None): 
        if os.getenv('OFFLINE_MODE'):
            return 
        # contract = self._w3.eth.contract(self.address , abi = self._abi_pair)
        
        time.sleep( Redis.rpc_request(self.chain , count = 1))
        _data = self._w3.eth.contract(self.address, abi = self._abi_pair).functions.getPMMStateForCall().call()
        
        self.reserves = [_data[2],_data[3]]
        self.mid_price = _data[0]
        self.k = _data[1]
        self.R = _data[6]
        self.save()
    
'''
  function querySellQuoteToken(address dodo, uint256 amount) public view returns (uint256) {
        DODOState memory state;
        (state.baseTarget, state.quoteTarget) = IDODOV1(dodo).getExpectedTarget();
        state.rStatus = RStatus(IDODOV1(dodo)._R_STATUS_());
        state.oraclePrice = IDODOV1(dodo).getOraclePrice();
        state.Q = IDODOV1(dodo)._QUOTE_BALANCE_();
        state.B = IDODOV1(dodo)._BASE_BALANCE_();
        state.K = IDODOV1(dodo)._K_();

        uint256 boughtAmount;
        // Determine the status (RStatus) and calculate the amount
        // based on the state
        if (state.rStatus == RStatus.ONE) {
            boughtAmount = _ROneSellQuoteToken(amount, state);
        } else if (state.rStatus == RStatus.ABOVE_ONE) {
            boughtAmount = _RAboveSellQuoteToken(amount, state);
        } else {
            uint256 backOneBase = state.B.sub(state.baseTarget);
            uint256 backOneQuote = state.quoteTarget.sub(state.Q);
            if (amount <= backOneQuote) {
                boughtAmount = _RBelowSellQuoteToken(amount, state);
            } else {
                boughtAmount = backOneBase.add(
                    _ROneSellQuoteToken(amount.sub(backOneQuote), state)
                );
            }
        }
        // Calculate fees
        return
            DecimalMath.divFloor(
                boughtAmount,
                DecimalMath.ONE.add(IDODOV1(dodo)._MT_FEE_RATE_()).add(
                    IDODOV1(dodo)._LP_FEE_RATE_()
                )
            );
    }
'''
