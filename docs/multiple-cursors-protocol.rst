The multiple cursors protocol
==============================================

.. versionadded:: 0.43.0

.. warning::
   This protocol is under public discussion in :iss:`8927`. It is subject to
   change until that discussion is completed.

Many editors support something called *multiple cursors* in which you can make
the same changes at multiple locations in a file and the editor shows you
cursors at each of the locations. In a terminal context editors typically
implement this by showing some Unicode glyph at each location instead of the
actual cursor. This is sub-optimal since actual cursors implemented by the
terminal have many niceties like smooth animation, auto adjust colors, etc. To
address this and other use cases, this protocol allows terminal programs to
request that the terminal display multiple cursors at specific locations on the
screen.

Quickstart
----------------

An example, showing how to use the protocol:

.. code-block:: sh

    # Show cursors of the same shape as the main cursor at y=4, x=5
    printf "\e[>29;2:4:5 q"
    # Show more cursors on the seventh line, of various shapes, the underline shape is shown twice
    printf "\e[>1;2:7:1 q\e[>2;2:7:3 q\e[>3;2:7:5;2:7:7 q"


The escape code to show a cursor has the following structure (ignore spaces
they are present for readability only)::

    CSI > SHAPE;CO-ORD TYPE : CO-ORDINATES ; CO-ORD TYPE : CO-ORDINATES ... TRAILER

