import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor

from aiohttp import web

from . import cq, event


class msg_session:
    def __init__(self, id: str, bot, driver: cq.driver):
        self.id = id
        self.bot = bot
        self.driver = driver
        self.executor = bot.executor
        self.var = dict()

    async def send_msg(self, message: str):
        pass

    async def del_msg(self, event: event.msg_event):
        await self.driver.del_message(event.attrs.get('-qq-msg-id'))

    # send picture
    def picstr(self, pic_url: str):
        return self.driver.pic(pic_url)


class group_session(msg_session):
    def __init__(self, group_id: str, bot, driver: cq.driver):
        super().__init__(group_id, bot, driver)

    async def send_msg(self, message: str):
        await self.driver.send_group_msg(self.id, message)

    # @somebody
    def atstr(self, user_id: str):
        return self.driver.at(user_id)

    # reply somebody
    def replystr(self, event: event.msg_event, message: str):
        return self.driver.reply(event.attrs.get('-qq-msg-id'), message)


class private_session(msg_session):
    def __init__(self, user_id: str, bot, driver: cq.driver):
        super().__init__(user_id, bot, driver)

    async def send_msg(self, message):
        await self.driver.send_private_msg(self.id, message)


class qqbot:
    def __init__(self, app: web.Application):
        # go-cqhttp chatdriver
        self.cqdriver = cq.driver(app)
        self.cqdriver.reg_message_handler(self.msg_handler)

        self.var = dict()
        app.on_shutdown.append(self.save_vars)

        # process pool initializer list
        self.ei = list()
        # process pool
        self.executor = ProcessPoolExecutor(max_workers=4, initializer=qqbot.executor_initializer, initargs=(self.ei, ))

        self.cmd_start_char = ''

        # data-struct that store group sessions
        # {
        #     'group_id': session
        # }
        self.group_sessions = dict()
        # data-struct that store private sessions
        # {
        #     'user_id': session
        # }
        self.private_sessions = dict()
        # data-struct that store command handlers
        # {
        #     'command name': command handler,
        # }
        self.cmd_handlers = dict()
        # data-struct that store message handlers
        # [handler, handler]
        self.msg_handlers = list()

        # read saved session vars
        if os.path.exists('session_data.json'):
            with open('session_data.json', 'r', encoding='utf-8') as fp:
                var_json = json.load(fp)
                self.var = var_json.get('application')
                if self.var is None:
                    self.var = dict()
                for key, item in var_json.get('group').items():
                    _session = self.get_group_session(str(key))
                    _session.var = item

                for key, item in var_json.get('private').items():
                    _session = self.get_private_session(str(key))
                    _session.var = item

    async def save_vars(self, app: web.Application):
        # store vars
        _vars = {
            'application': self.var,
            'group': {},
            'private': {}
        }

        for key, item in self.group_sessions.items():
            _vars['group'][key] = item.var
        for key, item in self.private_sessions.items():
            _vars['private'][key] = item.var

        if os.path.exists('session_data.json'):
            os.remove('session_data.json')
        with open('session_data.json', 'w', encoding='utf-8') as fp:
            json.dump(_vars, fp)

    async def msg_handler(self, msg_event: event.msg_event):
        # check message type and create session
        if msg_event.msg_type == event.msg_type.GROUP_MSG:
            _session = self.get_group_session(msg_event.group_id)
        elif msg_event.msg_type == event.msg_type.PRIVATE_MSG:
            _session = self.get_private_session(msg_event.user_id)
        else:
            return

        # call message handler
        for h in self.msg_handlers:
            self.cqdriver.task_queue.put_nowait(asyncio.create_task(h(msg_event, _session)))

        # call command handler
        if msg_event.message[0] in self.cmd_start_char:
            cmd = msg_event.message.split(' ')[0]
            cmd = cmd[1:]
            cmd_handler = self.cmd_handlers.get(cmd)
            if cmd_handler is not None:
                self.cqdriver.task_queue.put_nowait(asyncio.create_task(cmd_handler(msg_event, _session)))

    @staticmethod
    def executor_initializer(func_args_tuple):
        for function, args in func_args_tuple:
            function(*args)

    def get_group_session(self, id: str):
        _session = self.group_sessions.get(id)
        if _session is None:
            _session = group_session(id, self, self.cqdriver)
            self.group_sessions[id] = _session
        return _session

    def get_private_session(self, id: str):
        _session = self.private_sessions.get(id)
        if _session is None:
            _session = private_session(id, self, self.cqdriver)
            self.private_sessions[id] = _session
        return _session

    def reg_executor_initializer(self, function, *args):
        self.ei.append((function, args))

    def reg_cmd_handler(self, command: str, handler):
        self.cmd_handlers[command] = handler

    def reg_cmd_handler_dict(self, ch: dict):
        self.cmd_handlers.update(ch)

    def reg_msg_handlers(self, *args):
        for handler in args:
            self.msg_handlers.append(handler)

    def reg_cmd_start_char(self, c: str):
        self.cmd_start_char += c


if __name__ == "__main__":
    async def test_handler(msg_event, session):
        await session.send_msg(msg_event.message)

    app = web.Application()
    b = qqbot(app)
    b.reg_cmd_start_char('#$')
    b.reg_cmd_handler('r', test_handler)
    web.run_app(app, host='127.0.0.1', port=4130)
