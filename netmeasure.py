import asyncio
import os
import random
import hmac
import json
import statistics
import struct
import time
from itertools import zip_longest

import aiohttp
from aiohttp import web
from aiofile import async_open
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from config import netmeasure_servers, netmeasure_ws_key, bind_ip, bind_port
import argumentparser


class nm_serv:
    def __init__(self):
        self.RESOLVE = None
        self.PING = None
        self.TCPING = None
        self.MTR = None
        self.SPEED = None

    async def send_request(self, req_type: str or int, data: dict) -> dict:
        pass

    async def resolve(
            self,
            address: str,
            family: int,
            wait: str
    ) -> dict:
        data = {
            'address': address,
            'family': family,
            'wait': wait,
            'stamp': int(time.time()),
            'nonce': random.randint(0, 4294967296)
        }
        return await self.send_request(self.RESOLVE, data)

    async def ping(
            self,
            address: str,
            family: int,
            wait: int,
            interval: int,
            times: int
    ) -> dict:
        data = {
                'address': address,
                'family': family,
                'wait': wait,
                'interval': interval,
                'times': times,
                'stamp': int(time.time()),
                'nonce': random.randint(0, 4294967296)
        }
        return await self.send_request(self.PING, data)

    async def tcping(
            self,
            address: str,
            family: int,
            port: int,
            wait: int,
            interval: int,
            times: int
    ) -> dict:
        data = {
            'address': address,
            'family': family,
            'port': port,
            'wait': wait,
            'interval': interval,
            'times': times,
            'stamp': int(time.time()),
            'nonce': random.randint(0, 4294967296)
        }
        return await self.send_request(self.TCPING, data)

    async def mtr(
            self,
            address: str,
            family: int,
            wait: int,
            interval: int,
            times: int,
            max_hop: int,
            rdns: bool
    ) -> dict:
        data = {
            'address': address,
            'family': family,
            'wait': wait,
            'interval': interval,
            'times': times,
            'max_hop': max_hop,
            'rdns': rdns,
            'stamp': int(time.time()),
            'nonce': random.randint(0, 4294967296)
        }
        return await self.send_request(self.MTR, data)

    async def speed(
            self,
            address: str,
            family: int,
            wait: int,
            span: int,
            interval: int
    ) -> dict:
        data = {
            'url': address,
            'family': family,
            'wait': wait,
            'span': span,
            'interval': interval,
            'stamp': int(time.time()),
            'nonce': random.randint(0, 4294967296)
        }
        return await self.send_request(self.SPEED, data)


class nm_serv_http(nm_serv):
    def __init__(
            self,
            session: aiohttp.ClientSession,
            name: str,
            host: str,
            key: str,
            description: str
    ):
        super().__init__()
        self.session = session
        self.name = name
        self.host = host
        self.key = bytes(key, encoding='utf-8')
        self.description = description

        self.RESOLVE = '/api/resolve'
        self.PING = '/api/ping'
        self.TCPING = '/api/tcping'
        self.MTR = '/api/mtr'
        self.SPEED = '/api/speed'

    def __str__(self) -> str:
        return f'{self.description} = {self.name}'

    async def send_request(self, req_type: str, data: dict) -> dict:
        data_text = json.dumps(data)
        sign = hmac.new(self.key, data_text.encode('utf-8'), digestmod='sha256').hexdigest()
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'X-Signature': sign
        }
        try:
            async with self.session.post(self.host + req_type, headers=headers, data=data_text) as p:
                if p.status == 200:
                    return json.loads(await p.text())
        except:
            pass


