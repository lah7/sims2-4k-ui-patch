
# 4K UI Patcher for The Sims 2

![Project Icon](assets/icon.svg)

A patch utility to upscale The Sims 2's user interface for HiDPI (2K/4K) displays.


## About

Through the use of [graphic rules], it's easy to play The Sims 2
at high resolutions, but the buttons, text and interface become super tiny.
User interfaces from the 2000s have no concept of high density displays.

This project is a patch utility to upscale the UI resources from your copy of
the game to look better on high density displays.

When this project started, there were no 4K modifications out there to fix the UI.
I discovered the modularity of the game files enable us to double the UI geometry,
graphics, font sizes in various package files.

[graphic rules]: https://simswiki.info/wiki.php?title=Graphics_Rules_(for_The_Sims_2)


## Does it work?

**Yes!** This is supported for the retail disc and Ultimate Collection (Origin) releases.
There are some [imperfections] and known issues, like the [small pie menus](https://github.com/lah7/sims2-4k-ui-patch/issues/20)
when a lot of options are displayed.

If you spot anything wrong, please [check out the issues] and report any [new bugs].

[imperfections]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[check out the issues]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[new bugs]: https://github.com/lah7/sims2-4k-ui-patch/issues/new/choose


## What about the Legacy Collection?

[The Sims™ 2 Legacy Collection] (2025 re-release) automatically scales the UI
using pixel resolution scaling based on the current resolution. This can cause
the UI to look slightly blurry. Under the hood, the UI data is still internally
the same.

If you wish to use this mod for improved sharpness and clarity, you'll need to
disable the UI scaling feature which was not present in the older releases.
Unfortunately, I don't know a way. If you know, please [let us know]!

[let us know]: https://github.com/lah7/sims2-4k-ui-patch/issues

The UI scale factor is configurable in this file:

    The Sims 2 Legacy Collection\EP9\TSData\Res\Config\Graphics Rules.sgr

There is a line determining the scale. However, `1` is still too large.

    uintProp uiScaleFactor 1

In order to use this mod with the Legacy Collection, you need to find a way to
force the game to render the UI layer at its original geometry (100%) at 2160p,
which should look tiny on a 4K screen. This may not be possible with this
game's newer rendering engine.

Patching will double the density and make the UI look huge. As a result,
the Legacy Collection release is not supported by this project for the time being.


## Compatibility

This program is compatible with all original copies of The Sims 2, expansions and
stuff packs for PC, and the Life Stories series too.

[The Sims™ 2: Super Collection] (for Mac) haven't been tested. Do let us know if
you have a copy and would like to help investigate!

[The Sims™ 2 Legacy Collection] is not recommended right now, [see above.](#what-about-the-legacy-collection)

Any downloads, mods or custom content that alters the user interface from your
The Sims 2 save folder or game installation folder are **not yet detected** by
this program. They will likely break the UI or crash the game. Either:

* Remove these UI mods (e.g. Clean UI, Starship UI), for now.
* [Hack this code](https://github.com/lah7/sims2-4k-ui-patch/blob/0d439a6cf8483402b5915d0ed5e6ee7c51aa346b/sims2patcher/gamefile.py#L35) to include them (your mileage may vary)
* Wait for a newer version which will improve support for UI mods.

[The Sims™ 2 Legacy Collection]: https://store.steampowered.com/app/3314070
[The Sims™ 2: Super Collection]: https://apps.apple.com/us/app/the-sims-2-super-collection/id883782620?mt=12


## Instructions

Your game files are always backed up, so you can revert without reinstalling the game,
or to repatch later with a newer version of this program containing fixes and improvements.

By default, the patcher utilises as much CPU as possible to speed up the patching process.
**About 2 GB of RAM free** is a recommended, but more may be needed if your CPU has many threads.
You can change the slider if you wish to limit the CPU usage.

The program automatically checks this repository for an update.


### Windows

1. Download the [latest release] for Windows from the [Releases] page.
2. Extract the contents and run `sims2-4k-ui-patcher.exe`.
   * You'll need to run as administrator to modify the game files.
   * If you don't want to do that, change the permissions of the folder containing The Sims 2 and its expansions.

To run the program, you may need to install [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).


### Linux

For users who play The Sims 2 under the Wine+DXVK or Proton compatibility layer.

1. Download the [latest release] for Linux from the [Releases] page.
2. Extract the contents and run `./sims2-4k-ui-patcher`.
    * You may need to mark it as executable first (usually by right clicking → Properties → Permissions tab).

Alternately, see [Development](#development) for running from the repository.
This will provide a better desktop integration.


### macOS

We don't have a pre-built binary for macOS, but you can run the Python script directly. See [Development](#development) for instructions.

This patch program will work fine if you play the game under a Wine compatibility layer.
However, if you purchased the [The Sims™ 2: Super Collection],
we don't know whether files are exposed in a way that is compatible with this program. Please let us know!


[latest release]: https://github.com/lah7/sims2-4k-ui-patch/releases/latest
[Releases]: https://github.com/lah7/sims2-4k-ui-patch/releases


## Development

This project is written in Python. To start hacking, clone this repository
and set up a [virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
to install [requirements.txt](requirements.txt).

Python 3.10 is the minimum supported version.

**For Windows,** [install Python 3.13](https://www.python.org/downloads/windows/), and run:

    python -m venv venv
    venv\Scripts\activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python sims2_4k_ui_patcher.py

**For Linux,** your distribution likely already has Python 3 installed:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py

Alternatively, you could use your system's interpreter by installing packages
that provides the dependencies (names vary by distro):

    python-requests python-pillow python-pyqt6

**For macOS,** [install Python 3.13](https://www.python.org/downloads/macos/), and run:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py


### Tests

Unit tests check everything is in working order.

You'll need to copy a file from The Sims 2 University (EP1) into the `tests/files` folder:

    724723ddc5b020a55bdefc60a7cf1304    The Sims 2 University/TSData/Res/UI/ui.package

**File not included.** With this file present, you can locally run the tests:

    python -m unittest discover ./tests/

This checks the modules and compression procedures are working correctly.


## Game UI Tips

The game has its own UI debugger built-in. To activate, enable testing cheats
globally by adding a line to your latest game's `TSData/Res/Config/globalProps.xml` file.

    <AnyBoolean key="testingCheatsEnabled" type="0xcba908e1">true</AnyBoolean>'

* <kbd>CTRL</kbd>+<kbd>U</kbd> opens the UI browser. Click the "?" button for more shortcuts and hints.
* <kbd>CTRL</kbd>+<kbd>SHIFT</kbd>+<kbd>U</kbd> reloads the UI.


## License

[GNU General Public License v3](LICENSE) (GPLv3)


## Acknowledgements

If you wish to let the wider Sims community know,
be sure to leave them a link to this repository!

**Thank you to the following:**

These wiki pages for documenting the UI, DBPF and compression format:

* <https://www.wiki.sc4devotion.com/index.php?title=UI>
* <https://www.wiki.sc4devotion.com/index.php?title=DBPF>
* <https://simswiki.info/wiki.php?title=DBPF>
* <https://simswiki.info/index.php?title=DBPF_Compression>
* <https://simswiki.info/index.php?title=E86B1EEF>
* <https://modthesims.info/wiki.php?title=List_of_Sims_2_Formats_by_Name>
* <https://simswiki.info/wiki.php?title=List_of_Sims_2_Formats_by_Name>

This implementation of the QFS compression algorithm, which we ported to Python:

* https://github.com/memo33/jDBPFX (Java, GPLv3)

And [contributors](https://github.com/lah7/sims2-4k-ui-patch/graphs/contributors) who committed fixes!
