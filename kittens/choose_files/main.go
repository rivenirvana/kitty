package choose_files

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"

	"github.com/kovidgoyal/kitty/tools/cli"
	"github.com/kovidgoyal/kitty/tools/config"
	"github.com/kovidgoyal/kitty/tools/tty"
	"github.com/kovidgoyal/kitty/tools/tui/loop"
	"github.com/kovidgoyal/kitty/tools/utils"
)

var _ = fmt.Print
var debugprintln = tty.DebugPrintln

type ScorePattern struct {
	pat *regexp.Regexp
	op  func(float64, float64) float64
	val float64
}

type State struct {
	base_dir         string
	current_dir      string
	select_dirs      bool
	multiselect      bool
	max_depth        int
	exclude_patterns []*regexp.Regexp
	score_patterns   []ScorePattern
	search_text      string
}

func (s State) BaseDir() string                   { return utils.IfElse(s.base_dir == "", default_cwd, s.base_dir) }
func (s State) SelectDirs() bool                  { return s.select_dirs }
func (s State) Multiselect() bool                 { return s.multiselect }
func (s State) MaxDepth() int                     { return utils.IfElse(s.max_depth < 1, 4, s.max_depth) }
func (s State) String() string                    { return utils.Repr(s) }
func (s State) SearchText() string                { return s.search_text }
func (s State) ExcludePatterns() []*regexp.Regexp { return s.exclude_patterns }
func (s State) ScorePatterns() []ScorePattern     { return s.score_patterns }
func (s State) CurrentDir() string {
	return utils.IfElse(s.current_dir == "", s.BaseDir(), s.current_dir)
}

type ScreenSize struct {
	width, height, cell_width, cell_height, width_px, height_px int
}

type Handler struct {
	state       State
	screen_size ScreenSize
	scan_cache  ScanCache
	lp          *loop.Loop
}

func (h *Handler) draw_screen() (err error) {
	matches, in_progress := h.get_results()
	if len(matches) > 0 {
		h.lp.SetWindowTitle(matches[0].text)
	} else {
		h.lp.SetWindowTitle("Select a file") // TODO: make this conditional on mode
	}
	h.lp.StartAtomicUpdate()
	defer h.lp.EndAtomicUpdate()
	h.lp.ClearScreen()
	defer func() { // so that the cursor ends up in the right place
		h.lp.MoveCursorTo(1, 1)
		h.draw_search_bar(0)
	}()
	y := SEARCH_BAR_HEIGHT
	y += h.draw_results(y, 2, matches, in_progress)
	return
}

func load_config(opts *Options) (ans *Config, err error) {
	ans = NewConfig()
	p := config.ConfigParser{LineHandler: ans.Parse}
	err = p.LoadConfig("choose-files.conf", opts.Config, opts.Override)
	if err != nil {
		return nil, err
	}
	// ans.KeyboardShortcuts = config.ResolveShortcuts(ans.KeyboardShortcuts)
	return ans, nil
}

func (h *Handler) init_sizes(new_size loop.ScreenSize) {
	h.screen_size.width = int(new_size.WidthCells)
	h.screen_size.height = int(new_size.HeightCells)
	h.screen_size.cell_width = int(new_size.CellWidth)
	h.screen_size.cell_height = int(new_size.CellHeight)
	h.screen_size.width_px = int(new_size.WidthPx)
	h.screen_size.height_px = int(new_size.HeightPx)
}

func (h *Handler) OnInitialize() (ans string, err error) {
	if sz, err := h.lp.ScreenSize(); err != nil {
		return "", err
	} else {
		h.init_sizes(sz)
	}
	h.lp.AllowLineWrapping(false)
	h.lp.SetCursorShape(loop.BAR_CURSOR, true)
	h.draw_screen()
	return
}

func (h *Handler) OnKeyEvent(ev *loop.KeyEvent) (err error) {
	switch {
	case h.handle_edit_keys(ev):
		h.draw_screen()
	case ev.MatchesPressOrRepeat("esc") || ev.MatchesPressOrRepeat("ctrl+c"):
		h.lp.Quit(1)
	}
	return
}

func (h *Handler) OnText(text string, from_key_event, in_bracketed_paste bool) (err error) {
	h.state.search_text += text
	return h.draw_screen()
}

func mult(a, b float64) float64 { return a * b }
func sub(a, b float64) float64  { return a - b }
func add(a, b float64) float64  { return a + b }
func div(a, b float64) float64  { return a / b }

func (h *Handler) set_state_from_config(conf *Config) (err error) {
	h.state = State{max_depth: int(conf.Max_depth)}
	h.state.exclude_patterns = make([]*regexp.Regexp, 0, len(conf.Exclude_directory))
	seen := map[string]*regexp.Regexp{}
	for _, x := range conf.Exclude_directory {
		if strings.HasPrefix(x, "!") {
			delete(seen, x[1:])
		} else if seen[x] == nil {
			if pat, err := regexp.Compile(x); err == nil {
				seen[x] = pat
			} else {
				return fmt.Errorf("The exclude directory pattern %#v is invalid: %w", x, err)
			}
		}
	}
	h.state.exclude_patterns = utils.Values(seen)
	fmap := map[string]func(float64, float64) float64{
		"*=": mult, "+=": add, "-=": sub, "/=": div}
	h.state.score_patterns = make([]ScorePattern, len(conf.Modify_score))
	for i, x := range conf.Modify_score {
		p, rest, _ := strings.Cut(x, " ")
		if h.state.score_patterns[i].pat, err = regexp.Compile(p); err == nil {
			op, val, _ := strings.Cut(rest, " ")
			if h.state.score_patterns[i].val, err = strconv.ParseFloat(val, 64); err != nil {
				return fmt.Errorf("The modify score value %#v is invalid: %w", val, err)
			}
			if h.state.score_patterns[i].op = fmap[op]; h.state.score_patterns[i].op == nil {
				return fmt.Errorf("The modify score operator %#v is unknown", op)
			}

		} else {
			return fmt.Errorf("The modify score pattern %#v is invalid: %w", x, err)
		}

	}
	return
}

var default_cwd string

func main(_ *cli.Command, opts *Options, args []string) (rc int, err error) {
	conf, err := load_config(opts)
	if err != nil {
		return 1, err
	}
	lp, err := loop.New()
	if err != nil {
		return 1, err
	}
	handler := Handler{lp: lp}
	if err = handler.set_state_from_config(conf); err != nil {
		return 1, err
	}
	switch len(args) {
	case 0:
		os.Getwd()
		if default_cwd, err = os.Getwd(); err != nil {
			return
		}
	case 1:
		default_cwd = args[0]
	default:
		return 1, fmt.Errorf("Can only specify one directory to search in")
	}
	lp.OnInitialize = handler.OnInitialize
	lp.OnResize = func(old, new_size loop.ScreenSize) (err error) {
		handler.init_sizes(new_size)
		return handler.draw_screen()
	}
	lp.OnKeyEvent = handler.OnKeyEvent
	lp.OnText = handler.OnText
	lp.OnWakeup = func() error { return handler.draw_screen() }
	err = lp.Run()
	if err != nil {
		return 1, err
	}
	ds := lp.DeathSignalName()
	if ds != "" {
		fmt.Println("Killed by signal: ", ds)
		lp.KillIfSignalled()
		return 1, nil
	}
	return
}

func EntryPoint(parent *cli.Command) {
	create_cmd(parent, main)
}
