# # from pymongo import MongoClient
# # import motor.motor_tornado
# from aiofile import async_open
# import logging
# import asyncio
# import rapidjson
# import os

# DEFAULT_MONGO_CLIENT = motor.motor_tornado.MotorClient(host=os.getenv("MONGO_HOST") ,
#                                    port=os.getenv("MONGO_PORT"),)

# DEFAULT_MONGO_DB = DEFAULT_MONGO_CLIENT.local
# _tokens = DEFAULT_MONGO_DB['tokens']
# _pairs = DEFAULT_MONGO_DB['pairs']
# _dexs = DEFAULT_MONGO_DB['dexs']
# _abi = DEFAULT_MONGO_DB['abi']

# async def populate_mongo(filename=None):
#     '''
#     File Should be like so:
#     tokens :[
#         {
#             name : str
#             address : str
#             decimals : int
#         }
#     ]
#     dexs : [
#         {
#             -> dex detail <-
#             pairs :[
                
#             ]
#         }
#     ]
#     abis :
#         {
#             name : list
#         }
#     '''
#     await _tokens.create_index("address" , unique=True)
    
#     await _pairs.create_index("address" , unique=True)
    
#     await _dexs.create_index("name" , unique=True)
    
#     await _abi.create_index("name" , unique=True)
    
#     if filename:
#         async with async_open(filename) as _f:
#             _data = rapidjson(await _f.read())
#             _tokens = _data["tokens"]
#             await _tokens.insert_many(_tokens)
#             for dex in _data['dexs']:
#                 await _pairs.insert_many(dex['pairs'])
#                 dex.pop('pairs')
#                 await _dexs.insert_one(dex)
#             await _abi.insert_many(_data['abis'])

# async def get_abi(name):
#     try:
#         res_abi = await _abi.find_one({"name" : name})
#         return res_abi['abi']
#     except Exception as e:
#         logging.exception(e)
#         return None 

# async def get_factory(dex_name):
#     try:
#         res_abi = await _dexs.find_one({"name" : name})
#         return res_abi['factory']
#     except Exception as e:
#         logging.exception(e)
#         return None 

# async def get_lp_fee(dex_name):
#     try:
#         res_abi = await _dexs.find_one({"name" : name})
#         return res_abi['lp_fee']
#     except Exception as e:
#         logging.exception(e)
#         return None 
