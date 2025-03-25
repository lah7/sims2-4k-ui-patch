<img src="assets/icon.svg" alt="Project Logo" height="96"/>


# 4K UI Patcher for The Sims 2

A patch utility to upscale The Sims 2's user interface for HiDPI (2K/4K) displays.


## About

Through the use of [graphic rules], it's easy to play The Sims 2 at high
resolutions, but the buttons, text and interface become super tiny.

There were no 4K modifications out there to fix the UI. However, I discovered
the modularity of the game files allows us to double the UI geometry and graphics,
such as fonts and various `.package` files.

This project is a patcher program to automatically upscale UI resources from your copy of the game.

[graphic rules]: https://simswiki.info/wiki.php?title=Graphics_Rules_(for_The_Sims_2)


## Does it work?

Yes, but there's [few visual UI glitches] that may degrade the gameplay experience!

If you've like to **get involved**, [check out the issues] or [report any glitches].
Some things are still misaligned or could be improved. Still a work in progress!

[few visual UI glitches]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[check out the issues]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[report any glitches]: https://github.com/lah7/sims2-4k-ui-patch/issues/new/choose


## Compatibility

This program is compatible with all copies of The Sims 2, expansions and stuff
packs for PC, and likely the Life Stories series too.
[The Sims™ 2 Legacy Collection] and [The Sims™ 2: Super Collection] haven't
been tested.

Any downloads or custom content that alters the user interface from your
The Sims 2 save folder or game installation folder are not yet patched by
this program. It is recommended to disable/uninstall these mods until this is
integrated, but you can hack the code to include them[<sup>[1]</sup>](https://github.com/lah7/sims2-4k-ui-patch/issues/46#issuecomment-2289635309)

It seems that [The Sims™ 2 Legacy Collection] (2025 re-release) is scaling
the UI using pixel resolution scaling, but under the hood, it's still at
its original scaling. Since our patcher modifies the geometry and assets,
ours is native 4K UI, providing much crisper fonts and Sim detail.

[The Sims™ 2 Legacy Collection]: https://store.steampowered.com/app/3314070
[The Sims™ 2: Super Collection]: https://apps.apple.com/us/app/the-sims-2-super-collection/id883782620?mt=12


## Instructions

Your game files are always backed up, so you can revert without reinstalling the game,
or to repatch later using a newer version of this program with fixes and improvements.

While patching, you should have **at least 2 GB of RAM free**. It may take
a while to complete, depending on the performance of your CPU.

The program automatically checks this repository for an update, to ensure you have the latest version.


### Windows

1. Download the latest `windows-x64` asset from the [Releases] page.
2. Extract the contents and run `sims2-4k-ui-patcher.exe`.
   * You'll need to run as administrator to modify the game files.
   * If you don't want to do that, change the permissions of your EA GAMES directory, usually at `C:\Program Files (x86)\EA GAMES`.
3. Click "Patch"!

To run the program, you may need to install [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).


### Linux

For users who play The Sims 2 under the Wine/Proton compatibility layer. [It works well with DXVK!](https://github.com/lah7/sims2-wine-patches/blob/master/README-D9VK.md)

1. Download the latest `linux-x64` asset from the [Releases] page.
2. Extract the contents and run `./sims2-4k-ui-patcher`.
    * You may need to mark it as executable first (usually by right clicking → Properties → Permissions tab).
3. Find your "EA GAMES" directory, e.g. a wine prefix at `~/.wine/drive_c/Program Files (x86)/EA GAMES`.
4. Click "Patch"!


### macOS

We don't have a pre-built binary for macOS, but you can run the Python script directly. See [Development](#development) for instructions.

This patch program will work fine if you play the game under a Wine compatibility layer.
However, if you purchased the [The Sims™ 2: Super Collection],
we don't know whether files are exposed in a way that is compatible with this program. Please let us know!


[Releases]: https://github.com/lah7/sims2-4k-ui-patch/releases/latest


## Development

This project is written in Python. To start hacking, clone this repository
and set up a [virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
to install [requirements.txt](requirements.txt).

Python 3.10 is the minimum supported version.

For Windows, [install Python 3.13](https://www.python.org/downloads/windows/), and run:

    python -m venv venv
    venv\Scripts\activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python sims2_4k_ui_patcher.py

For Linux, your distribution likely already has Python 3 installed:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py

Alternatively, you could use your system's interpreter by installing packages
that provides the dependencies (names vary by distro):

    python-requests python-pillow python-pyqt6

For macOS, [install Python 3.13](https://www.python.org/downloads/macos/), and run:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py


### Tests

Unit tests check everything is in working order.

You'll need to copy a file from The Sims 2 University into the `tests/files` folder:

    724723ddc5b020a55bdefc60a7cf1304    The Sims 2 University/TSData/Res/UI/ui.package

**File not included.** With this file present, you can locally run the tests:

    python -m unittest discover ./tests/

This checks the modules and compression procedures are working correctly.


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
