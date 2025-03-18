%global gomodulesmode GO111MODULE=on
%global goipath kitty

%ifarch %{x86_64} %{arm64}
%bcond test 1
%else
%bcond test 0
%endif

Name:           kitty
Version:        {{{git_custom_version}}}
Release:        {{{git_custom_release}}}%{?dist}
Summary:        Cross-platform, fast, feature full, GPU based terminal emulator

# GPL-3.0-only: kitty
# Zlib: glfw
# LGPL-2.1-or-later: kitty/iqsort.h
# MIT: docs/_static/custom.css, shell-integration/ssh/bootstrap-utils.sh
# MIT AND CC0-1.0: simde
# CC0-1.0: 3rdparty/ringbuf
# BSD-2-Clause: 3rdparty/base64
# MIT: NerdFontsSymbolsOnly
# MIT: 3rdparty/verstable.h
License:        GPL-3.0-only AND LGPL-2.1-or-later AND Zlib AND (MIT AND CC0-1.0) AND BSD-2-Clause AND CC0-1.0 AND MIT
URL:            https://sw.kovidgoyal.net/kitty
Source0:        {{{git_repo_pack}}}
Source4:        go-vendor-tools.toml
# Add AppData manifest file
# * https://github.com/kovidgoyal/kitty/pull/2088
Source5:        https://raw.githubusercontent.com/kovidgoyal/kitty/46c0951751444e4f4994008f0d2dcb41e49389f4/kitty/data/%{name}.appdata.xml
Source6:        https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/NerdFontsSymbolsOnly.tar.xz

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:    %{ix86}

BuildRequires:  golang >= 1.23.0
BuildRequires:  go-rpm-macros
BuildRequires:  go-vendor-tools

BuildRequires:  git
BuildRequires:  gnupg2
BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  lcms2-devel
BuildRequires:  libappstream-glib
BuildRequires:  ncurses
BuildRequires:  python3-devel >= 3.10
BuildRequires:  wayland-devel
BuildRequires:  simde-static

BuildRequires:  pkgconfig(cairo-fc)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(harfbuzz) >= 2.2
BuildRequires:  pkgconfig(libcanberra)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libxxhash)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xcursor)
BuildRequires:  pkgconfig(xi)
BuildRequires:  pkgconfig(xinerama)
BuildRequires:  pkgconfig(xkbcommon-x11)
BuildRequires:  pkgconfig(xrandr)
BuildRequires:  pkgconfig(zlib)
BuildRequires:  pkgconfig(libcrypto)

%if %{with test}
# For tests:
BuildRequires:  fish
BuildRequires:  glibc-common
BuildRequires:  openssh-clients
BuildRequires:  ripgrep
BuildRequires:  zsh
BuildRequires:  python3dist(pillow)
%endif

Requires:       python3%{?_isa}
Requires:       hicolor-icon-theme

Obsoletes:      %{name}-bash-integration < 0.28.1-3
Obsoletes:      %{name}-fish-integration < 0.28.1-3
Provides:       %{name}-bash-integration = %{version}-%{release}
Provides:       %{name}-fish-integration = %{version}-%{release}

# Terminfo file has been split from the main program and is required for use
# without errors. It has been separated to support SSH into remote machines using
# kitty as per the maintainers suggestion. Install the terminfo file on the remote
# machine.
Requires:       %{name}-terminfo = %{version}-%{release}
Requires:       %{name}-shell-integration = %{version}-%{release}
Requires:       %{name}-kitten%{?_isa} = %{version}-%{release}

# For the "Hyperlinked grep" feature
Recommends:     ripgrep

# Very weak dependencies, these are required to enable all features of kitty's
# "kittens" functions install separately
Suggests:       ImageMagick%{?_isa}

Provides:       bundled(font(SymbolsNerdFontMono)) = 3.3.0
Provides:       bundled(font(SymbolsNerdFont)) = 3.3.0

Provides:       bundled(Verstable) = 2.1.1
# modified version of https://github.com/dhess/c-ringbuf
Provides:       bundled(c-ringbuf)
# heavily modified
Provides:       bundled(glfw)
# https://github.com/aklomp/base64
Provides:       bundled(base64simd)

%description
- Offloads rendering to the GPU for lower system load and buttery smooth
  scrolling. Uses threaded rendering to minimize input latency.

- Supports all modern terminal features: graphics (images), unicode, true-color,
  OpenType ligatures, mouse protocol, focus tracking, bracketed paste and
  several new terminal protocol extensions.

- Supports tiling multiple terminal windows side by side in different layouts
  without needing to use an extra program like tmux.

- Can be controlled from scripts or the shell prompt, even over SSH.

- Has a framework for Kittens, small terminal programs that can be used to
  extend kitty's functionality. For example, they are used for Unicode input,
  Hints and Side-by-side diff.

- Supports startup sessions which allow you to specify the window/tab layout,
  working directories and programs to run on startup.

- Cross-platform: kitty works on Linux and macOS, but because it uses only
  OpenGL for rendering, it should be trivial to port to other Unix-like
  platforms.

- Allows you to open the scrollback buffer in a separate window using arbitrary
  programs of your choice. This is useful for browsing the history comfortably
  in a pager or editor.

- Has multiple copy/paste buffers, like vim.


# terminfo package
%package        terminfo
Summary:        The terminfo file for Kitty Terminal
License:        GPL-3.0-only
BuildArch:      noarch

Requires:       ncurses-base

%description    terminfo
Cross-platform, fast, feature full, GPU based terminal emulator.

The terminfo file for Kitty Terminal.

