import os
import asyncio
import aioredis
from requests_ws import verify_inbox
import uvloop
import socket
import uuid
import contextvars
from fastapi import FastAPI, Depends, Request
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocket, WebSocketDisconnect
from core.core import settings
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from aioredis.errors import ConnectionClosedError as ServerConnectionClosedError
from utils import get_current_user


REDIS_HOST = 'localhost'
REDIS_PORT = 6379
XREAD_TIMEOUT = 0
XREAD_COUNT = 100
NUM_PREVIOUS = 30
STREAM_MAX_LEN = 1000
ALLOWED_inboxS = ['chat1', 'chat2', 'chat3', '1-2', '1-3', 'lab', '1-4', '1-5', '1-7', '2-4']
PORT = 9080
HOST = "0.0.0.0"


# Context Vars
cvar_client_addr = contextvars.ContextVar('client_addr', default=None)
cvar_chat_info = contextvars.ContextVar('chat_info', default=None)
cvar_tenant = contextvars.ContextVar('tenant', default=None)
cvar_redis = contextvars.ContextVar('redis', default=None)


class CustomHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_value='Example'):
        print('__init__')
        super().__init__(app)
        self.header_value = header_value

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Custom'] = self.header_value
        return response


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
app = FastAPI()
app.add_middleware(CustomHeaderMiddleware)
templates = Jinja2Templates(directory="templates")
app = FastAPI(title=settings.PROJECT_NAME)


async def get_redis_pool():
    try:
        pool = await aioredis.create_redis_pool(
            (REDIS_HOST, REDIS_PORT), encoding='utf-8')
        return pool
    except ConnectionRefusedError as e:
        print('cannot connect to redis on:', REDIS_HOST, REDIS_PORT)
        return None


async def ws_send(websocket: WebSocket, chat_info: dict): 
    """
    wait for new items on chat stream and
    send data from server to client over a WebSocket

    :param websocket:
    :type websocket:
    :param chat_info:
    :type chat_info:
    """
    pool = await get_redis_pool()
    latest_ids = ['$']
    ws_connected = True
    first_run = True
    while pool and ws_connected:
        try:
            if first_run:
                # fetch some previous chat history
                events = await pool.xrevrange(
                    stream=cvar_tenant.get() + ":stream",
                    count=NUM_PREVIOUS,
                    start='+',
                    stop='-'
                )
                first_run = False
                events.reverse()
                for e_id, e in events:
                    e['e_id'] = e_id
                    await websocket.send_json(e)
            else:
                events = await pool.xread(
                    streams=[cvar_tenant.get() + ":stream"],
                    count=XREAD_COUNT,
                    timeout=XREAD_TIMEOUT,
                    latest_ids=latest_ids
                )
                for _, e_id, e in events:
                    e['e_id'] = e_id
                    await websocket.send_json(e)
                    latest_ids = [e_id]
            #print('################contextvar ', cvar_tenant.get())
        except ConnectionClosedError:
            ws_connected = False

        except ConnectionClosedOK:
            ws_connected = False

        except ServerConnectionClosedError:
            print('redis server connection closed')
            return
    pool.close()


async def ws_recieve(websocket: WebSocket, chat_info: dict):
    """
    receive json data from client over a WebSocket, add messages onto the
    associated chat stream

    :param websocket:
    :type websocket:
    :param chat_info:
    :type chat_info:
    """

    ws_connected = False
    pool = await get_redis_pool()
    added = await add_inbox_user(chat_info, pool)

    if added:
        await announce(pool, chat_info, 'connected')
        ws_connected = True
    else:
        print('duplicate user error')

    while ws_connected:
        try:
            data = await websocket.receive_json()
            #print(data)
            if type(data) == list and len(data):
                data = data[0]
            fields = {
                'uname': chat_info['username'],
                'msg': data['msg'],
                'type': 'txt',
                'inbox': chat_info['inbox_hash']
            }
            await pool.xadd(stream=cvar_tenant.get() + ":stream",
                            fields=fields,
                            message_id=b'*',
                            max_len=STREAM_MAX_LEN)
            #print('################contextvar ', cvar_tenant.get())
        except WebSocketDisconnect:
            await remove_inbox_user(chat_info, pool)
            await announce(pool, chat_info, 'disconnected')
            ws_connected = False

        except ServerConnectionClosedError:
            print('redis server connection closed')
            return

        except ConnectionRefusedError:
            print('redis server connection closed')
            return

    pool.close()


