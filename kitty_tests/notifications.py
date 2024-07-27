#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import tempfile
from base64 import standard_b64encode

from kitty.notifications import Channel, DesktopIntegration, IconDataCache, NotificationManager, UIState, Urgency

from . import BaseTest


def n(title='title', body='', urgency=Urgency.Normal, desktop_notification_id=1, icon_name='', icon_path='', application_name='', notification_type=''):
    return {
        'title': title, 'body': body, 'urgency': urgency, 'id': desktop_notification_id, 'icon_name': icon_name, 'icon_path': icon_path,
        'application_name': application_name, 'notification_type': notification_type,
    }


class DesktopIntegration(DesktopIntegration):
    def initialize(self):
        self.reset()

    def reset(self):
        self.notifications = []
        self.close_events = []
        self.new_version_activated = False
        self.close_succeeds = True
        self.counter = 0

    def on_new_version_notification_activation(self, cmd) -> None:
        self.new_version_activated = True

    def close_notification(self, desktop_notification_id: int) -> bool:
        self.close_events.append(desktop_notification_id)
        if self.close_succeeds:
            self.notification_manager.notification_closed(desktop_notification_id)
        return self.close_succeeds

    def notify(self, cmd) -> int:
        self.counter += 1
        title, body, urgency = cmd.title, cmd.body, (Urgency.Normal if cmd.urgency is None else cmd.urgency)
        ans = n(title, body, urgency, self.counter, cmd.icon_name, os.path.basename(cmd.icon_path), cmd.application_name, cmd.notification_type)
        self.notifications.append(ans)
        return self.counter


class Channel(Channel):

    focused = visible = True

    def __init__(self, *a):
        super().__init__(*a)
        self.reset()

    def reset(self):
        self.responses = []
        self.focus_events = []

    def ui_state(self, channel_id):
        return UIState(self.focused, self.visible)

    def focus(self, channel_id: int, activation_token: str) -> None:
        self.focus_events.append(activation_token)

    def send(self, channel_id: int, osc_escape_code: str) -> bool:
        self.responses.append(osc_escape_code)


