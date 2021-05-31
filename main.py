import aiohttp
from aiohttp import web

import config
from chatdriver import qqbot
from random_pic import random_pic
from netmeasure import netmeasure


if __name__ == "__main__":
    client_session = aiohttp.ClientSession()
    app = web.Application()

    rp = random_pic()
    nm = netmeasure(client_session, app)

    cmd_handlers = {
        'updimg': rp.update_pic_handler,
        'poi': rp.random_pics_handler,
        'nodelist': nm.nodelist_handler,
        'ipr': nm.resolve_handler,
        'ping': nm.ping_handler,
        'tcping': nm.tcping_handler,
        'mtr': nm.mtr_handler,
        'speed': nm.speed_handler
    }

    bot = qqbot(app)
    bot.reg_cmd_start_char('#$')
    bot.reg_msg_handlers(rp.random_pic_handler)
    bot.reg_cmd_handler_dict(cmd_handlers)
    bot.reg_executor_initializer(netmeasure.add_browser)

    web.run_app(app, host=config.bind_ip, port=config.bind_port)