class nm_serv_ws(nm_serv):
    def __init__(self, ws: web.WebSocketResponse, name: str):
        super().__init__()
        self.ws = ws
        self.name = name
        self.requests = dict()

        self.RESOLVE = 0
        self.PING = 1
        self.TCPING = 2
        self.MTR = 3
        self.SPEED = 4

    def __str__(self) -> str:
        return f'{self.name}'

    def __del__(self):
        del self.requests

    async def send_request(self, req_type: int, data: dict) -> dict:
        _id = random.randint(0, 4294967296)
        event = asyncio.Event()
        self.requests[_id] = {
            'event': event
        }
        data_bytes = json.dumps({
            'id': _id,
            'request': data
        }).encode('utf-8')
        try:
            await self.ws.send_bytes(
                struct.pack('!I', req_type) +
                struct.pack('!I', len(data_bytes)) +
                data_bytes
            )
            await asyncio.wait_for(event.wait(), 300)
        finally:
            return self.requests.pop(_id).get('response')


class nm_ws_manager:
    def __init__(
            self,
            key: str,
            app: web.Application,
    ):
        self.key = key
        self.app = app
        self.app.add_routes([
            web.get('/netmeasure', self.main_handler)
        ])
        self.api_servers = dict()
        self.nonce_last = None

    async def main_handler(self, request: web.Request) -> web.WebSocketResponse or None:
        # check header
        ident = request.headers.get('X-Identifier')
        sign = request.headers.get('X-Signature')
        # no these headers
        if (ident is None) or (sign is None):
            # close connection
            return

        ident_sign = hmac.new(bytes(self.key, encoding='utf-8'), ident.encode('utf-8'), digestmod="sha256").hexdigest()
        # wrong sign
        if ident_sign != sign:
            return

        ident_l = ident.split('.')

        # same nonce
        if ident_l[2] == self.nonce_last:
            return
        # wrong time
        if int(ident_l[1], base=16) - int(time.time()) > 3:
            return

        api_name = ident_l[0].upper()
        ws = None
        try:
            ws = web.WebSocketResponse()
            await ws.prepare(request)

            api_server = nm_serv_ws(ws, api_name)
            self.api_servers[api_name] = api_server
            print(f'ws api: {api_name} connected')
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    rdata = json.loads(msg.data[8:])
                    try:
                        request_id = rdata['id']
                        request = api_server.requests[request_id]
                        request['response'] = rdata
                        request.get('event').set()
                    except:
                        pass
        except Exception as e:
            print(str(e))
        finally:
            print(f'lose connection from ws api: {api_name}')
            del self.api_servers[api_name]
            return ws


