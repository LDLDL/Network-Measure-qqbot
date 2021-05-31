import chatdriver.event as ce


def message_event(event_json: dict) -> ce.msg_event:
    message_type = event_json.get('message_type')
    if message_type == 'private':
        return private_msg(event_json)
    elif message_type == 'group':
        return group_msg(event_json)


def private_msg(event_json: dict) -> ce.msg_event:
    pm = ce.msg_event()
    pm.time = event_json.get('time')
    pm.user_id = str(event_json.get('user_id'))
    pm.user_name = event_json.get('sender').get('nickname')
    pm.message = event_json.get('message')

    pm.attrs['-qq-msg-id'] = event_json.get('message_id')

    return pm


def group_msg(event_json: dict) -> ce.msg_event:
    gm = ce.msg_event()
    gm.msg_type = ce.msg_type.GROUP_MSG
    gm.time = event_json.get('time')
    gm.group_id = str(event_json.get('group_id'))
    gm.user_id = str(event_json.get('user_id'))
    gm.user_name = event_json.get('sender').get('nickname')
    gm.message = event_json.get('message')

    gm.attrs['-qq-msg-id'] = event_json.get('message_id')

    return gm


def request_event(event_json: dict) -> ce.request_event:
    return ce.request_event()


def notice_event(event_json: dict) -> ce.notice_event:
    return ce.notice_event()
