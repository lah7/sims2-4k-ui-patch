#!/usr/bin/env python3
"""
Create/update the test package for unit testing using example files.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf

package = dbpf.DBPF()

# Graphics
package.add_entry_from_file(0x856ddbac, 0x00001000, 0x00000001, 0x0, "image1.tga", compress=True)
package.add_entry_from_file(0x856ddbac, 0x00001000, 0x00000002, 0x0, "image2.tga", compress=True)
package.add_entry_from_file(0x856ddbac, 0x00002000, 0x00000003, 0x0, "image3.png", compress=False)
package.add_entry_from_file(0x856ddbac, 0x00002000, 0x00000004, 0x0, "image4.jpg", compress=True)
package.add_entry_from_file(0x856ddbac, 0x00002000, 0x00000005, 0x0, "image5.bmp", compress=True)

# UI Data
package.add_entry_from_file(0x0, 0x00003000, 0x00000006, 0x0, "uiscript1.txt", compress=True)
package.add_entry_from_file(0x0, 0x00003000, 0x00000007, 0x0, "uiscript2.txt", compress=True)
package.add_entry_from_file(0x0, 0x00003000, 0x00000008, 0x0, "uiscript3.txt", compress=True)

os.chdir(os.path.dirname(__file__))
package.save_package("../test.package")
print("Package saved")