class netmeasure:
    def __init__(self, session: aiohttp.ClientSession, app: web.Application):
        self.session = session
        self.app = app
        self.api_servers_http = dict()
        for s in netmeasure_servers:
            self.api_servers_http[s[0].upper()] = nm_serv_http(session, s[0].upper(), s[1], s[2], s[3])

        self.api_serv_ws_mgr = nm_ws_manager(netmeasure_ws_key, app)
        self.api_servers_ws = self.api_serv_ws_mgr.api_servers

        # mtr screenshot path
        self.app.add_routes([
            web.static('/netmeasurestatic', 'static/'),
            web.static('/netmeasuretmp', 'tmp/')
        ])

        self.resolve_parse = argumentparser.ArgumentParser(
            prog='#ipr',
            description='resolve ip address',
            allow_abbrev=False,
            add_help=False,
            exit_on_error=False
        )
        self._add_resolve_argument()

        self.ping_parse = argumentparser.ArgumentParser(
            prog='#ping',
            description='ping',
            allow_abbrev=False,
            add_help=False,
            exit_on_error=False
        )
        self._add_ping_argument()

        self.mtr_parse = argumentparser.ArgumentParser(
            prog='#mtr',
            description='trace route',
            allow_abbrev=False,
            add_help=False,
            exit_on_error=False
        )
        self._add_mtr_argument()

        self.tcping_parse = argumentparser.ArgumentParser(
            prog='#tcping',
            description='tcping',
            allow_abbrev=False,
            add_help=False,
            exit_on_error=False
        )
        self._add_tcping_argument()

        self.speed_parse = argumentparser.ArgumentParser(
            prog='#speed',
            description='speed test',
            allow_abbrev=False,
            add_help=False,
            exit_on_error=False
        )
        self._add_speed_argument()

    def _add_resolve_argument(self):
        self.resolve_parse.add_argument(
            '-h', '--help',
            help='显示帮助',
            action='help'
        )
        self.resolve_parse.add_argument(
            'host',
            help='域名'
        )
        family_type = self.resolve_parse.add_mutually_exclusive_group()
        family_type.add_argument(
            '-6',
            help='仅IPV6',
            action='store_true'
        )
        family_type.add_argument(
            '-4',
            help='仅IPV4',
            action='store_true'
        )
        self.resolve_parse.add_argument(
            '-w',
            help='解析超时时间 [0, 10000]ms',
            type=int,
            default=2000
        )
        self.resolve_parse.add_argument(
            '-r',
            help='测试节点',
            default='FJ'
        )

    def _add_ping_argument(self):
        self.ping_parse.add_argument(
            '-h', '--help',
            help='显示帮助',
            action='help'
        )
        self.ping_parse.add_argument(
            'host',
            help='域名或ip'
        )
        family_type = self.ping_parse.add_mutually_exclusive_group()
        family_type.add_argument(
            '-6',
            help='强制IPV6',
            action='store_true'
        )
        family_type.add_argument(
            '-4',
            help='强制IPV4',
            action='store_true'
        )
        self.ping_parse.add_argument(
            '-c',
            help='ping次数',
            type=int,
            default=5
        )
        self.ping_parse.add_argument(
            '-i',
            help='ping间隔 ms',
            type=int,
            default=1000
        )
        self.ping_parse.add_argument(
            '-w',
            help='ping超时时间 ms',
            type=int,
            default=2000
        )
        self.ping_parse.add_argument(
            '-r',
            help='测试节点',
            default='FJ'
        )

    def _add_mtr_argument(self):
        self.mtr_parse.add_argument(
            '--help',
            help='显示帮助',
            action='help'
        )
        self.mtr_parse.add_argument(
            'host',
            help='域名或ip'
        )
        family_type = self.mtr_parse.add_mutually_exclusive_group()
        family_type.add_argument(
            '-6',
            help='强制IPV6',
            action='store_true'
        )
        family_type.add_argument(
            '-4',
            help='强制IPV4',
            action='store_true'
        )
        self.mtr_parse.add_argument(
            '-c',
            help='mtr次数',
            type=int,
            default=1
        )
        self.mtr_parse.add_argument(
            '-i',
            help='每轮mtr间隔 ms',
            type=int,
            default=1000
        )
        self.mtr_parse.add_argument(
            '-w',
            help='每跳超时时间 ms',
            type=int,
            default=2000
        )
        self.mtr_parse.add_argument(
            '-h',
            help='最大跳数',
            type=int,
            default=30
        )
        self.mtr_parse.add_argument(
            '-r',
            help='测试节点',
            default='FJ'
        )
        self.mtr_parse.add_argument(
            '--no-local',
            help='不解析地理位置',
            action='store_true'
        )

    def _add_tcping_argument(self):
        self.tcping_parse.add_argument(
            '-h', '--help',
            help='显示帮助',
            action='help'
        )
        self.tcping_parse.add_argument(
            'host',
            help='域名或ip'
        )
        self.tcping_parse.add_argument(
            'port',
            help='端口号',
            type=int
        )
        family_type = self.tcping_parse.add_mutually_exclusive_group()
        family_type.add_argument(
            '-6',
            help='强制IPV6',
            action='store_true'
        )
        family_type.add_argument(
            '-4',
            help='强制IPV4',
            action='store_true'
        )
        self.tcping_parse.add_argument(
            '-c',
            help='tcping次数',
            type=int,
            default=5
        )
        self.tcping_parse.add_argument(
            '-i',
            help='tcping间隔 ms',
            type=int,
            default=1000
        )
        self.tcping_parse.add_argument(
            '-w',
            help='tcping超时时间 ms',
            type=int,
            default=2000
        )
        self.tcping_parse.add_argument(
            '-r',
            help='测试节点',
            default='FJ'
        )

    def _add_speed_argument(self):
        self.speed_parse.add_argument(
            '-h', '--help',
            help='显示帮助',
            action='help'
        )
        self.speed_parse.add_argument(
            'url',
            help='测速目标地址'
        )
        family_type = self.speed_parse.add_mutually_exclusive_group()
        family_type.add_argument(
            '-6',
            help='强制IPV6',
            action='store_true'
        )
        family_type.add_argument(
            '-4',
            help='强制IPV4',
            action='store_true'
        )
        self.speed_parse.add_argument(
            '-t',
            help='速度测试时长 ms',
            type=int,
            default=30000
        )
        self.speed_parse.add_argument(
            '-i',
            help='速度采样间隔 ms',
            type=int,
            default=250
        )
        self.speed_parse.add_argument(
            '-w',
            help='连接超时时间 ms',
            type=int,
            default=10000
        )
        self.speed_parse.add_argument(
            '-r',
            help='测试节点',
            default='FJ'
        )

    @staticmethod
    def add_browser():
        global firefoxdriver
        global ip
        global port
        ip = bind_ip
        port = bind_port
        options = Options()
        options.headless = True
        firefoxdriver = webdriver.Firefox(options=options)

    async def nodelist_handler(self, msg_event, session):
        await session.send_msg(
            'websocket服务器:\n' +
            '\n'.join([key for key, value in self.api_servers_ws.items()]) +
            '\nhttp服务器:\n' +
            '\n'.join([str(value) for key, value in self.api_servers_http.items()])
        )

    async def resolve_handler(self, msg_event, session):
        try:
            arg = self.resolve_parse.parse_args(msg_event.message.split(' ')[1:])
            arg = vars(arg)
            address = arg.get('host')

            family = 4 if arg.get('4') else 0
            family = 6 if arg.get('6') else family

            wait = arg.get('w')
            wait = wait if wait < 10001 else 10000
            wait = wait if wait > 0 else 2000
            remote = arg.get('r').upper()

            serv = self.api_servers_ws.get(remote)
            if serv is None:
                serv = self.api_servers_http.get(remote)
            if serv is None:
                await session.send_msg('指定的节点不存在')
                return
            await session.send_msg(f'正在使用远程节点 {str(serv)} 解析IP地址。')
            resp = await serv.resolve(address, family, wait)
            if resp is not None:
                if resp.get('ok'):
                    await session.send_msg(
                        f'远程节点 {str(serv)}  对 {address} 解析结果如下:\n' +
                        '\n'.join(resp.get('result').get('data'))
                    )
                else:
                    await session.send_msg(f'请求失败: {resp.get("info")}')
                return
            await session.send_msg('请求失败')
        except argumentparser.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.resolve_parse.format_help()}')

    async def ping_handler(self, msg_event, session):
        try:
            arg = self.ping_parse.parse_args(msg_event.message.split(' ')[1:])
            arg = vars(arg)
            address = arg.get('host')

            family = 4 if arg.get('4') else 0
            family = 6 if arg.get('6') else family

            count = arg.get('c')
            count = count if count < 101 else 100
            count = count if count > 0 else 5

            wait = arg.get('w')
            interval = arg.get('i')
            remote = arg.get('r').upper()

            serv = self.api_servers_ws.get(remote)
            if serv is None:
                serv = self.api_servers_http.get(remote)
            if serv is None:
                await session.send_msg('指定的节点不存在')
                return
            await session.send_msg(f'正在使用远程节点 {str(serv)} 对 {address} 进行 {count} 次 ICMP Ping 测试。'
                                   f'测试间隔 {interval}ms，超时时间 {wait}ms')
            resp = await serv.ping(address, family, wait, interval, count)
            if resp is not None:
                if resp.get('ok'):
                    totol_count = len(resp.get('result').get('data'))
                    resp_address = resp.get('result').get('resolved')
                    success_count = 0
                    avg_latency = 0
                    max_latency = 0
                    min_latency = 2000
                    for data in resp.get('result').get('data'):
                        if data.get('code') == 257:
                            success_count += 1
                            latency = data.get('latency')
                            avg_latency += latency
                            max_latency = max(latency, max_latency)
                            min_latency = min(latency, min_latency)
                    if success_count > 0:
                        avg_latency = avg_latency / success_count
                        jitter = max_latency - min_latency
                    else:
                        avg_latency = wait
                        max_latency = wait
                        min_latency = wait
                        jitter = 0
                    loss = (totol_count - success_count) / totol_count * 100
                    await session.send_msg(
                        f'远程节点 {str(serv)}  对 {address} 进行 {count} 次 ICMP Ping 测试结果如下:\n'
                        f'IP地址: {resp_address} \n丢包率: {round(loss, 2)}%\n接收情况: {success_count}/{totol_count}\n'
                        f'平均延迟: {round(avg_latency, 2)}ms\n最大延迟: {round(max_latency, 2)}ms\n'
                        f'最小延迟: {round(min_latency, 2)}ms\n抖动: {round(jitter, 2)}ms'
                    )
                else:
                    await session.send_msg(f'请求失败: {resp.get("info")}')
                return
            await session.send_msg('请求失败')
        except argumentparser.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.ping_parse.format_help()}')

    async def tcping_handler(self, msg_event, session):
        try:
            arg = self.tcping_parse.parse_args(msg_event.message.split(' ')[1:])
            arg = vars(arg)
            address = arg.get('host')
            port = arg.get('port')

            family = 4 if arg.get('4') else 0
            family = 6 if arg.get('6') else family

            count = arg.get('c')
            count = count if count < 101 else 100
            count = count if count > 0 else 5

            wait = arg.get('w')
            interval = arg.get('i')
            remote = arg.get('r').upper()

            serv = self.api_servers_ws.get(remote)
            if serv is None:
                serv = self.api_servers_http.get(remote)
            if serv is None:
                await session.send_msg('指定的节点不存在')
                return
            await session.send_msg(
                f'正在使用远程节点 {str(serv)} 对 {address} TCP端口 {port} 进行 {count} 次 TCP Ping 测试。'
                f'测试间隔 {interval}ms，超时时间 {wait}ms'
            )
            resp = await serv.tcping(address, family, port, wait, interval, count)
            if resp is not None:
                if resp.get('ok'):
                    totol_count = len(resp.get('result').get('data'))
                    resp_address = resp.get('result').get('resolved')
                    success_count = 0
                    avg_latency = 0
                    max_latency = 0
                    min_latency = 2000
                    for data in resp.get('result').get('data'):
                        if data.get('success'):
                            success_count += 1
                            latency = data.get('latency')
                            avg_latency += latency
                            max_latency = max(latency, max_latency)
                            min_latency = min(latency, min_latency)
                    if success_count > 0:
                        avg_latency = avg_latency / success_count
                        jitter = max_latency - min_latency
                    else:
                        avg_latency = wait
                        max_latency = wait
                        min_latency = wait
                        jitter = 0
                    loss = (totol_count - success_count) / totol_count * 100
                    await session.send_msg(
                        f'远程节点 {str(serv)} 对 {address} TCP端口 {port}  进行 {count} 次 TCP Ping 测试结果如下:\n'
                        f'IP地址: {resp_address} \n丢包率: {round(loss, 2)}%\n接收情况: {success_count}/{totol_count}\n'
                        f'平均延迟: {round(avg_latency, 2)}ms\n最大延迟: {round(max_latency, 2)}ms\n'
                        f'最小延迟: {round(min_latency, 2)}ms\n抖动: {round(jitter, 2)}ms'
                    )
                else:
                    await session.send_msg(f'请求失败: {resp.get("info")}')
                return
            await session.send_msg('请求失败')
        except argumentparser.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.tcping_parse.format_help()}')

    @staticmethod
    def mtr_screenshot(json_name, pic_file):
        firefoxdriver.set_window_size(800, 10000)
        firefoxdriver.get(f'http://{ip}:{port}/netmeasurestatic/mtr.html?json={json_name}')
        firefoxdriver.find_element_by_id("mtr").screenshot(pic_file)

    async def mtr_handler(self, msg_event, session):
        try:
            arg = self.mtr_parse.parse_args(msg_event.message.split(' ')[1:])
            arg = vars(arg)
            address = arg.get('host')

            family = 4 if arg.get('4') else 0
            family = 6 if arg.get('6') else family

            count = arg.get('c')
            count = count if count < 101 else 100
            count = count if count > 0 else 5

            hops = arg.get('h')
            wait = arg.get('w')
            interval = arg.get('i')
            remote = arg.get('r').upper()

            serv = self.api_servers_ws.get(remote)
            if serv is None:
                serv = self.api_servers_http.get(remote)
            if serv is None:
                await session.send_msg('指定的节点不存在')
                return
            await session.send_msg(
                f'正在使用远程节点 {str(serv)} 对 {address} 进行 {count}轮 最大 {hops}跳的 MTR路由追踪。每轮间隔'
                f' {interval}ms, 每跳超时 {wait}ms。'
            )
            resp = await serv.mtr(address, family, wait, interval, count, hops, True)
            if resp is not None:
                if resp.get('ok'):
                    rdata = resp.get('result').get('data')
                    hops = max(map(len, rdata))
                    z = zip_longest(*rdata)

                    result = [
                        {
                            'hop': i + 1,
                            'address': list(),
                            'location': '',
                            'rdns': list(),
                            'loss': 0.0,
                            'avg': 0.0,
                            'best': 10000.0,
                            'worst': 0.0,
                            'sdev': 0.0
                        }
                        for i in range(hops)
                    ]
                    for hop, t in enumerate(z):
                        receive_count = 0
                        loss_count = 0
                        latency_sum = 0.0
                        stdevs = []
                        for i in t:
                            if i:
                                if i['code'] == 257 or i['code'] == 258:
                                    receive_count += 1
                                    _l = i['latency']
                                    stdevs.append(_l)
                                    latency_sum += _l
                                    result[hop]['best'] = min(result[hop]['best'], _l)
                                    result[hop]['worst'] = max(result[hop]['worst'], _l)
                                else:
                                    loss_count += 1
                                _addr = i['address']
                                if _addr:
                                    if _addr not in result[hop]['address']:
                                        result[hop]['address'].append(_addr)
                                        result[hop]['rdns'].append(i['rdns'])
                        if receive_count:
                            result[hop]['avg'] = latency_sum / receive_count

                        result[hop]['loss'] = loss_count / (loss_count + receive_count)
                        if not result[hop]['address']:
                            result[hop]['address'].append('')
                            result[hop]['rdns'].append('')
                            result[hop]['best'] = 0.0
                        if len(stdevs) > 1:
                            result[hop]['sdev'] = statistics.stdev(stdevs)
                        result[hop]['received'] = receive_count
                        result[hop]['lossed'] = loss_count

                    _t = str(time.time())
                    json_name = f'mtr_{_t}.json'
                    json_path = f'tmp/json/mtr_{_t}.json'
                    pic_path = f'tmp/pic/mtr_{_t}.png'
                    async with async_open(json_path, 'w') as j:
                        await j.write(json.dumps({
                            'time': time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()),
                            'node': serv.name,
                            'address': address,
                            'data': result
                        }))
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            session.executor,
                            netmeasure.mtr_screenshot,
                            json_name,
                            pic_path
                        )
                        await session.send_msg(session.picstr(f'file://{os.getcwd()}/{pic_path}'))
                        # sleep 5 min then delete temp file
                        await asyncio.sleep(300)
                    finally:
                        # clean up
                        os.remove(json_path)
                        os.remove(pic_path)
                else:
                    await session.send_msg(f'请求失败: {resp.get("info")}')
                return
            await session.send_msg('请求失败')
        except argumentparser.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.mtr_parse.format_help()}')

    @staticmethod
    def speed_screenshot(json_name, pic_file):
        firefoxdriver.set_window_size(1280, 720)
        firefoxdriver.get(f'http://{ip}:{port}/netmeasurestatic/speedtest.html?json={json_name}')
        time.sleep(1)
        firefoxdriver.find_element_by_id("speed").screenshot(pic_file)

    @staticmethod
    def bytes_unit(numbers):
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = 1024.0
        for i in range(len(units)):
            if (numbers / size) < 1:
                return f'{numbers:.2f} {units[i]}'
            numbers /= size

    async def speed_handler(self, msg_event, session):
        try:
            arg = self.speed_parse.parse_args(msg_event.message.split(' ')[1:])
            arg = vars(arg)
            address = arg.get('url')

            family = 4 if arg.get('4') else 0
            family = 6 if arg.get('6') else family

            span = arg.get('t')
            wait = arg.get('w')
            interval = arg.get('i')
            remote = arg.get('r').upper()
            serv = self.api_servers_ws.get(remote)
            if serv is None:
                serv = self.api_servers_http.get(remote)
            if serv is None:
                await session.send_msg('指定的节点不存在')
                return
            await session.send_msg(
                f'正在使用远程节点 {str(serv)} 进行测速。测速总时长: {span} ms, 测速握手超时：{wait} ms, '
                f'测速采样率{1000/int(interval)}Hz。'
            )
            resp = await serv.speed(address, family, wait, span, interval)
            if resp is not None:
                if resp.get('ok'):
                    resolved_address = resp.get('result').get('resolved')
                    latency = resp.get('result').get('latency')
                    elapsed = resp.get('result').get('elapsed')
                    received = resp.get('result').get('received')
                    if received is not None:
                        received = netmeasure.bytes_unit(received)
                    result_data = resp.get('result').get('data')
                    start = 0
                    result_list = list()
                    for result in result_data:
                        now = result.get('point')
                        receive = result.get('received')
                        result_list.append({
                            'point': round(now / 1000, 2),
                            'received': round(8 * receive / (now - start) / 1000, 2)
                        })
                        start = now
                    _t = str(time.time())
                    json_name = f'speed_{_t}.json'
                    json_path = f'tmp/json/speed_{_t}.json'
                    pic_path = f'tmp/pic/speed_{_t}.png'

                    async with async_open(json_path, 'w') as j:
                        await j.write(json.dumps({
                            'ip': resolved_address,
                            'location': '',
                            'latency': latency,
                            'received': received,
                            'average': round(8 * resp.get('result').get('received') / elapsed / 1000, 2),
                            'time': time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()),
                            'node': serv.name,
                            'data': result_list
                        }))

                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            session.executor,
                            netmeasure.speed_screenshot,
                            json_name,
                            pic_path
                        )
                        await session.send_msg(session.picstr(f'file://{os.getcwd()}/{pic_path}'))
                        # sleep 5 min then delete temp file
                        await asyncio.sleep(300)
                    finally:
                        # clean up
                        os.remove(json_path)
                        os.remove(pic_path)
                else:
                    await session.send_msg(f'请求失败: {resp.get("info")}')
                return
            await session.send_msg('请求失败')
        except argumentparser.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.mtr_parse.format_help()}')
