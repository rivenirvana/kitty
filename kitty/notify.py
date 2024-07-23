#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import re
from base64 import standard_b64decode
from collections import OrderedDict
from contextlib import suppress
from enum import Enum
from itertools import count
from typing import Callable, Dict, FrozenSet, Optional

from .constants import is_macos, logo_png_file
from .fast_data_types import current_focused_os_window_id, get_boss
from .types import run_once
from .utils import get_custom_window_icon, log_error


class Urgency(Enum):
    Low: int = 0
    Normal: int = 1
    Critical: int = 2


if is_macos:
    from .fast_data_types import cocoa_send_notification

    def notify(
        title: str,
        body: str,
        timeout: int = 5000,
        application: str = 'kitty',
        icon: bool = True,
        identifier: Optional[str] = None,
        subtitle: Optional[str] = None,
        urgency: Urgency = Urgency.Normal,
    ) -> None:
        cocoa_send_notification(identifier, title, body, subtitle, urgency.value)

else:

    from .fast_data_types import dbus_send_notification

    alloc_map: Dict[int, str] = {}
    identifier_map: Dict[str, int] = {}

    def dbus_notification_created(alloc_id: int, notification_id: int) -> None:
        identifier = alloc_map.pop(alloc_id, None)
        if identifier is not None:
            identifier_map[identifier] = notification_id

    def dbus_notification_activated(notification_id: int, action: str) -> None:
        rmap = {v: k for k, v in identifier_map.items()}
        identifier = rmap.get(notification_id)
        if identifier is not None:
            notification_activated(identifier)

    def notify(
        title: str,
        body: str,
        timeout: int = -1,
        application: str = 'kitty',
        icon: bool = True,
        identifier: Optional[str] = None,
        subtitle: Optional[str] = None,
        urgency: Urgency = Urgency.Normal,
    ) -> None:
        icf = ''
        if icon is True:
            icf = get_custom_window_icon()[1] or logo_png_file
        alloc_id = dbus_send_notification(application, icf, title, body, 'Click to see changes', timeout, urgency.value)
        if alloc_id and identifier is not None:
            alloc_map[alloc_id] = identifier

class NotifyImplementation:
    def __call__(self, title: str, body: str, identifier: str, urgency: Urgency = Urgency.Normal) -> None:
        notify(title, body, identifier=identifier, urgency=urgency)

notify_implementation = NotifyImplementation()


class OnlyWhen(Enum):
    unset = ''
    always = 'always'
    unfocused = 'unfocused'
    invisible = 'invisible'


class Action(Enum):
    focus = 'focus'
    report = 'report'


class NotificationCommand:

    done: bool = True
    identifier: str = '0'
    title: str = ''
    body: str = ''
    actions: FrozenSet[Action] = frozenset((Action.focus,))
    only_when: OnlyWhen = OnlyWhen.unset
    urgency: Optional[Urgency] = None

    def __repr__(self) -> str:
        return (
            f'NotificationCommand(identifier={self.identifier!r}, title={self.title!r}, body={self.body!r},'
            f'actions={self.actions}, done={self.done!r}, urgency={self.urgency})')


def parse_osc_9(raw: str) -> NotificationCommand:
    ans = NotificationCommand()
    ans.title = raw
    return ans


def parse_osc_777(raw: str) -> NotificationCommand:
    parts = raw.split(';', 1)
    ans = NotificationCommand()
    ans.title = parts[0]
    if len(parts) > 1:
        ans.body = parts[1]
    return ans


@run_once
def sanitize_identifier_pat() -> 're.Pattern[str]':
    return re.compile(r'[^a-zA-Z0-9-_+.]+')


def sanitize_id(v: str) -> str:
    return sanitize_identifier_pat().sub('', v)


class QueryResponse(Exception):

    def __init__(self, response_string: str):
        super().__init__('not an error')
        self.response_string = response_string


def parse_osc_99(raw: str) -> NotificationCommand:
    cmd = NotificationCommand()
    metadata, payload = raw.partition(';')[::2]
    payload_is_encoded = False
    payload_type = 'title'
    if metadata:
        for part in metadata.split(':'):
            try:
                k, v = part.split('=', 1)
            except Exception:
                log_error('Malformed OSC 99: metadata is not key=value pairs')
                return cmd
            if k == 'p':
                payload_type = v
            elif k == 'i':
                cmd.identifier = sanitize_id(v)
            elif k == 'e':
                payload_is_encoded = v == '1'
            elif k == 'd':
                cmd.done = v != '0'
            elif k == 'a':
                for ax in v.split(','):
                    if remove := ax.startswith('-'):
                        ax = ax.lstrip('+-')
                    try:
                        ac = Action(ax)
                    except ValueError:
                        pass
                    else:
                        if remove:
                            cmd.actions -= {ac}
                        else:
                            cmd.actions = cmd.actions.union({ac})
            elif k == 'o':
                with suppress(ValueError):
                    cmd.only_when = OnlyWhen(v)
            elif k == 'u':
                with suppress(Exception):
                    cmd.urgency = Urgency(int(v))
    if payload_type == '?':
        actions = ','.join(x.name for x in Action)
        when = ','.join(x.name for x in OnlyWhen if x.value)
        urgency = ','.join(str(x.value) for x in Urgency)
        i = f'i={sanitize_id(cmd.identifier or "0")}:'
        raise QueryResponse(f'99;{i}p=?;a={actions}:o={when}:u={urgency}')

    if payload_type not in ('body', 'title'):
        log_error(f'Malformed OSC 99: unknown payload type: {payload_type}')
        return NotificationCommand()
    if payload_is_encoded:
        try:
            payload = standard_b64decode(payload).decode('utf-8')
        except Exception:
            log_error('Malformed OSC 99: payload is not base64 encoded UTF-8 text')
            return NotificationCommand()
    if payload_type == 'title':
        cmd.title = payload
    else:
        cmd.body = payload
    return cmd


