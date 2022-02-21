# The Sims 2 4K UI Mod

A script to upscale The Sims 2's user interface for 4K (HiDPI) displays.

> **Work In Progress / Help Wanted**
>
> The theory works, but there's a few minor visual glitches to resolve.
>
> **If you're a programmer:** I'd hugely appreciate [help with DBPF (de)compression](https://github.com/lah7/sims2-4k-ui-mod/issues?q=is%3Aissue+is%3Aopen+label%3A%22script+bug%22).
>
> **If you're a player:** Your best experience is playing in 1080p for the moment.
> If you don't mind visual glitches, feel free to try this script.
>

## About

Through the use of [graphic rules], it's easy to play The Sims 2 with high
resolutions. However, the buttons, text and interface becomes super tiny.

At time of writing, there are no 4K modifications out there. I discovered that
the modularity of the game means that by doubling the pixels for UI geometry
and the graphics, you can increase the UI density so it's comfortable for 4K
resolutions.

This mod is a script that processes UI resources and graphics from your copy of
the game, and upscales them to look good at a resolution of 3840x2160 (4K/2160p)

Other resolutions (like 1440p) might work by tweaking and running
the script on your computer.

[graphic rules]: https://simswiki.info/wiki.php?title=Graphics_Rules_(for_The_Sims_2)

## Download

There are no downloads yet, it's not polished enough.

You can download this repository to run the script if you'd like to take a
preview.

<!--
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

## Script Usage

You can use this script to upscale any game version, expansion pack, or existing
UI modification. This works by:

* Increase the font size in `FontStyle.ini`
* Processing an extracted `ui.package`
    * Use `imagemagick` to upscale the graphics
    * Double the geometry and sizes of UI elements
* Generate a new `ui.package`

### 1. Prerequisites

First things first, you'll need:

* [Python 3](https://www.python.org/) (to run this script)
* [Imagemagick](https://imagemagick.org/) (to process images)
* [SimPE](https://sourceforge.net/projects/simpe/) (to extract resources)

This script was designed on a Linux system, since [The Sims 2 works under Wine!](https://github.com/lah7/sims-2-wine-patches)
It should run on Windows, [WSL2] and Mac too, providing you have the utilities installed
and accessible in your PATH (so you can run them without typing the full path to
the executable)

[WSL2]: https://docs.microsoft.com/en-us/windows/wsl/about

**Note:** If you play an expansion pack, you'll need to run these steps once for
the base game, then repeat them all for the expansion pack used to play the game,
such as _The Sims 2 Mansion and Garden Stuff_ (Sims2EP9.exe)

### 2. Extract with SimPE

> Unfortunately, I [hit a snag] figuring out how to decompress files from the DBPF
file, so this step is manual.

[hit a snag]: https://github.com/lah7/sims-2-4k-ui-mod/issues

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

### 5. Copy into the game

Navigate to the game's UI folder, usually:

    C:\Program Files (x86)\EA Games\The Sims 2\TSData\Res\UI\

It is **strongly recommended** to backup the original `ui.package` for the game.
Simply add `.bak` to the end of the file.

Copy `output/ui.package` into this folder. As this project doesn't support
compression, this file is expected to be significantly larger.

Repeat these steps again for base game or expansion pack that you use to play the game.


## License

The scripts in this repository are licensed under GPLv3.


## Acknowledgements

Thank you to these wiki pages for documenting the UI files and DBPF format:

* <https://www.wiki.sc4devotion.com/index.php?title=UI>
* <https://www.wiki.sc4devotion.com/index.php?title=DBPF>
* <https://simswiki.info/wiki.php?title=DBPF>
* **Compression**
    * <https://simswiki.info/index.php?title=DBPF_Compression>
    * <https://simswiki.info/index.php?title=E86B1EEF>
