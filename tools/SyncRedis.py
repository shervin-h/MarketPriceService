from Network import Chain
# from Schema import Token
from . import Schema
import rapidjson as json
from enum import Enum
import logging
import pickle
import redis
import time
import os

'''
TODO
- Add Redis pipeline :) 
- Add addressbook ( instead of using addresses for keys use indecies and a seperate namespace for indeces:address)
'''

UPDATE_STATUS = "update-status"
UPDATE_TIME_OUT = 1 * 3600
ADDRESS_PREFIX = "ad2I:"
DEX_PREFIX = "dex:"
PAIR_PREFIX = "pair:"
DOOMED_PAIRS_PREFIX = "dpairs:"
PATH_PREFIX = "path:"
TOKEN_PREFIX = "token:"
PATH_INDEX_KEY = "pathIndex"
PATH_TIMEOUT = 5 * 60 * 60
TRX_DEADLINE = 25 * 60
TRX_PRIFIX = "trx_data:"
RPC_LIMIT_PREFIX = "rpc_limit:"
RPC_LIMIT = 10_000
RPC_LIMIT_TIMEOUT = 5 * 60
MAX_WORKERS = 30
MAX_RETRIES = 5
CHECK_CONNECTION_COUNT = 1000000

global REQUEST_COUNT
REQUEST_COUNT = None


class UpdateStatus(Enum):
    RUNNING = "running"
    FINISHED = "finished"
    NULL = "null"


BAD_ADDRESS = [
    # USDT
    "0xb62aFA01a640899828328Be912a1564beA361b8E",
    "0x1B27A9dE6a775F98aaA5B90B62a4e2A0B84DbDd9",
    # ETH
    "0xC9cAc05F770384F18a960e2D2365650d7f182b36",
]

global _REDIS_CLIENTS
global _LAST_USED_DB
'''
# ! DB Zero is never allocated :)
'''

_REDIS_CLIENTS = {
    0: None,
}
_LAST_USED_DB = 0


def RedisClient(_db=None, no_decode=False):
    global _REDIS_CLIENTS
    global REQUEST_COUNT
    global _LAST_USED_DB
    if no_decode:
        return redis.Redis(os.getenv('REDIS_HOST'), os.getenv(
            'REDIS_PORT'), _db or _LAST_USED_DB)
    if _db:
        _REDIS_CLIENT = _REDIS_CLIENTS.get(_db)
        if not _REDIS_CLIENT:
            data = (os.getenv('REDIS_HOST'), os.getenv(
                'REDIS_PORT'), _db or _LAST_USED_DB)
            _REDIS_CLIENT = redis.Redis(os.getenv('REDIS_HOST'), os.getenv(
                'REDIS_PORT'), _db or _LAST_USED_DB, decode_responses=True)

            _REDIS_CLIENTS.update({_db: _REDIS_CLIENT})

        if _db:
            _LAST_USED_DB = _db

        retry_interval = 0.1
        if REQUEST_COUNT == None or CHECK_CONNECTION_COUNT < REQUEST_COUNT:
            REQUEST_COUNT = 0
            for i in range(MAX_RETRIES):
                try:
                    _REDIS_CLIENT.set("connection", "up")
                    assert _REDIS_CLIENT.get(
                        "connection") == "up", "Fauly redis Connection"
                    break
                except Exception as e:
                    logging.exception(e)
                    logging.error("Issue with redis connection")
                    time.sleep(retry_interval)
                    retry_interval *= 3
                    continue

            assert _REDIS_CLIENT.get(
                "connection") == "up", 'Where is Redis X_X'
        REQUEST_COUNT += 1
        return _REDIS_CLIENT


def remove_badly_added_pair(factory_address, db, index):
    '''
    Be really careful in using this function
    Cant cause near to infite loop X_X
    '''
    try:
        cl = RedisClient(db)
        _key = f"{DEX_PREFIX}{factory_address}"
        cl.lrem(_key, 0, index)
    except Exception as e:
        logging.exception(e)


