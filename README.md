# The Sims 2 4K UI Mod

A script to upscale The Sims 2's user interface for 4K (HiDPI) displays.

## The Problem

Through the use of [graphic rules], it's easy to play The Sims 2 with high
resolutions. However, the buttons, text and interface is super tiny.

Not anymore! This repository contains a script that will unpack UI resources
and graphics from the game, and upscale them to look good on a 3840x2160 resolution.
This might work for other resolutions (like 1440p) too by tweaking and running
the script on your computer.

[graphic rules]: https://simswiki.info/wiki.php?title=Graphics_Rules_(for_The_Sims_2)


## Script Usage

You can use this script to upscale any game version, expansion pack, or existing
UI modification. This works by:

* Increasing the font size in `FontStyle.ini`
* Extracting `ui.package`
    * Upscale the graphics using `imagemagick`
    * Double the geometry and sizes of UI elements
* Generating a new `ui.package`

### 1. Prerequisites

First things first, you'll need:

* [Python 3](https://www.python.org/) (to run this script)
* [Imagemagick](https://imagemagick.org/) (to process images)
* [SimPE](https://sourceforge.net/projects/simpe/) (to extract resources)

This script was designed on a Linux system, since [The Sims 2 works under Wine!](https://github.com/lah7/sims-2-wine-patches).
It should run on Windows, [WSL2] and Mac too, providing you have the utilities installed
and accessible in your PATH (so you can run them without typing the full path to
the executable)

[WSL2]: https://docs.microsoft.com/en-us/windows/wsl/about

### 2. Extract with SimPE

1. In SimPE, open the base game's `TSData/Res/UI/ui.package` (from the game's installation folder)
1. Select "jpg/tga/png Image" in the resource tree, select all and extract to the **input** folder.
1. Repeat step 2, but for "UI Data" too.

If you play an expansion pack, repeat again for the latest expansion pack installed
and is used to play the game. For example, _The Sims 2 Mansion and Garden Stuff_ (Sims2EP9.exe)

### 3. Run the script

    python3 ./sims2-4k-ui-converter.py

## License

The script is licensed under GPLv3.
