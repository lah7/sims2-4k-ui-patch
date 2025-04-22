# Development

This project is written in Python. To start hacking, clone this repository
and set up a [virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
to install [requirements.txt](requirements.txt).

    git clone --recurse-submodules https://github.com/lah7/sims2-4k-ui-patcher.git

Python 3.10 is the minimum supported version.

### Windows

[Install Python 3.13](https://www.python.org/downloads/windows/), then run:

    python -m venv venv
    venv\Scripts\activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python sims2_4k_ui_patcher.py

### macOS

[Install Python 3.13](https://www.python.org/downloads/macos/), then run:

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py

### Linux

Your distribution likely already has Python 3 installed. In some cases, you may
need to install a package to provide virtual environment support (e.g. `python3-venv` on Debian/Ubuntu)

    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python3 sims2_4k_ui_patcher.py

Alternatively, you could use your system's interpreter by installing packages
that provides the dependencies. This might be more space efficient.

**For Arch Linux:**

    sudo pacman -S --asdeps python-pyqt6 python-pillow python-requests

**For Debian 12 /Ubuntu 24.04:**

    sudo apt install python3-pyqt6 python3-pillow python3-requests


## Updating

Since we use submodules, make sure to pull them too:

    git pull --recurse-submodules --rebase origin master


## Testing

Unit tests check everything is in working order.

You'll need to copy a file from The Sims 2 University (EP1) into the `tests/files` folder:

    724723ddc5b020a55bdefc60a7cf1304    The Sims 2 University/TSData/Res/UI/ui.package

**File not included.** With this file present, you can locally run the tests:

    python -m unittest discover ./tests/

This checks the modules and compression procedures are working correctly.