async def add_inbox_user(chat_info: dict, pool):
    #added = await pool.sadd(chat_info['inbox']+":users", chat_info['username'])
    added = await pool.sadd(cvar_tenant.get()+":users", cvar_chat_info.get()['username'])
    return added


async def remove_inbox_user(chat_info: dict, pool):
    # removed = await pool.srem(chat_info['inbox_hash']+":users", chat_info['username'])
    # print('REMOVED')
    removed = await pool.srem(cvar_tenant.get()+":users", cvar_chat_info.get()['username'])
    return removed


async def inbox_users(chat_info: dict, pool):
    #users = await pool.smembers(chat_info['inbox']+":users")
    users = await pool.smembers(cvar_tenant.get()+":users")
    print(len(users))
    return users


async def announce(pool, chat_info: dict, action: str):
    """ 
    1. Gets the list of users in the chat
    2. Creates a message with the action and the users in the chat
    3. Adds the message to the chat stream 
    """
    users = await inbox_users(chat_info, pool)
    fields = {
        'msg': f"{chat_info['username']} {action}",
        'action': action,
        'type': 'announcement',
        'users': ", ".join(users),
        'inbox': chat_info['inbox_hash']
    }
    print(fields)

    # TODO make user disconnect or SOMETHING


    # await pool.xadd(stream=cvar_tenant.get() + ":stream",
    #                 fields=fields,
    #                 message_id=b'*',
    #                 max_len=STREAM_MAX_LEN)


async def chat_info_vars(inbox: str = None, token: str = None):
    """
    The code above does the following:
    1. Gets the current user from the token
    2. Gets the username and user_id from the user
    3. Gets the inbox_hash from the URL parameter
    4. Returns a dictionary with the below information 
    """
    user = get_current_user(token)
    if not user:
        return None
    username = user['username']
    user_id = user['user_id']

    if user is None or inbox is None:
        return False
   
    return {"username": username, 
            "user_id": user_id ,
            "inbox_hash": inbox,
            "token": token
             }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket,
                             chat_info: dict = Depends(chat_info_vars)):
    #print('request.hostname', websocket.url.hostname)
    tenant_id = ":".join([websocket.url.hostname.replace('.', '_'),
                           chat_info['inbox_hash']])
    # print('tenant_id', tenant_id)
    cvar_tenant.set(tenant_id)
    cvar_chat_info.set(chat_info)
    


    # check the user is allowed into the chat inbox
    verified = await verify_user_for_inbox(chat_info)
    # open connection
    await websocket.accept()
    if not verified:
        print('failed verification')
         
        await websocket.close()
    else:

        # spin up coro's for inbound and outbound communication over the socket
        await asyncio.gather(ws_recieve(websocket, chat_info),
                             ws_send(websocket, chat_info))


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("chat.html",
                                      {"request": request,                     
                                       "port": PORT})


async def verify_user_for_inbox(chat_info): 
    verified = True
    pool = await get_redis_pool()
    if not pool:
        print('Redis connection failure')
        return False

    print("CVAR chatinfo", cvar_chat_info.get())
    already_exists = await pool.sismember(cvar_tenant.get()+":users", cvar_chat_info.get()['username'])

    if already_exists:
        print(chat_info['username'] +' user already_exists in ' + chat_info['inbox_hash'])
        verified = False
    
    # check the user is allowed into the chat inbox
    if not verify_inbox(chat_info['inbox_hash'], chat_info['token']):
        print('could not verify server side')
        return False

    pool.close()
    return verified


@app.on_event("startup")
async def handle_startup():
    try:
        pool = await aioredis.create_redis_pool(
            (REDIS_HOST, REDIS_PORT), encoding='utf-8', maxsize=20)
        cvar_redis.set(pool)
        print("Connected to Redis on ", REDIS_HOST, REDIS_PORT)
    except ConnectionRefusedError as e:
        print('cannot connect to redis on:', REDIS_HOST, REDIS_PORT)
        return


@app.on_event("shutdown")
async def handle_shutdown():
    redis = cvar_redis.get()
    redis.close()
    await redis.wait_closed()
    print("closed connection Redis on ", REDIS_HOST, REDIS_PORT)


if __name__ == "__main__":
    import uvicorn
    print(dir(app))
    print(app.url_path_for('websocket_endpoint'))
    uvicorn.run('chat_ws:app', host=HOST, port=PORT, log_level='info', reload=True)# uds='uvicorn.sock') #, uds='uvicorn.sock')
