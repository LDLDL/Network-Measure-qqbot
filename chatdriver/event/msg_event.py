import enum

from chatdriver import event


class BadMsg(Exception):
    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg


class msg_type(enum.Enum):
    PRIVATE_MSG = enum.auto()
    GROUP_MSG = enum.auto()


class msg_event:
    def __init__(self):
        self.event_type = event.event_type.MESSAGE
        self.msg_type = msg_type.PRIVATE_MSG
        self.time = 0
        self.user_id = ''
        self.group_id = ''
        self.user_name = ''
        self.message = ''

        self.attrs = dict()
