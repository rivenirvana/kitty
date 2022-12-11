set -l KITTY_INSTALLATION_DIR "/usr/lib64/kitty"
if test -n "$KITTY_PID"
    if test -f "$KITTY_INSTALLATION_DIR"/shell-integration/fish/vendor_conf.d/kitty-shell-integration.fish
        set --global KITTY_SHELL_INTEGRATION enabled
        source "$KITTY_INSTALLATION_DIR/shell-integration/fish/vendor_conf.d/kitty-shell-integration.fish"
        set --prepend fish_complete_path "$KITTY_INSTALLATION_DIR/shell-integration/fish/vendor_completions.d"
    end
end
