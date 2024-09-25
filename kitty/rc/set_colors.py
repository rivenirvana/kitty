#!/usr/bin/env python
# License: GPLv3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


import os
from typing import TYPE_CHECKING, Dict, Iterable, Optional

from kitty.cli import emph
from kitty.config import parse_config
from kitty.fast_data_types import Color, patch_color_profiles

from .base import (
    MATCH_TAB_OPTION,
    MATCH_WINDOW_OPTION,
    ArgsType,
    Boss,
    ParsingOfArgsFailed,
    PayloadGetType,
    PayloadType,
    RCOptions,
    RemoteCommand,
    ResponseType,
    Window,
)

if TYPE_CHECKING:
    from kitty.cli_stub import SetColorsRCOptions as CLIOptions


def parse_colors(args: Iterable[str]) -> tuple[Dict[str, Optional[int]], tuple[tuple[Color, float], ...]]:
    from kitty.options.types import nullable_colors
    colors: Dict[str, Optional[Color]] = {}
    nullable_color_map: Dict[str, Optional[int]] = {}
    transparent_background_colors = ()
    for spec in args:
        if '=' in spec:
            conf = parse_config((spec.replace('=', ' '),))
        else:
            with open(os.path.expanduser(spec), encoding='utf-8', errors='replace') as f:
                conf = parse_config(f)
        transparent_background_colors = conf.pop('transparent_background_colors', ())
        colors.update(conf)
    for k in nullable_colors:
        q = colors.pop(k, False)
        if q is not False:
            val = int(q) if isinstance(q, Color) else None
            nullable_color_map[k] = val
    ans: Dict[str, Optional[int]] = {k: int(v) for k, v in colors.items() if isinstance(v, Color)}
    ans.update(nullable_color_map)
    return ans, transparent_background_colors


class SetColors(RemoteCommand):

    protocol_spec = __doc__ = '''
    colors+/dict.colors: An object mapping names to colors as 24-bit RGB integers or null for nullable colors. Or a string for transparent_background_colors.
    match_window/str: Window to change colors in
    match_tab/str: Tab to change colors in
    all/bool: Boolean indicating change colors everywhere or not
    configured/bool: Boolean indicating whether to change the configured colors. Must be True if reset is True
    reset/bool: Boolean indicating colors should be reset to startup values
    '''

    short_desc = 'Set terminal colors'
    desc = (
        'Set the terminal colors for the specified windows/tabs (defaults to active window).'
        ' You can either specify the path to a conf file'
        ' (in the same format as :file:`kitty.conf`) to read the colors from or you can specify individual colors,'
        ' for example::\n\n'
        '    kitten @ set-colors foreground=red background=white'
    )
    options_spec = '''\
--all -a
type=bool-set
By default, colors are only changed for the currently active window. This option will
cause colors to be changed in all windows.


--configured -c
type=bool-set
Also change the configured colors (i.e. the colors kitty will use for new
windows or after a reset).


--reset
type=bool-set
Restore all colors to the values they had at kitty startup. Note that if you specify
this option, any color arguments are ignored and :option:`kitten @ set-colors --configured` and :option:`kitten @ set-colors --all` are implied.
''' + '\n\n' + MATCH_WINDOW_OPTION + '\n\n' + MATCH_TAB_OPTION.replace('--match -m', '--match-tab -t')
    args = RemoteCommand.Args(spec='COLOR_OR_FILE ...', json_field='colors', special_parse='parse_colors_and_files(args)',
                              completion=RemoteCommand.CompletionSpec.from_string('type:file group:"CONF files", ext:conf'))

    def message_to_kitty(self, global_opts: RCOptions, opts: 'CLIOptions', args: ArgsType) -> PayloadType:
        final_colors: Dict[str, int | None | str] = {}
        transparent_background_colors: tuple[tuple[Color, float], ...] = ()
        if not opts.reset:
            try:
                fc, transparent_background_colors = parse_colors(args)
            except FileNotFoundError as err:
                raise ParsingOfArgsFailed(f'The colors configuration file {emph(err.filename)} was not found.') from err
            except Exception as err:
                raise ParsingOfArgsFailed(str(err)) from err
            final_colors.update(fc)
        if transparent_background_colors:
            final_colors['transparent_background_colors'] = ' '.join(f'{c.as_sharp}@{f}' for c, f in transparent_background_colors)
        ans = {
            'match_window': opts.match, 'match_tab': opts.match_tab,
            'all': opts.all or opts.reset, 'configured': opts.configured or opts.reset,
            'colors': final_colors, 'reset': opts.reset,
        }
        return ans

    def response_from_kitty(self, boss: Boss, window: Optional[Window], payload_get: PayloadGetType) -> ResponseType:
        windows = self.windows_for_payload(boss, window, payload_get)
        colors: Dict[str, int | None] = payload_get('colors')
        tbc = colors.get('transparent_background_colors')
        if payload_get('reset'):
            colors = {k: None if v is None else int(v) for k, v in boss.color_settings_at_startup.items()}
        profiles = tuple(w.screen.color_profile for w in windows if w)
        if tbc:
            from kitty.options.utils import transparent_background_colors
            parsed_tbc = transparent_background_colors(str(tbc))
        else:
            parsed_tbc = ()
        patch_color_profiles(colors, parsed_tbc, profiles, payload_get('configured'))
        boss.patch_colors(colors, parsed_tbc, payload_get('configured'))
        default_bg_changed = 'background' in colors
        for w in windows:
            if w:
                if default_bg_changed:
                    boss.default_bg_changed_for(w.id)
                w.refresh()
        return None


set_colors = SetColors()
