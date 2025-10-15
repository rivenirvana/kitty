module github.com/kovidgoyal/kitty

go 1.24.0

toolchain go1.24.6

require (
	github.com/ALTree/bigfloat v0.2.0
	github.com/alecthomas/chroma/v2 v2.20.0
	github.com/bmatcuk/doublestar/v4 v4.9.1
	github.com/dlclark/regexp2 v1.11.5
	github.com/google/go-cmp v0.7.0
	github.com/google/uuid v1.6.0
	github.com/kovidgoyal/dbus v0.0.0-20250519011319-e811c41c0bc1
	github.com/kovidgoyal/exiffix v0.0.0-20250919160812-dbef770c2032
	github.com/kovidgoyal/go-parallel v1.0.1
	github.com/kovidgoyal/imaging v1.7.2
	github.com/seancfoley/ipaddress-go v1.7.1
	github.com/shirou/gopsutil/v3 v3.24.5
	github.com/zeebo/xxh3 v1.0.2
	golang.org/x/exp v0.0.0-20230801115018-d63ba01acd4b
	golang.org/x/image v0.32.0
	golang.org/x/sys v0.37.0
	golang.org/x/text v0.30.0
	howett.net/plist v1.0.1
)

// Uncomment the following to use a local checkout of dbus
// replace github.com/kovidgoyal/dbus => ../dbus

// Uncomment the following to use a local checkout of imaging
// replace github.com/kovidgoyal/imaging => ../imaging

require (
	github.com/go-ole/go-ole v1.2.6 // indirect
	github.com/klauspost/cpuid/v2 v2.2.5 // indirect
	github.com/lufia/plan9stats v0.0.0-20230326075908-cb1d2100619a // indirect
	github.com/power-devops/perfstat v0.0.0-20221212215047-62379fc7944b // indirect
	github.com/rwcarlsen/goexif v0.0.0-20190401172101-9e8deecbddbd // indirect
	github.com/seancfoley/bintree v1.3.1 // indirect
	github.com/shoenig/go-m1cpu v0.1.7 // indirect
	github.com/tklauser/go-sysconf v0.3.12 // indirect
	github.com/tklauser/numcpus v0.6.1 // indirect
	github.com/yusufpapurcu/wmi v1.2.4 // indirect
)
