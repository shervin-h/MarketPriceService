from web3 import Web3
from enum import Enum
import rapidjson as json
import os


FANTOM = 250
BINANCE = 56
ETHEREUM = 1

_SUPPORTED_CHAINES = [FANTOM, BINANCE, ETHEREUM]

_NETWORK_VALUE_ADDRESS = {
    ETHEREUM: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    BINANCE: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    FANTOM: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
}

_NETWORK_VALUE_SYMBOL = {
    ETHEREUM: "ETH",
    BINANCE: "BNB",
    FANTOM: "FTM"
}
_CHAIN_RPC = {
    ETHEREUM: "https://mainnet.infura.io/v3/bb055071bba745488eda95512a6d0035",
    BINANCE: "https://bsc-dataseed.binance.org/",
    FANTOM:  "https://rpcapi.fantom.network/",
}

_CHAIN_REDIS_DB = {
    ETHEREUM: 1,
    BINANCE: 3,
    FANTOM: 2
}
_NETWORK_VALUE_WRAPPED_SYMBOL = {
    ETHEREUM: "WETH",
    BINANCE: "WBNB",
    FANTOM: "WFTM"
}
_NETWORK_VALUE_WRAPPED_ADDRESS = {
    ETHEREUM: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    BINANCE: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    FANTOM: "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83"
}


_WEB3_CLIENTS = {
    ETHEREUM: Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/bb055071bba745488eda95512a6d0035")),
    BINANCE: Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/")),
    FANTOM:  Web3(Web3.HTTPProvider("https://rpc.ftm.tools/")),
}

class ETH_ROUTERS(Enum):
    Paraswap = Web3.toChecksumAddress("0xb70Bc06D2c9Bf03b3373799606dc7d39346c06B3")
    OneInch = Web3.toChecksumAddress("0x11111112542d85b3ef69ae05771c2dccff4faa26")
    Totle = Web3.toChecksumAddress("0x74758AcFcE059f503a7E6B0fC2c8737600f9F2c4")  # * not so sure
    ZeroX = Web3.toChecksumAddress("0xdef1c0ded9bec7f1a1670819833240f027b25eff")
    DexAg = Web3.toChecksumAddress("0xCcaF8533b6822a6c17b1059dda13C168E75544a4")

'''
David's

class ETH_ROUTERS(Enum):
    Paraswap = "0x1bD435F3C054b6e901B7b108a0ab7617C808677b"
    OneInch = "0x11111112542d85b3ef69ae05771c2dccff4faa26"
    _Totle1 = "0x74758AcFcE059f503a7E6B0fC2c8737600f9F2c4"  # * not so sure
    ZeroX = "0xdef1c0ded9bec7f1a1670819833240f027b25eff"
    DexAg = "0x745DAA146934B27e3f0b6bff1a6e36b9B90fb131"
    Totle = "0x7113Dd99c79afF93d54CFa4B2885576535A132dE"
'''

class Aggregator(Enum):
    _1inch = "1inch"
    dexag = "dexag"
    paraswap = "paraswap"
    _0x = "0x"
    totle = "totle"
    ALL = "all"

    @ property
    def routers(self):
        if self == Aggregator._1inch:
            return ETH_ROUTERS.OneInch.value
        if self == Aggregator.dexag:
            return ETH_ROUTERS.DexAg.value
        if self == Aggregator.paraswap:
            return ETH_ROUTERS.Paraswap.value
        if self == Aggregator._0x:
            return ETH_ROUTERS.ZeroX.value
        if self == Aggregator.totle:
            return ETH_ROUTERS.Totle.value

class ETH_ROUTER(Enum):
    MAIN = ""   
    ABI = []

class BSC_ROUTER(Enum):
    MAIN = ""
    ABI = []

class FTM_ROUTER(Enum):
    MAIN = "0xB0251D54A6E3E89d8abceA63DF76cdE97295a382"
    ABI = []


# _TOKEN_LIST = json.load(open(os.getenv("TOKENS_LIST_DIR")))
# _DEX_LIST = json.load(open(os.getenv("ADDRESS_BOOK_DIR")))



class Chain(Enum):

    FANTOM = 250
    BINANCE = 56
    ETHEREUM = 1

    @ property
    def routers(self):
        if self == Chain.FANTOM:
            return FTM_ROUTER
        if self == Chain.BINANCE:
            return BSC_ROUTER
        if self == Chain.ETHEREUM:
            return ETH_ROUTERS

    @ property
    def router_address(self):
        if self == Chain.FANTOM:
            return FTM_ROUTER.MAIN.value
        if self == Chain.BINANCE:
            return BSC_ROUTER.MAIN.value
        if self == Chain.ETHEREUM:
            return ETH_ROUTER.MAIN.value
            
    @ property
    def router_abi(self):
        if self == Chain.FANTOM:
            return FTM_ROUTER.ABI.value
        if self == Chain.BINANCE:
            return BSC_ROUTER.ABI.value
        if self == Chain.ETHEREUM:
            return ETH_ROUTER.ABI.value

    @ property
    def rpc(self):
        return _CHAIN_RPC[self.value]

    @ property
    def redis_db(self):
        return _CHAIN_REDIS_DB[self.value]

    @ property
    def wrapped_token(self):
        return _NETWORK_VALUE_WRAPPED_ADDRESS[self.value]

    @ property
    def wrapped_token_symbol(self):
        return _NETWORK_VALUE_WRAPPED_SYMBOL[self.value]

    @ property
    def w3(self):
        return _WEB3_CLIENTS[self.value]

    @ property
    def value_token_address(self):
        return _NETWORK_VALUE_ADDRESS[self.value]

    @ property
    def value_token_symbol(self):
        return _NETWORK_VALUE_SYMBOL[self.value]

    @ property
    def tokens(self):
        return _TOKEN_LIST.get(str(self.value))

    @ property
    def dexs(self):
        return _DEX_LIST.get(str(self.value))

    @ property
    def _id(self):
        return self.value

    @ classmethod
    def is_chain_registered(cls, chainId):
        return chainId in _SUPPORTED_CHAINES

    @ classmethod
    def chain_dbs(cls):
        return _CHAIN_REDIS_DB.values()

    @ classmethod
    def chains(cls):
        return [cls(value) for value in _SUPPORTED_CHAINES]
