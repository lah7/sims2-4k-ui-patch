# The Sims 2 4K UI Mod

A script to upscale The Sims 2's user interface for 4K (HiDPI) displays.

## About

Through the use of [graphic rules], it's easy to play The Sims 2 at high
resolutions, but the buttons, text and interface become super tiny.

At time of writing, there are no 4K modifications out there to fix the UI.
I discovered that the game's modularity (`ui.package`) allows us to double
the UI geometry and graphics.

This "mod" is a script that upscales UI resources and graphics from your copy of
the game. Other resolutions (like 1440p) could work too by tweaking the script.

[graphic rules]: https://simswiki.info/wiki.php?title=Graphics_Rules_(for_The_Sims_2)


## Work in Progress...

The theory works, but there's a few minor visual glitches that make the game
feel buggy or makes it difficult to play.

The patcher tool is currently being worked on. Hang tight!

**If you're a player:** Your best experience is playing in 1080p for now.
If you don't mind [visual glitches](https://github.com/lah7/sims2-4k-ui-mod/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22), feel free to try this script.

**If you've like to get involved:**

* [Investigate why some assets are misaligned or didn't scale](https://github.com/lah7/sims2-4k-ui-mod/issues?q=is%3Aissue+is%3Aopen+label%3A%22visual+bug%22)


<!--
## Download

For your convenience, you can download upscaled package file from the [Releases]
page, assuming the latest patches for the game.

There are two parts:

* Place the .package file for **both** the base game, **and** the expansion pack you play
into your `Documents\EA Games\The Sims 2\Downloads` folder.
* Place `FontStyle.ini` into the base game's `C:\Program Files (x86)\EA Games\The Sims 2\TSData\Res\UI\Fonts\FontStyle.ini` folder.
  * It's recommended to back up this file first (add `.bak` at the end)

Note that any other mods that modify the user interface may cause a mix of
normal and high density interface.

[Releases]: https://github.com/lah7/sims-2-4k-ui-mod/releases
-->

## Tests

Unit tests are an optional check everything is in working order.

You'll need to copy a file from The Sims 2 University into the `tests` folder:

    724723ddc5b020a55bdefc60a7cf1304    The Sims 2 University/TSData/Res/UI/ui.package

_File not included._ With this file, you can run:

    python -m unittest discover ./tests/

This tests the package read, write and compression procedures are working correctly.


## Script Usage

You can use this script to upscale any game version, expansion pack, even if
you have existing UI modifications installed. This works by:

* Increasing the font size in `FontStyle.ini`
* Extract `ui.package` and then:
    * Use `imagemagick` to upscale the graphics
    * Double the geometry and size for UI elements
* Generate a new `ui.package` (uncompressed, see [#2])

[#2]: https://github.com/lah7/sims2-4k-ui-mod/issues/2

### 1. Prerequisites

First things first, you'll need:

* [Python 3](https://www.python.org/) (to run this script)
* [Imagemagick](https://imagemagick.org/) (to process images)
* [SimPE](https://sourceforge.net/projects/simpe/) (to extract resources)

This script was designed on a Linux system, since [The Sims 2 works under Wine!](https://github.com/lah7/sims-2-wine-patches)
It should run on Windows, [WSL2] and Mac too, providing you have the utilities installed
and are accessible in your PATH (so you can run them without typing the full path to
the executable)

[WSL2]: https://docs.microsoft.com/en-us/windows/wsl/about

**Note:** If you play an expansion pack, you'll need to run these steps once for
the base game, then repeat them all for the expansion pack used to play the game,
such as _The Sims 2 Mansion and Garden Stuff_ (Sims2EP9.exe)

### 2. Extract with SimPE

> Unfortunately, this step is manual as I hit a snag [(#1)] figuring out how to decompress files without needing SimPE.

[(#1)]: https://github.com/lah7/sims2-4k-ui-mod/issues/1

1. In SimPE, open the game's `TSData/Res/UI/ui.package` (from the game's installation folder)
1. Select "jpg/tga/png Image" in the resource tree, select all and extract to the **input** folder.
1. Repeat step 2, but for "UI Data" too.
1. Repeat step 2, but for "Accelerator Key Definitions" too.

### 3. Copy FontStyle.ini

From the base game's installation folder, copy `TSData\Res\UI\Fonts\FontStyle.ini` into
the **input** folder.

### 4. Run the script

    python3 ./sims2-4k-ui-converter.py

This will process the files and produce a new `ui.package`.

For more parameters, add `--help` at the end. For example, you can choose the
directory to use while processing (like a RAM Disk), otherwise, the default will
use `input`, `temp` and `output` directories in this folder.

### 5. Copy into the game

1. Navigate to the game's UI folder, usually:

        C:\Program Files (x86)\EA Games\The Sims 2\TSData\Res\UI\

    It is **strongly recommended** to backup the original `ui.package` for the game
(like adding `.bak` to the end of the file)

2. Copy `output/ui.package` into this folder. As the script doesn't support
compression yet [(#2)], this file is expected to be significantly larger.

[(#2)]: https://github.com/lah7/sims2-4k-ui-mod/issues/2

3. Repeat these steps again for base game or expansion pack that you use to play the game.


## License

The scripts in this repository are licensed under GPLv3.


## Acknowledgements

If you wish to let the wider Sims community know, be sure to leave a link
to this repository!

Thank you to these wiki pages for documenting the UI files and DBPF format:

* <https://www.wiki.sc4devotion.com/index.php?title=UI>
* <https://www.wiki.sc4devotion.com/index.php?title=DBPF>
* <https://simswiki.info/wiki.php?title=DBPF>
* **Compression**
    * <https://simswiki.info/index.php?title=DBPF_Compression>
    * <https://simswiki.info/index.php?title=E86B1EEF>