def limit_size(x: str) -> str:
    if len(x) > 1024:
        x = x[:1024]
    return x


def merge_osc_99(prev: NotificationCommand, cmd: NotificationCommand) -> NotificationCommand:
    if prev.done or prev.identifier != cmd.identifier:
        return cmd
    cmd.actions = prev.actions.union(cmd.actions)
    cmd.title = limit_size(prev.title + cmd.title)
    cmd.body = limit_size(prev.body + cmd.body)
    if cmd.only_when is OnlyWhen.unset:
        cmd.only_when = prev.only_when
    if cmd.urgency is None:
        cmd.urgency = prev.urgency
    return cmd


identifier_registry: "OrderedDict[str, RegisteredNotification]" = OrderedDict()
id_counter = count()


class RegisteredNotification:
    identifier: str
    window_id: int
    focus: bool = False
    report: bool = False

    def __init__(self, cmd: NotificationCommand, window_id: int):
        self.window_id = window_id
        for x in cmd.actions:
            if x is Action.focus:
                self.focus = True
            elif x is Action.report:
                self.report = True
        self.identifier = cmd.identifier


def register_identifier(identifier: str, cmd: NotificationCommand, window_id: int) -> None:
    identifier_registry[identifier] = RegisteredNotification(cmd, window_id)
    if len(identifier_registry) > 100:
        identifier_registry.popitem(False)


def notification_activated(identifier: str, activated_implementation: Optional[Callable[[str, int, bool, bool], None]] = None) -> None:
    if identifier == 'new-version':
        from .update_check import notification_activated as do
        do()
    elif identifier.startswith('test-notify-'):
        log_error(f'Test notification {identifier} activated')
    else:
        r = identifier_registry.pop(identifier, None)
        if r is not None and (r.focus or r.report):
            if activated_implementation is None:
                get_boss().notification_activated(r.identifier, r.window_id, r.focus, r.report)
            else:
                activated_implementation(r.identifier, r.window_id, r.focus, r.report)


def reset_registry() -> None:
    global id_counter
    identifier_registry.clear()
    id_counter = count()


def notify_with_command(cmd: NotificationCommand, window_id: int, notify_implementation: NotifyImplementation = notify_implementation) -> None:
    title = cmd.title or cmd.body
    body = cmd.body if cmd.title else ''
    if not title:
        return
    urgency = Urgency.Normal if cmd.urgency is None else cmd.urgency
    if cmd.only_when is not OnlyWhen.always and cmd.only_when is not OnlyWhen.unset:
        w = get_boss().window_id_map.get(window_id)
        if w is None:
            return
        boss = get_boss()
        window_has_keyboard_focus = w.is_active and w.os_window_id == current_focused_os_window_id()
        if window_has_keyboard_focus:
            return
        if cmd.only_when is OnlyWhen.invisible:
            if w.os_window_id == current_focused_os_window_id() and w.tabref() is boss.active_tab and w.is_visible_in_layout:
                return  # window is in the active OS window and the active tab and is visible in the tab layout
    if title:
        identifier = f'i{next(id_counter)}'
        notify_implementation(title, body, identifier, urgency)
        register_identifier(identifier, cmd, window_id)


def handle_notification_cmd(
    osc_code: int,
    raw_data: str,
    window_id: int,
    prev_cmd: NotificationCommand,
    notify_implementation: NotifyImplementation = notify_implementation
) -> Optional[NotificationCommand]:
    if osc_code == 99:
        cmd = merge_osc_99(prev_cmd, parse_osc_99(raw_data))
        if cmd.done:
            notify_with_command(cmd, window_id, notify_implementation)
            cmd = NotificationCommand()
        return cmd
    if osc_code == 9:
        cmd = parse_osc_9(raw_data)
        notify_with_command(cmd, window_id, notify_implementation)
        return cmd
    if osc_code == 777:
        cmd = parse_osc_777(raw_data)
        notify_with_command(cmd, window_id, notify_implementation)
        return cmd
    return None