Here ``CSI`` is the two bytes ESC (``0x1b``) and [ (``0x5b``). ``SHAPE`` can be
one of:

* ``0``: No cursor
* ``1``: Block cursor
* ``2``: Beam cursor
* ``3``: Underline cursor
* ``29``: Follow the shape of the main cursor
* ``30``: Change the color of text under extra cursors
* ``40``: Change the color of extra cursors
* ``100``: Used for querying currently set cursors

``CO-ORD TYPE`` can be one of:

* ``0``: This refers to the position of the main cursor and has no following
  co-ordinates.

* ``2``: In this case the following co-ordinates are pairs of numbers pointing
  to cells in the form ``y:x`` with the origin in the top left corner at
  ``1,1``. There can be any number of pairs, the terminal must treat each pair
  as a new location to set a cursor.

* ``4``: In this case the following co-ordinates are sets of four numbers that
  define a rectangle in the same co-ordinate system as above of the form:
  ``top:left:bottom:right``. The shape is set on every cell in the rectangle
  from the top left cell to the bottom right cell, inclusive. If no numbers
  are provided, the rectangle is the full screen. There can be any number of
  rectangles, the terminal must treat each set of four numbers as a new
  rectangle.

The sequence of ``CO-ORD TYPE : CO-ORDINATES`` can be repeated any number of
times separated by ``;``. The ``SHAPE`` will be set on the cells indicated by
each such group. For example: ``-1;2:3:4;4:5:6:7:8`` will set the shape ``-1``
at the cell ``(3, 2)`` and in the rectangle ``(6, 5)`` to ``(8, 7)`` inclusive.

Finally, the ``TRAILER`` terminates the sequence and is the bytes SPACE
(``0x20``) and q (``0x71``).

Terminals **must** ignore cells that fall outside the screen. That means, for
rectangle co-ordinates only the intersection of the rectangle with the screen
must be considered, and point co-ordinates that fall outside of the screen are
simply ignored, with no effect.

Terminals **must** ignore extra co-ordinates, that means if an odd number of
co-ordinates are specified for type ``2`` the last co-ordinate is ignored.
Similarly for type ``4`` if the number of co-ordinates is not a multiple of
four, the last ``1 <= n <= 3`` co-ordinates are ignored, as if they were not
specified.

Querying for support
-------------------------

A terminal program can query the terminal emulator for support of this
protocol by sending the escape code::

    CSI > TRAILER

In this case a supporting terminal must reply with::

    CSI > 1;2;3;29;30;40;100;101 TRAILER

Here, the list of numbers indicates the cursor shapes and other operations
the terminal supports and can be any subset of the above. No numbers
indicates the protocol is not supported. To avoid having to wait with a
timeout for a response from the terminal, the client should send this
query code immediately followed by a request for the
`primary device attributes <https://vt100.net/docs/vt510-rm/DA1.html>`_.
If the terminal responds with an answer for the device attributes without
an answer for the *query* the terminal emulator does not support this protocol at all.

Terminals **must** respond to these queries in FIFO order, so that
multiplexers that split a single screen know which split to send responses too.

Clearing previously set multi-cursors
------------------------------------------

The cursor at a cell is cleared by setting its shape to ``0``.
The most common operation is to clear all previously set multi-cursors. This is
easily done using the *rectangle* co-ordinate system above, like this::

    CSI > 0;4 TRAILER

For more precise control different co-ordinate types can be used. This is
particularly important for multiplexers that split up the screen and therefore
need to re-write these escape codes.

.. _extra_cursor_color:

Changing the color of extra cursors
---------------------------------------

In order to visually distinguish extra cursors from the main cursor, it is
possible to specify a color pair for extra cursors. Note that for performance
reasons, there is only a single color pair that all extra cursors share.
The color pair consists of the cursor color and the color for text in the cell
the cursor is on.

To change this color pair use an escape code of the form::

    CSI > WHICH ; COLOR_SPACE : COLOR_PARAMETER1 : COLOR_PARAMETER2 : ... TRAILER

Here, ``WHICH`` is ``30`` to set the color of text under the cursor and ``40``
to set the color of the cursor itself (these numbers mimic the SGR codes for
foreground and background respectively).

The ``COLOR_SPACE`` parameter sets the type of color, it can take values:

``0`` - unset color is same as for main cursor. No color parameters.
``1`` - *special* which typically means some kind of reverse video effect, see below
``2`` - sRGB color, with three color parameters, red, green and blue as numbers
from 0 to 255
``5`` - Indexed color with one color parameter which is an index into the color
table from 0 to 255

When the cursor color is set to *special* via ``40`` it means the block cursor
must be rendered with a reverse video effect where the cursor color becomes the
foreground color of the cell under the cursor and the foreground color of the
cell becomes its background color. Implementations are free to adjust these
colors to ensure suitable contrast levels. In this case the text color set by
``30`` must be ignored.

When the cursor color is not set to *special* but the text color via ``30`` is
set to special, then that means the foreground color of the cell with the
cursor must be changed to its background color for a partial reverse video
effect.

When unset, aka, set to ``0`` the cursors must be the same color as the main
cursor. In particular if the main color is using a reverse video effect, the
extra cursors must use the exact same colors as the main cursor, not the colors
of the cells they are on.

Querying for already set cursors
--------------------------------------

Programs can ask the terminal what extra cursors are currently set, by sending
the escape code::

    CSI > 100 TRAILER

The terminal must respond with **one** escape code::

    CSI > 100; SHAPE:CO-ORDINATE TYPE:CO-ORDINATES ; ... TRAILER

Here, the ``SHAPE:CO-ORDINATE TYPE:CO-ORDINATES`` block can be repeated any
number of times, separated by ``;``. This response gives the set of shapes and
positions currently active. If no cursors are currently active, there will be
no blocks, just an empty response of the form::

    CSI > 100 TRAILER

Again, terminals **must** respond in FIFO order so that multiplexers know where
to direct the responses.

Querying for extra cursor colors
-------------------------------------

Programs can ask the terminal what cursor colors are currently set, by sending
escape code::

    CSI > 101 TRAILER

The terminal must respond with **one** escape code::

    CSI > 101 ; 30 : COLOR_SPACE : COLOR_PARAMETERS ; 40 : COLOR_SPACE : COLOR_PARAMETERS TRAILER

The number and type of ``COLOR_PARAMETERS`` depends on the preceding
``COLOR_SPACE`` and can be omitted for some ``COLOR_SPACE`` values. See the
section :ref:`extra_cursor_color` for details.


Interaction with other terminal controls and state
-------------------------------------------------------

**The main cursor**
    The extra cursors must all have the same color and opacity and blink state
    as the main cursor. The main cursor's visibility must not affect the
    visibility of the extra cursors. Their visibility and shape are controlled
    only by this protocol.

**Clearing the screen**
    The escape codes used to clear the screen (`ED <https://vt100.net/docs/vt510-rm/ED.html>`__)
    with parameters 2, 3 and 22 must remove all extra cursors,
    this is so that the clear command can be used by users to clear the screen of extra cursors.

**Reset***
    This must remove all extra cursors.

**Alternate screen***
    Switching between the main and alternate screens must remove all extra
    cursors.

**Scrolling**
    The index (IND) and reverse index (RI) escape codes that cause screen
    contents to scroll into scrollback or off screen must not affect
    the extra cursors in any way. They remain at exactly the same position.
    It is up to applications to manage extra cursor positions when using these
    escape codes if needed. There are not a lot of use cases for scrolling
    extra cursors with screen content, since extra cursors are meant to be
    ephemeral and on screen only, not in scrollback. This allows terminals
    to avoid the extra overhead of adjusting positions of the extra cursors
    on every scroll.
