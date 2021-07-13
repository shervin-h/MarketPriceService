from tools import Schema, SyncRedis as Redis
# from tools.Dex import AMM,Curve
from tools.Dex.AMM import (UniSwap, MDEX, MoonSwap, Spartan)
from tools.Dex.Curve import (ValueLiquidity, EllipsisFinance)
from tools.Dex.PMM import (DODO)

from tools.Schema import (Token, Pair, Path, DEX_TYPE)
from concurrent.futures import ThreadPoolExecutor, as_completed
import rapidjson as json
import logging
import asyncio

REDIS_CLIENT = None
MINIMUM_RESERVES = 1.5  # 1.5 of 10**token.decimal
MINIMUM_RESERVES_TOREVIVE = 3 

def index_pairs(chain, _base_tokens=[]):
    db = chain.redis_db
    pair_count = len(Redis.all_pair(db))
    with ThreadPoolExecutor(1) as executor:
        for dex, info in chain.dexs.items():
            logging.info(f'--Started-Checking--> {dex}')

            # Curves
            if DEX_TYPE(info['type']) == DEX_TYPE.ELLIPSIS:
                for pair in info['pairs']:
                    if True:
                    # if not Redis.get_obj(pair['address'],db, is_pair=True):
                        try:
                            _pair = EllipsisFinance.EllipsisPair(**{"chain" : chain ,**pair})
                            _pair.sync()
                            for token in _pair.tokens:
                                Redis.get_obj(
                                    token,db, is_token=True).add_pair(_pair.address)
                            _pair.save()
                            _pair.sync()
                            _pair.save()
                            _pair
                            
                        except Exception as e:
                            logging.exception(e)
                            pass
            if DEX_TYPE(info['type']) == DEX_TYPE.AcryptoS:
                for pair in info['pairs']:
                    logging.info(pair)
                    if True:
                    # if not Redis.get_obj(pair['address'],chain.redis_db, is_pair=True):
                        try:
                            _pair = EllipsisFinance.EllipsisPair(**{"chain" : chain ,**pair})
                            for token in _pair.tokens:
                                Redis.get_obj(
                                    token,db, is_token=True).add_pair(_pair.address)

                            _pair.sync()
                            _pair.save()
                        except:
                            pass
            if DEX_TYPE(info['type']) == DEX_TYPE.VALUE_LIQUIDITY_POOL:
                executor.submit(
                    ValueLiquidity.ValueLiquidityVPeg.my_pairs(chain , info['factory']))
            
            continue
            
            
            # PMMs
            if DEX_TYPE(info['type']) == DEX_TYPE.DODOV1:
                executor.submit(
                    DODO.DODOPairV1.my_pairs,chain, info['factory'])
            if DEX_TYPE(info['type']) == DEX_TYPE.DODOV2:
                executor.submit(DODO.DODOPairV2.my_pairs,chain,
                                info['factories'], _base_tokens)

            
            
            # AMMs
            if DEX_TYPE(info['type']) == DEX_TYPE.UNISWAP:
                executor.submit(UniSwap.UniswapPair.my_pairs,chain , 
                                info['factory'], info['lp_fee'])
            if DEX_TYPE(info['type']) == DEX_TYPE.MDEX:
                executor.submit(
                    MDEX.MDEXPair.my_pairs,chain, info['factory'])
            if DEX_TYPE(info['type']) == DEX_TYPE.MOONSWAP:
                executor.submit(
                    MoonSwap.MoonSwapPair.my_pairs,chain, info['factory'])
            if DEX_TYPE(info['type']) == DEX_TYPE.SPARTAN:
                executor.submit(
                    Spartan.SpartanPair.my_pairs,chain, info['UTILS'])

    logging.info(f"Rertived ----> { len(Redis.all_pair(chain.redis_db)) - pair_count} new pairs")


