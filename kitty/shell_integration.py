#!/usr/bin/env python
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shlex
from typing import Callable, Dict, List, Optional

from .constants import kitten_exe
from .fast_data_types import get_options
from .options.types import Options, defaults


def as_str_literal(x: str) -> str:
    parts = x.split("'")
    return '"\'"'.join(f"'{x}'" for x in parts)


def as_fish_str_literal(x: str) -> str:
    x = x.replace('\\', '\\\\').replace("'", "\\'")
    return f"'{x}'"


def posix_serialize_env(env: Dict[str, str], prefix: str = 'builtin export', sep: str = '=') -> str:
    ans = []
    for k, v in env.items():
        ans.append(f'{prefix} {as_str_literal(k)}{sep}{as_str_literal(v)}')
    return '\n'.join(ans)


def fish_serialize_env(env: Dict[str, str]) -> str:
    ans = []
    for k, v in env.items():
        ans.append(f'set -gx {as_fish_str_literal(k)} {as_fish_str_literal(v)}')
    return '\n'.join(ans)


ENV_SERIALIZERS: Dict[str, Callable[[Dict[str, str]], str]] = {
    'zsh':  posix_serialize_env,
    'bash': posix_serialize_env,
    'fish': fish_serialize_env,
}


def get_supported_shell_name(path: str) -> Optional[str]:
    name = os.path.basename(path)
    if name.lower().endswith('.exe'):
        name = name.rpartition('.')[0]
    if name.startswith('-'):
        name = name[1:]
    return name if name in ENV_SERIALIZERS else None


def serialize_env(path: str, env: Dict[str, str]) -> str:
    if not env:
        return ''
    name = get_supported_shell_name(path)
    if not name:
        raise ValueError(f'{path} is not a supported shell')
    return ENV_SERIALIZERS[name](env)


def get_effective_ksi_env_var(opts: Optional[Options] = None) -> str:
    opts = opts or get_options()
    if 'disabled' in opts.shell_integration:
        return ''
    # Use the default when shell_integration is empty due to misconfiguration
    if 'invalid' in opts.shell_integration:
        return ' '.join(defaults.shell_integration)
    return ' '.join(opts.shell_integration)


def modify_shell_environ(opts: Options, env: Dict[str, str], argv: List[str]) -> None:
    shell = get_supported_shell_name(argv[0])
    ksi = get_effective_ksi_env_var(opts)
    if shell is None or not ksi:
        return
    argv[:] = [kitten_exe(), 'run-shell', '--shell-integration', ksi, '--shell', shlex.join(argv)]