def do_test(self: 'TestNotifications', tdir: str) -> None:
    di = DesktopIntegration(None)
    ch = Channel()
    nm = NotificationManager(di, ch, lambda *a, **kw: None, base_cache_dir=tdir)
    di.notification_manager = nm

    def reset():
        di.reset()
        ch.reset()
        nm.reset()

    def h(raw_data, osc_code=99, channel_id=1):
        nm.handle_notification_cmd(channel_id, osc_code, raw_data)

    def activate(which=0):
        n = di.notifications[which]
        nm.notification_activated(n['id'])

    def close(which=0):
        n = di.notifications[which]
        di.close_notification(n['id'])

    def assert_events(focus=True, close=0, report='', close_response=''):
        self.ae(ch.focus_events, [''] if focus else [])
        if report:
            self.assertIn(f'99;i={report};', ch.responses)
        else:
            for r in ch.responses:
                m = re.match(r'99;i=[a-z0-9]+;', r)
                self.assertIsNone(m, f'Unexpectedly found report response: {r}')
        if close_response:
            self.assertIn(f'99;i={close_response}:p=close;', ch.responses)
        else:
            for r in ch.responses:
                m = re.match(r'99;i=[a-z0-9]+:p=close;', r)
                self.assertIsNone(m, f'Unexpectedly found close response: {r}')
        self.ae(di.close_events, [close] if close else [])

    h('test it', osc_code=9)
    self.ae(di.notifications, [n(title='test it')])
    activate()
    assert_events()
    reset()

    h('d=0:u=2:i=x;title')
    h('d=1:i=x:p=body;body')
    self.ae(di.notifications, [n(body='body', urgency=Urgency.Critical)])
    activate()
    assert_events()
    reset()

    h('i=x:p=body:a=-focus;body')
    self.ae(di.notifications, [n(title='body')])
    activate()
    assert_events(focus=False)
    reset()

    nm.send_new_version_notification('moose')
    self.ae(di.notifications, [n('kitty update available!', 'kitty version moose released')])
    activate()
    self.assertTrue(di.new_version_activated)
    reset()

    h('i=x:e=1;' + standard_b64encode(b'title').decode('ascii'))
    self.ae(di.notifications, [n()])
    activate()
    assert_events()
    reset()

    h('e=1;' + standard_b64encode(b'title').decode('ascii'))
    self.ae(di.notifications, [n()])
    activate()
    assert_events()
    reset()

    h('d=0:i=x:a=-report;title')
    h('d=1:i=x:a=report;body')
    self.ae(di.notifications, [n(title='titlebody')])
    activate()
    assert_events(report='x')
    reset()

    h('a=report;title')
    self.ae(di.notifications, [n()])
    activate()
    assert_events(report='0')
    reset()

    h('d=0:i=y;title')
    h('d=1:i=y:p=xxx;title')
    self.ae(di.notifications, [n()])
    reset()

    # test closing interactions with reporting and activation
    h('i=c;title')
    self.ae(di.notifications, [n()])
    close()
    assert_events(focus=False, close=True)
    reset()
    h('i=c:c=1;title')
    self.ae(di.notifications, [n()])
    h('i=c:p=close')
    self.ae(di.notifications, [n()])
    assert_events(focus=False, close=True, close_response='c')
    reset()
    h('i=c:c=1;title')
    h('i=c:p=close')
    self.ae(di.notifications, [n()])
    assert_events(focus=False, close=True, close_response='c')
    reset()
    h('i=c;title')
    activate()
    close()
    h('i=c:p=close')
    self.ae(di.notifications, [n()])
    assert_events(focus=True, close=True)
    reset()
    h('i=c:a=report:c=1;title')
    activate()
    h('i=c:p=close')
    self.ae(di.notifications, [n()])
    assert_events(focus=True, report='c', close=True, close_response='c')
    reset()

    h(';title')
    self.ae(di.notifications, [n()])
    activate()
    assert_events()
    reset()

    # Test querying
    h('i=xyz:p=?')
    self.assertFalse(di.notifications)
    qr = 'a=focus,report:o=always,unfocused,invisible:u=0,1,2:p=title,body,?,close,icon:c=1'
    self.ae(ch.responses, [f'99;i=xyz:p=?;{qr}'])
    reset()
    h('p=?')
    self.assertFalse(di.notifications)
    self.ae(ch.responses, [f'99;i=0:p=?;{qr}'])

    # Test MIME streaming
    for padding in (True, False):
        for extra in ('a', 'ab', 'abc', 'abcd'):
            text = 'some reasonably long text to test MIME streaming with: '
            encoded = standard_b64encode(text.encode()).decode()
            if not padding:
                encoded = encoded.rstrip('=')
            for t in encoded:
                h(f'i=s:e=1:d=0;{t}')
            h(f'i=s:e=1:d=0:p=body;{encoded[:13]}')
            h(f'i=s:e=1:d=0:p=body;{encoded[13:]}')
            h('i=s')
            self.ae(di.notifications, [n(text, text)])
            reset()

    # Test application name and notification type
    def e(x):
        return standard_b64encode(x.encode()).decode()

    h(f'i=t:d=0:f={e("app")};title')
    h(f'i=t:t={e("test")}')
    self.ae(di.notifications, [n(application_name='app', notification_type='test')])
    reset()

    # Test Disk Cache
    dc = IconDataCache(base_cache_dir=tdir, max_cache_size=4)
    cache_dir = dc._ensure_state()
    for i in range(5):
        dc.add_icon(str(i), str(i).encode())
    self.ae(set(dc.keys()), set(map(str, range(1, 5))))
    del dc
    self.assertFalse(os.path.exists(cache_dir))

    # Test icons
    def send_with_icon(data='', n='', g=''):
        m = ''
        if n:
            m += f'n={n}:'
        if g:
            m += f'g={g}:'
        h(f'i=9:d=0:{m};title')
        h(f'i=9:p=icon;{data}')

    dc = nm.icon_data_cache
    send_with_icon(n='mycon')
    self.ae(di.notifications, [n(icon_name='mycon')])
    reset()
    send_with_icon(g='gid')
    self.ae(di.notifications, [n()])
    reset()
    send_with_icon(g='gid', data='1')
    self.ae(di.notifications, [n(icon_path=dc.hash(b'1'))])
    send_with_icon(g='gid', n='moose')
    self.ae(di.notifications[-1], n(icon_name='moose', icon_path=dc.hash(b'1'), desktop_notification_id=len(di.notifications)))
    send_with_icon(g='gid2', data='2')
    self.ae(di.notifications[-1], n(icon_path=dc.hash(b'2'), desktop_notification_id=len(di.notifications)))
    reset()


class TestNotifications(BaseTest):

    def test_desktop_notify(self):
        with tempfile.TemporaryDirectory() as tdir:
            do_test(self, tdir)

