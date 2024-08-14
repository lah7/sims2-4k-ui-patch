<img src="assets/icon.svg" alt="Project Logo" height="96"/>


# 4K UI Patcher for The Sims 2

A patch utility to upscale The Sims 2's user interface for 4K (HiDPI) displays.


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

If you've like to **get involved**, [check out the issues] or [report any issues]. Some things are still misaligned or could be improved.

[few visual UI glitches]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[check out the issues]: https://github.com/lah7/sims2-4k-ui-patch/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22
[report any issues]: https://github.com/lah7/sims2-4k-ui-patch/issues/new/choose


## Instructions

Your game files are always backed up, so you can revert without reinstalling the game,
or to repatch later using a newer version of this program with fixes and improvements.

While patching, you should have **at least 2 GB of RAM free**. It may take
a while to complete, depending on the single core performance of your CPU.

The game originally compressed its package files with QFS compression.
You can optionally turn this on, but it will take longer to complete.
Without compression, a retail game with all expansions and backup files
would use an **additional 7.7 GiB of disk space**.

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
    * You may need to mark it as executable first (e.g. right click -> Properties -> Permissions tab).
3. Find your "EA GAMES" directory, e.g. a wine prefix at `~/.wine/drive_c/Program Files (x86)/EA GAMES`.
4. Click "Patch"!

Ironically, the patcher interface (built with TK) may not scale well on a 4K display.


### macOS

We don't have a pre-built binary for macOS, but you can run the Python script directly. See [Development](#development) for instructions.

This patch program will work fine if you play the game under a Wine compatibility layer.

If you purchased the [The Sims™ 2: Super Collection](https://apps.apple.com/us/app/the-sims-2-super-collection/id883782620?mt=12),
we don't know whether files are exposed in a way that is compatible with this program. Please let us know!


[Releases]: https://github.com/lah7/sims2-4k-ui-patch/releases/latest


## Compatibility

This program is compatible with all copies of The Sims 2, expansions and stuff
packs for PC.

Any downloads or custom content that alters the user interface or modifies
graphical interface elements via your The Sims 2 save folder are not patched by
this program. Using such mods may result in mixed UI scaling.

However, any existing UI modifications that are directly made to the game's
original files (like `TSData/Res/UI/ui.package`) will be transparently patched with this program.


## Development

This project is written in Python. To start hacking, clone this repository
and set up a [virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
to install [requirements.txt](requirements.txt).

For Windows, [install Python 3](https://www.python.org/downloads/windows/), and run:

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

For macOS, [install Python 3](https://www.python.org/downloads/macos/), and run:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py


### Tests

Unit tests check everything is in working order.

You'll need to copy a file from The Sims 2 University into the `tests/files` folder:

    724723ddc5b020a55bdefc60a7cf1304    The Sims 2 University/TSData/Res/UI/ui.package

**File not included.** With this file present, run:

    python -m unittest discover ./tests/

This tests the package read, write and compression procedures are working correctly.


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

This implementation of the QFS compression algorithm, which we ported to Python:

* https://github.com/memo33/jDBPFX (Java, GPLv3)

And [contributors](https://github.com/lah7/sims2-4k-ui-patch/graphs/contributors) who committed fixes!