# shell-integration package
%package        shell-integration
Summary:        Shell integration scripts for %{name}
License:        GPL-3.0-only AND MIT
BuildArch:      noarch

Recommends:     %{name}-kitten

%description    shell-integration
%{summary}.

# kitten package
%package        kitten
Summary:        The kitten executable
# Generated with go-vendor-tools
%global kitten_license Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND GPL-3.0-only AND MIT AND MPL-2.0
License:        %{kitten_license}

%description    kitten
%{summary}.

%package        doc
Summary:        Documentation for %{name}
License:        GPL-3.0-only AND MIT
BuildArch:      noarch

BuildRequires:  python3dist(sphinx)
%if ! 0%{?epel}
BuildRequires:  python3dist(sphinx-copybutton)
BuildRequires:  python3dist(sphinx-inline-tabs)
BuildRequires:  python3dist(sphinxext-opengraph)
%endif

%description    doc
This package contains the documentation for %{name}.


%prep
{{{git_repo_setup_macro}}}

go_vendor_archive create --config ./go-vendor-tools.toml ./ -O kitty-vendor.tar.xz
tar -xf kitty-vendor.tar.xz

mkdir fonts
tar -xf %{SOURCE6} -C fonts

# Changing sphinx theme to classic
sed "s/html_theme = 'furo'/html_theme = 'classic'/" -i docs/conf.py

# Replace python shebangs to make them compatible with fedora
find -type f -name "*.py" -exec sed -e 's|/usr/bin/env python3|%{python3}|g'    \
                                    -e 's|/usr/bin/env python|%{python3}|g'     \
                                    -e 's|/usr/bin/env -S kitty|/usr/bin/kitty|g' \
                                    -i "{}" \;

find -type f ! -executable -name "*.py" -exec sed -i '1{\@^#!%{python3}@d}' "{}" \;

%generate_buildrequires
%go_vendor_license_buildrequires -c %{S:4}

%build
%set_build_flags
%{python3} setup.py linux-package   \
    --libdir-name=%{_lib}           \
    --update-check-interval=0       \
    --verbose                       \
    --skip-building-kitten          \
    --ignore-compiler-warnings      \
    %{nil}

unset LDFLAGS
%gobuild -o _build/bin/kitten ./tools/cmd

# build docs
export KITTEN_EXE_FOR_DOCS=$(pwd)/_build/bin/kitten
make docs

%install
%go_vendor_license_install -c %{S:4}

# rpmlint fixes
find linux-package/%{_lib}/%{name}/shell-integration -type f ! -executable -exec sed -r -i '1{\@^#!/bin/(fish|zsh|sh|bash)@d}' "{}" \;

# copy_man_pages()
mansrc="docs/_build/man"
mandir="linux-package/share/man"
lvls="15"
shopt -s nullglob
for (( i=0; i<${#lvls}; i++ )); do
    lvl="${lvls:i:1}"
    manpgs=("$mansrc"/*."$lvl")
    if [[ -n "${manpgs[@]}" ]]; then
        manlvl="$mandir"/man"$lvl"
        mkdir -p "$manlvl"
        cp "${manpgs[@]}" "$manlvl"
    fi
done
shopt -u nullglob

# copy_html_docs()
docsrc="docs/_build/html"
docdir="linux-package/share/doc/%{name}/html"
mkdir -p "$docdir"
shopt -s dotglob
cp -r "$docsrc"/* "$docdir"
shopt -u dotglob

cp -a linux-package/. %{buildroot}%{_prefix}
install -m0755 -Dp _build/bin/kitten %{buildroot}%{_bindir}/kitten

install -m0644 -Dp %{SOURCE5} %{buildroot}%{_metainfodir}/%{name}.appdata.xml

# rpmlint fixes
rm %{buildroot}%{_datadir}/doc/%{name}/html/.buildinfo \
   %{buildroot}%{_datadir}/doc/%{name}/html/.nojekyll


%check
%go_vendor_license_check -c %{S:4} %{kitten_license}
%if %{with test}
%if 0%{?epel}
sed '/def test_ssh_leading_data/a \
\        self.skipTest("Skipping a failing test")' -i kitty_tests/ssh.py
%endif
export %{gomodulesmode}
# Some tests ignores PATH env...
mkdir -p kitty/launcher
ln -s %{buildroot}%{_bindir}/%{name} kitty/launcher/
export PATH=%{buildroot}%{_bindir}:$PATH
export PYTHONPATH=$(pwd)
%{python3} setup.py test          \
    --prefix=%{buildroot}%{_prefix}
%endif

appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.xml
desktop-file-validate %{buildroot}/%{_datadir}/applications/*.desktop


%files
%license LICENSE
%{_bindir}/%{name}
%{_datadir}/applications/*.desktop
%{_datadir}/icons/hicolor/*/*/*.{png,svg}
%{_libdir}/%{name}/
%exclude %{_libdir}/%{name}/shell-integration
%{_mandir}/man{1,5}/*.{1,5}*
%{_metainfodir}/*.xml

%files kitten -f %{go_vendor_license_filelist}
%license vendor/modules.txt
%license LICENSE
%{_bindir}/kitten

%files terminfo
%license LICENSE
%{_datadir}/terminfo/x/xterm-%{name}

%files shell-integration
%license LICENSE
%{_libdir}/%{name}/shell-integration/

%files doc
%license LICENSE
%doc CONTRIBUTING.md CHANGELOG.rst INSTALL.md
%{_docdir}/%{name}/html/
%dir %{_docdir}/%{name}


%changelog
* {{{git_custom_date}}} Arvin Verain <arvinverain@proton.me> - {{{git_custom_version}}}-{{{git_custom_release}}}
- Nightly build from git master