def dex_pairs_retrival(factory_address, db, index=-1, cl=None):
    '''
    Stores a list of retrived indexes :) in redis
    '''
    try:
        if not cl:
            cl = RedisClient(db)
        _key = f"{DEX_PREFIX}{factory_address}"
        _count = cl.llen(_key) or 0
        if isinstance(index, str):
            cl.lpush(_key, index)
            return _count + 1
        if index >= 0:
            # ! in redis we have a problem which is array of indeces are [0,0,0,0,0,0,0, ...] ????
            cl.lpush(_key, index)
            return _count + 1
        else:
            return cl.lrange(_key, 0, _count)
    except Exception as e:
        logging.exception(e)
        return 0


def rpc_request(chain, count=1):
    '''
    BSC Has a 10k /5 min request limmit X_X
    in case limit is resolved set RPC_LIMIT = 0    TY :)
    '''
    db = chain.redis_db
    rpc_node = chain.rpc
    if RPC_LIMIT:
        cl = RedisClient(db)
        _key = f"{RPC_LIMIT_PREFIX}{rpc_node}"
        _call_count = int(cl.get(_key) or 0)
        if _call_count > RPC_LIMIT:
            return cl.ttl(_key)
        else:
            cl.set(_key, _call_count + count, ex=RPC_LIMIT_TIMEOUT)
            return 0
    else:
        return 0


def all_paths(request):

    cl = RedisClient(request._chain.redis_db)
    _key = f"{PATH_PREFIX}{request.fromToken.address}:{request.toToken.address}:*"
    keys = cl.keys(_key)
    res = []
    for _p in cl.mget(keys):
        res.append(json.loads(_p))
    return res


def paths_count(db,):
    cl = RedisClient(db)
    return len(cl.keys(f'{PATH_PREFIX}*'))


def all_tokens_address(db):
    cl = RedisClient(db)
    return cl.keys(f'{TOKEN_PREFIX}*')


def all_tokens(db,):
    cl = RedisClient(db)
    keys = cl.keys(f'{TOKEN_PREFIX}*')
    return cl.mget(keys)


def all_pair_address(db):
    cl = RedisClient(db)
    prefix = DOOMED_PAIRS_PREFIX
    dkeys = cl.keys(f'{prefix}*')
    prefix = PAIR_PREFIX
    keys = cl.keys(f'{prefix}*')
    return {"good": keys, "bad": dkeys}


def all_pair_count(db):

    cl = RedisClient(db)
    prefix = DOOMED_PAIRS_PREFIX
    dkeys = cl.keys(f'{prefix}*')
    prefix = PAIR_PREFIX
    keys = cl.keys(f'{prefix}*')
    return {"good": len(keys), "bad": len(dkeys)}


def all_pair(db, doomed=False):
    cl = RedisClient(db)
    if doomed:
        prefix = DOOMED_PAIRS_PREFIX
    else:
        prefix = PAIR_PREFIX
    keys = cl.keys(f'{prefix}*')
    _res = []
    for key in keys:
        _res.append(key[len(prefix)-1:])
    return _res


def save_transaction(request, data):
    cl = RedisClient(request._chain.redis_db, no_decode=True)
    return cl.set(TRX_PRIFIX + request.walletAddress,  pickle.dumps(data), TRX_DEADLINE)


def get_transaction(request):
    cl = RedisClient(request._chain.redis_db, no_decode=True)
    try:
        return pickle.loads(cl.get(TRX_PRIFIX + request.walletAddress))
    except:
        return None


def pending_transactions_count(db):
    cl = RedisClient(db)
    return cl.keys(TRX_PRIFIX + "*")


def get_obj_by_name(name, chain: Chain, from_file=True, is_token=False):
    db = chain.redis_db
    if is_token:
        if from_file:
            base_tokens = {}
            for token in chain.tokens.values():
                if token['symbol'] == name:
                    obj = Schema.Token(**token)
                    return obj

        else:
            for _token in all_tokens(db):
                token = Schema.Token(**json.loads(_token))
                if token.address in BAD_ADDRESS:
                    continue
                if token.symbol.upper() == name.upper():
                    logging.info(token)
                    return token

