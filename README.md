
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

Unlike the Legacy Collection, setting the UI scale is not possible with this mod,
except we have an experimental 150% scaling option [(with visual artifacts)](https://github.com/lah7/sims2-4k-ui-patch/issues/52)


## Comparison

The mod makes the UI playable at a 3840x2160 resolution.

![Comparing 2160p gameplay before and after patching](https://github.com/user-attachments/assets/9b63fc77-86a9-4399-90ee-54fcaeeefbdc)

Since our patcher modifies the geometry and assets directly, this mod provides a
native 4K UI experience, providing much crisper fonts and Sim detail. Up to now,
playing in 1080p was the best way to play.

Here's how things compare pixel wise.
Click the image to open in a new tab, and switch between them to take a closer look.

| Legacy Collection    | Retail Discs + Patch |
| -------------------- | -------------------- |
| ![Gameplay Menu - Legacy Collection](https://github.com/user-attachments/assets/bbacdfbd-b99b-4009-98ac-00cad854a5d6) | ![Gameplay Menu - Patched](https://github.com/user-attachments/assets/6580a4fe-9cb5-47cc-9781-b9ef16dae5ae) |
| ![Lot Info - Legacy Collection](https://github.com/user-attachments/assets/a0f31540-cf52-4ca4-84a7-209dfe441c67) | ![Lot Info - After](https://github.com/user-attachments/assets/2add746d-d57b-498c-9c97-28692e05cffb) |
| ![Dialog - Legacy Collection](https://github.com/user-attachments/assets/21f02a7d-681e-4e00-a027-dab66bb15ef1) | ![Dialog - After](https://github.com/user-attachments/assets/fad899bd-f3c2-4043-839a-8373e9d7f077) |

To compare 1080p, here are the equivalent images from an unpatched retail game.
Zoom these to 200%.

* [Image 1 - Gameplay Menu (1080p)](https://github.com/user-attachments/assets/1f805481-c9cf-4ea5-95ca-a743be9a3f73)
* [Image 2 - Lot Info (1080p)](https://github.com/user-attachments/assets/2a6acec7-6e8b-4ba3-8314-12ffc755d5f0)
* [Image 3 - Dialog (1080p)](https://github.com/user-attachments/assets/95d44383-301c-4354-8496-2ac665af6160)

<sub>(1080p and the Legacy Collection at 2160p (4K) are identical in terms of
UI sharpness. It's not you, the UI isn't as sharp with the 2025 re-release
"4K support")</sub>


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

For the absolute latest changes before a versioned release, download an artifact
from the [latest workflow run.](https://github.com/lah7/sims2-4k-ui-patch/actions?query=event%3Apush+branch%3Amaster)


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

Alternately, see [DEVELOPMENT.md](DEVELOPMENT.md#linux) for running from the repository.
This will provide a better desktop integration.


### macOS

We don't have a pre-built binary for macOS, but you can run the Python script directly. See [DEVELOPMENT.md](DEVELOPMENT.md#macos) for instructions.

This patch program will work fine if you play the game under a Wine compatibility layer.
However, if you purchased the [The Sims™ 2: Super Collection],
we don't know whether files are exposed in a way that is compatible with this program. Please let us know!


[latest release]: https://github.com/lah7/sims2-4k-ui-patch/releases/latest
[Releases]: https://github.com/lah7/sims2-4k-ui-patch/releases


## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for instructions on hacking the code
and running from the repository.

## Game UI Tips

The game has its own UI debugger built-in. To activate, enable testing cheats
globally by adding a line to your latest game's `TSData/Res/Config/globalProps.xml` file.

    <AnyBoolean key="testingCheatsEnabled" type="0xcba908e1">true</AnyBoolean>'

* <kbd>CTRL</kbd>+<kbd>U</kbd> opens the UI browser. Click the "?" button for more shortcuts and hints.
* <kbd>CTRL</kbd>+<kbd>SHIFT</kbd>+<kbd>U</kbd> reloads the UI.


## UI Inspector

While developing this project, we developed our own UI inspector program,
**S2UI Inspector**, to aid with the research and analysis for UI scripts,
its elements and attributes.

https://github.com/lah7/sims2-ui-inspector


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
