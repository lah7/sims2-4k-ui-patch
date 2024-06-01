# 4K UI Patch for The Sims 2

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

Your game files will always be backed up, so you can revert without reinstalling the game,
or to repatch later using a newer version of this program with fixes and improvements.

While patching, you should have **at least 2 GB of RAM free**. It may take
a while to complete, depending on the single core performance of your CPU.

At the moment, the packages are **not compressed**.
An **additional 7.7 GiB of disk space** is required
(assuming a retail game with all expansions).

The program automatically checks this repository for an update, to ensure you have the latest version.


### Windows

1. Download the latest version from the [Releases] page.
2. Extract the contents and run `sims2-4k-ui-patcher.exe`.
   * You'll need to run as administrator to modify the game files.
   * If you don't want to do that, change the permissions of your EA GAMES directory, usually at `C:\Program Files (x86)\EA GAMES`.
3. Click "Patch"!


### Linux/macOS (Wine/Proton)

[The Sims 2 is playable under Wine!] For the best patching performance,
run this patch program natively under Python.

1. Download the [latest ZIP of this repository](https://github.com/lah7/sims2-4k-ui-patch/archive/refs/heads/master.zip).

2. Extract the contents and run:

       python -m venv venv
       source venv/bin/activate
       pip install -r requirements.txt
       python sims2-4k-ui-patcher.py

Ironically, the patcher interface (built with TK) may not scale well on a 4K display.

[Releases]: https://github.com/lah7/sims2-4k-ui-patch/releases/latest
[The Sims 2 is playable under Wine!]: https://github.com/lah7/sims-2-wine-patches


## Compatibility

This program is compatible with all copies of The Sims 2, expansions and stuff
packs for PC.

Any downloads or custom content that creates custom user interfaces or modifies
graphical interface elements via your The Sims 2 save folder are not patched by
this program. Using such mods may result in mixed UI scaling.

However, any existing UI modifications that were made in the game's installation
folder (like `TSData/Res/UI/ui.package`) are compatible with this program.

**On a Mac?** We don't know whether [The Sims™ 2: Super Collection](https://apps.apple.com/us/app/the-sims-2-super-collection/id883782620?mt=12)
is compatible with this program. Please let us know!


## Development

This project is written in Python. To start hacking, clone this repository
 and set up a [virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
 to install [requirements.txt](requirements.txt).

For Windows, [install Python], and run:

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    python sims2_4k_ui_patcher.py

For macOS/Linux instructions, [see above](#linuxmacos-wineproton).

[install Python]: https://www.python.org/downloads/windows/

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

Thank you to these wiki pages for documenting the UI files and DBPF format:

* <https://www.wiki.sc4devotion.com/index.php?title=UI>
* <https://www.wiki.sc4devotion.com/index.php?title=DBPF>
* <https://simswiki.info/wiki.php?title=DBPF>
* **Compression**
    * <https://simswiki.info/index.php?title=DBPF_Compression>
    * <https://simswiki.info/index.php?title=E86B1EEF>

Thank you to [contributors](https://github.com/lah7/sims2-4k-ui-patch/graphs/contributors) who committed fixes!
