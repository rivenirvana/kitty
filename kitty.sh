KITTY_INSTALLATION_DIR="/usr/lib64/kitty"
if [[ -n "${BASH_VERSION}" && -n "${KITTY_PID}" ]]; then
    if [[ -f "$KITTY_INSTALLATION_DIR"/shell-integration/bash/kitty.bash ]]; then
        export KITTY_SHELL_INTEGRATION="enabled"
        source "$KITTY_INSTALLATION_DIR"/shell-integration/bash/kitty.bash
    fi
fi