def create_graph(chain , depth=4, _base_tokens=[]):
    count = 0
    diffrent_lengths = {i: 0 for i in range(depth + 1)}

    def other_token(pair, token, _cache):
        if token.address == pair.tokens[0]:
            _t = pair.tokens[1]
            if ("t:" + _t) not in _cache:
                _cache["t:" + _t] = Redis.get_obj(_t,chain.redis_db, is_token=True)
            return _cache["t:" + _t]
        else:
            _t = pair.tokens[0]
            if ("t:" + _t) not in _cache:
                _cache["t:" + _t] = Redis.get_obj(_t,chain.redis_db, is_token=True)
            return _cache["t:" + _t]

    def make(start, end):
        logging.info(f"---graphin--started--on---{start}--->{end}")
        diffrent_lengths = {i: 0 for i in range(depth + 1)}
        count = 0
        _cache = {}
        actions = []
        try:
            actions = []
            stack = []
            _stack = []  # -> for A-(1)->B  B-(1)->A
            current = start
            for _pair in current.pairs:
                if ("p:"+_pair) not in _cache:
                    _cache["p:"+_pair] = Redis.get_obj(_pair,chain.redis_db, is_pair=True)
                pair = _cache["p:"+_pair]
                if not pair:
                    print("ASD")
                next_token_0 = other_token(pair, current, _cache)

                if next_token_0.address not in _base_tokens:
                    continue

                if pair not in _stack:
                    _stack.append(pair)
                else:
                    continue
                stack.append(pair.for_path(current))

                if next_token_0 == end:
                    data = {
                        "routes": stack.copy()
                    }
                    actions.append(data)
                    diffrent_lengths[1] += 1
                    count += 1

                for _pair in next_token_0.pairs:
                    if ("p:"+_pair) not in _cache:
                        _cache["p:"+_pair] = Redis.get_obj(_pair,chain.redis_db, is_pair=True)
                    pair = _cache["p:"+_pair]
                    if not pair:
                        print("ASD")
                    next_token_1 = other_token(pair, next_token_0, _cache)
                    if next_token_1.address not in _base_tokens:
                        continue

                    if pair not in _stack:
                        _stack.append(pair)
                    else:
                        continue
                    stack.append(pair.for_path(next_token_0))
                    if next_token_1 == end:
                        data = {
                            "routes": stack.copy()
                        }
                        diffrent_lengths[2] += 1
                        actions.append(data)
                        count += 1

                    for _pair in next_token_1.pairs:
                        if ("p:"+_pair) not in _cache:
                            _cache["p:" +
                                   _pair] = Redis.get_obj(_pair,chain.redis_db, is_pair=True)
                        pair = _cache["p:"+_pair]
                        if not pair:
                            print("ASD")
                        next_token_2 = other_token(pair, next_token_1, _cache)
                        if next_token_2.address not in _base_tokens:
                            continue
                        if pair not in _stack:
                            _stack.append(pair)
                        else:
                            continue
                        stack.append(pair.for_path(next_token_1))
                        if next_token_2 == end:
                            data = {
                                "routes": stack.copy()
                            }
                            actions.append(data)
                            diffrent_lengths[3] += 1
                            count += 1

                        stack.pop()
                        _stack.pop()
                    stack.pop()
                    _stack.pop()
                stack.pop()
                _stack.pop()

            for action in actions:
                Schema.Path(**{
                    "tokens": [start.address, end.address] , "chain":chain, **action})
        except Exception as e:
            logging.exception(e)
        logging.info(f"---graphin--ended--on---{start}--->{end}")
        del _cache
        del actions
        return count, diffrent_lengths
    _token_objs = []
    for _token in _base_tokens:
        _token_objs.append(Redis.get_obj(
            _token,chain.redis_db, is_token=True, _complete=True))

    _futures = []
    with ThreadPoolExecutor(7) as e:
        for A in _token_objs:
            for B in _token_objs:
                _futures.append(e.submit(make, A, B))
    for _future in as_completed(_futures):
        res = _future.result()
        count += res[0]
        for i, _count in res[1].items():
            diffrent_lengths[i] += _count

    logging.info(f'----finished--with-->{count} possibilities')
    logging.info(f'---paths-Count-->{diffrent_lengths}')


def check_doomed_pairs(chain):
    for _pair in Redis.all_pair(doomed=True):
        pair = Redis.get_obj(_pair,chain.redis_db ,is_doomed_pair = True)
        if pair:
            pair.sync()
            can_i_revive = True
            for i in range(len(pair.tokens)):
                _token = Redis.get_obj(pair.tokens[i],chain.redis_db, is_token=True)
                if pair.reserves[i] < int(MINIMUM_RESERVES * 10**_token.decimal):
                    pair.delete()
                    logging.info(f"----shit--pair--removed-->{pair}")
                    can_i_revive = False
                    break
            if can_i_revive:
                pair.undelete()
            

def clean_pairs(chain, _base_tokens=[]):
    _pairs = Redis.all_pair(chain.redis_db)
 
    def iter_over_bases(_token):
        even_more_cleaing = []
        token = Redis.get_obj(_token,chain.redis_db, is_token=True)
        if token:
            logging.info(f'-({_token})------>{len(token.pairs)}')
            for _pair in token.pairs:
                pair = Redis.get_obj(_pair,chain.redis_db, is_pair=True)
                if pair:

                    if pair.tokens[0] in _pairs or pair.tokens[1] in _pairs:
                        logging.error(f'----LP-as-token-found->{pair.address}')
                        pair.delete()
                        logging.info(f"----shit--pair--removed-->{pair}")
                        continue
                    try:
                        pair.sync()
                        can_i_save = True
                        for i in range(len(pair.tokens)):
                            _token = Redis.get_obj(pair.tokens[i],chain.redis_db, is_token=True)
                            if pair.reserves[i] < int(MINIMUM_RESERVES * 10**_token.decimal):
                                pair.delete()
                                # logging.info(f"----shit--pair--removed-->{pair}")
                                can_i_save = False
                                
                                _token = Redis.get_obj(pair.tokens[i],chain.redis_db, is_token=True)
                                if pair.address in _token.pairs:
                                    print('HEY BITCH')

                        if can_i_save:
                            pair.save()
                    except AttributeError as e:
                        logging.exception(e)

                else:
                    even_more_cleaing.append(_pair)
                    # logging.info(f'----Issue--man---->{token}')
        return even_more_cleaing
    # with ThreadPoolExecutor(1) as executor:
    for _token in _base_tokens:
        even_more_cleaing = iter_over_bases(_token)
        token = Redis.get_obj(_token,chain.redis_db , is_token=True)
        if token:
            for emc in even_more_cleaing:
                try:
                    token.pairs.pop(emc)
                except Exception as e:
                    # logging.exception(e)
                    pass
            token.save()
