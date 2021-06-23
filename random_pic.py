import random
import os
import time
import argparse
from argumentparser import ArgumentParser


class random_pic:
    def __init__(self):
        self.parser_n = ArgumentParser(
            prog='poi',
            description='发送N张随机图片',
            add_help=False,
            exit_on_error=False,
        )
        self.parser_n.add_argument(
            '-h', '--help',
            help='显示帮助',
            action='help'
        )
        self.parser_n.add_argument(
            'N',
            help='图片数N',
            type=int
        )
        self.pics = dict()
        self.artists = list()
        self._update_pic()

    def _update_pic(self):
        self.pics = dict()
        _work_dir = os.getcwd()
        _artists = os.listdir('pics')
        for artist in _artists:
            _pics = os.listdir(f'pics/{artist}')
            self.pics[artist] = [f'file://{_work_dir}/pics/{artist}/{p}' for p in _pics]
        self.artists = list(self.pics.keys())

    async def random_pic_handler(self, msg_event, session):
        if msg_event.message == '~':
            _artist = random.choice(self.artists)
            _pic = random.choice(self.pics.get(_artist))
            await session.send_msg(f'{session.picstr(_pic)}\n画师: {_artist}')

    async def random_pics_handler(self, msg_event, session):
        try:
            para = self.parser_n.parse_args(msg_event.message.split()[1:])
            n = para.N if para.N < 6 else 5

            last_post = session.var.get('last_post')
            if last_post is not None:
                pt = time.time() - last_post
                if pt < 90:
                    await session.send_msg(f'连续发图冷却中, 剩余{90 - int(pt)}秒。')
                    return
            session.var['last_post'] = time.time()

            for i in range(n):
                _artist = random.choice(self.artists)
                _pic = random.choice(self.pics.get(_artist))
                await session.send_msg(f'{session.picstr(_pic)}画师: {_artist}')
        except argparse.ArgumentError as err:
            await session.send_msg(f'{str(err)} \n{self.parser_n.format_help()}')

    async def update_pic_handler(self, msg_event, session):
        self._update_pic()
        count = 0
        for artist in self.artists:
            count += len(self.pics.get(artist))
        await session.send_msg(f'图库更新完成!\n共有{count}张图片, 画师数: {len(self.artists)}')
