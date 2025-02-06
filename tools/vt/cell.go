package vt

import (
	"fmt"
)

var _ = fmt.Print

type Cell struct {
	Ch          Ch
	Fg, Bg, Dec CellColor
	Attrs       CellAttrs
	Mc          MultiCell
}
