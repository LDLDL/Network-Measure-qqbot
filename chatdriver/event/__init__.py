import enum

from .msg_event import *
from .request_event import *
from .notice_event import *

__all__ = [
    'event_type',
    # events
    'msg_event',
    'request_event',
    'notice_event',
]


class event_type(enum.Enum):
    MESSAGE = enum.auto()
    NOTICE = enum.auto()
    REQUEST = enum.auto()