def get_obj_all_tokens(chain: Chain):
    db = chain.redis_db
    tkns = []
    for token in chain.tokens.values():
        obj = Schema.Token(**token)
        tkns.append(obj)
    return tkns


def get_obj(key, db, is_token=False, is_pair=False,
            is_doomed_pair=False, is_path=False,
            cl=None, _complete=True,
            _with_prefix=False):
    '''
    Gets key and return obj based on keys type :)
    has a _complete parameter -> if True will populate obj with pairs and other longer stuff :) lookinto schema and you'll understand 
    For path retrival give me a dict of {
        token0address,
        token1address, 
        index
    }
    '''
    if not cl:
        cl = RedisClient(db)
    if is_token:
        if not _with_prefix:
            _k = f'{TOKEN_PREFIX}{key}'
        else:
            _k = key
        _detail = json.loads(cl.get(_k) or "{}")
        if _detail:
            return Schema.Token(**_detail, save=False)
    if is_pair or is_doomed_pair:
        if is_pair:
            _k = f'{PAIR_PREFIX}{key}'
        if is_doomed_pair:
            _k = f'{DOOMED_PAIRS_PREFIX}{key}'

        _detail = json.loads(cl.get(_k) or "{}")
        if _detail:
            return Schema.DEX_TYPE(_detail['type']).create(_detail)
    if is_path:
        _detail = json.loads(cl.get(_k) or "{}")
        if _detail:
            _k = f'{PATH_PREFIX}{Schema.Path.key_creator(**key)}'
            return Schema.Path(**_detail, save=False)
    return None


def update(self, db, cl=None):

    if not cl:
        cl = RedisClient(db)
    if isinstance(self, Schema.Token):
        key = TOKEN_PREFIX + self.address
    if isinstance(self, Schema.Pair):
        key = PAIR_PREFIX + self.address
    if isinstance(self, Schema.Path):
        key = PATH_PREFIX + self.key
    try:
        data = self.json()
        cl.set(key, data)
        return True
    except Exception as e:
        logging.exception(e)
        return False


def doom_it(key, db, cl=None, is_pair=False):
    '''
    # ! Stay away from these pair cuase the tokens attached to these pairs are non exsistance :)
    # ! So If you want to revive em try to add them to token.pairs :)
    '''
    if not cl:
        cl = RedisClient(db)
    if is_pair:
        try:
            ini_key = PAIR_PREFIX + key
            after_key = DOOMED_PAIRS_PREFIX + key
            data = cl.get(ini_key)
            cl.delete(ini_key)
            cl.set(after_key, data)
            return True
        except Exception as e:
            if cl.get(DOOMED_PAIRS_PREFIX + key):
                return True
            else:
                print("HOLLY SHIT ")
                # logging.exception(e)


def undoom_it(key, db, cl=None, is_pair=False):
    '''
    # ! MAKE SURE TO CALL ADD PAIR on TOKEN OBJ   
    '''
    if not cl:
        cl = RedisClient(db)
    if is_pair:
        ini_key = DOOMED_PAIRS_PREFIX + key
        after_key = PAIR_PREFIX + key
        data = cl.get(ini_key)
        cl.delete(ini_key)
        cl.set(after_key, data)
        return True


def get_token_keys(db):
    return RedisClient(_db=db).keys(f"{TOKEN_PREFIX}*")


def update_status(db, new_state=None):
    cl = RedisClient(db)
    r = cl.get(UPDATE_STATUS)

    if not r and not new_state:
        cl.set(UPDATE_STATUS, UpdateStatus.NULL.value, ex=UPDATE_TIME_OUT)
        return UpdateStatus.NULL
    elif r and not new_state:
        return UpdateStatus(r)
    elif r and new_state:
        cl.set(UPDATE_STATUS, new_state.value, ex=UPDATE_TIME_OUT)
        return new_state
