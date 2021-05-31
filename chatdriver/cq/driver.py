import json
import asyncio

import aiohttp
from aiohttp import web

from chatdriver.cq import event


class driver:
    def __init__(self, app: web.Application):
        app.add_routes([
            web.get('/cq', self.ws_handler)
        ])

        self.task_queue = asyncio.Queue()
        app.on_startup.append(self.app_startup)

        # handlers
        self.message_handlers = []
        self.request_handlers = []
        self.notice_handlers = []

        # ws connection
        self.ws = web.WebSocketResponse()

    def reg_message_handler(self, handler):
        self.message_handlers.append(handler)

    def reg_request_handler(self, handler):
        self.request_handlers.append(handler)

    def reg_notice_handler(self, handler):
        self.notice_handlers.append(handler)

    async def task_gc(self):
        while True:
            await asyncio.sleep(60)
            pending_tasks = list()
            count = 0
            while not self.task_queue.empty():
                task = await self.task_queue.get()
                if task.done():
                    count += 1
                else:
                    pending_tasks.append(task)
            print(f'GC: {count} tasks done, {len(pending_tasks)} pending')
            for t in pending_tasks:
                self.task_queue.put_nowait(t)

    async def app_startup(self, app: web.Application):
        app['cq_task_gc'] = asyncio.create_task(self.task_gc())

    async def ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        # upgrade to websocket connection
        self.ws = web.WebSocketResponse()
        await self.ws.prepare(request)
        # received a message
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                event_data = json.loads(msg.data)
                post_type = event_data.get('post_type')
                if post_type == 'message':
                    # call message handler
                    for handler in self.message_handlers:
                        self.task_queue.put_nowait(asyncio.create_task(handler(event.message_event(event_data))))
                elif post_type == 'request':
                    for handler in self.request_handlers:
                        self.task_queue.put_nowait(asyncio.create_task(handler(event.request_event(event_data))))
                elif post_type == 'notice':
                    for handler in self.notice_handlers:
                        self.task_queue.put_nowait(asyncio.create_task(handler(event.notice_event(event_data))))

        return self.ws

    async def send_private_msg(self, usr_id: str, msg: str):
        await self.ws.send_json({
            'action': 'send_private_msg',
            'params': {
                'user_id': usr_id,
                'message': msg
            }
        })

    async def send_group_msg(self, group_id: str, msg: str):
        await self.ws.send_json({
            'action': 'send_group_msg',
            'params': {
                'group_id': group_id,
                'message': msg
            }
        })

    async def set_group_ban(self, group_id: str, user_id: str, duration: int):
        await self.ws.send_json({
            'action': 'set_group_ban',
            'params': {
                'group_id': group_id,
                'user_id': user_id,
                'duration': duration
            }
        })

    async def del_message(self, message_id: int):
        await self.ws.send_json({
            'action': 'delete_msg',
            'params': {
                'message_id': message_id
            }
        })

    @staticmethod
    def reply(message_id: int, text: str):
        return f'[CQ:reply,id={message_id},text={text}]'

    @staticmethod
    def pic(pic_url: str) -> str:
        return f'[CQ:image,file={pic_url}]'

    @staticmethod
    def at(user_id: str) -> str:
        return f'[CQ:at,qq={user_id}]'
