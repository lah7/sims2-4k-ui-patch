"""
Perform tests on the UI scripts module to ensure that the data
can be serialised and deserialised correctly.

"Serialisation" means converting the data structure between Maxis' XML-like format
and our own Python format, which should be reconstructed as accurately as possible.
"""
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import uiscript
from sims2patcher.uiscript import UIScriptElement, UIScriptRoot
from tests.test_base import BaseTestCase


class UIScriptTest(BaseTestCase):
    """
    Test our "UI scripts" module against a test package and edge cases.
    """
    def test_serialize(self):
        """Check we can serialize UI script files"""
        raw = """# This is a comment
        <LEGACY clsid=GZWinGen iid=IGZWinGen area=(10,10,605,432) >
        <CHILDREN>
            <LEGACY clsid=GZWinBMP iid=IGZWinBMP transparentbkg=yes >
            <LEGACY clsid=GZWinText caption="Hello, World!" >
        </CHILDREN>
        """
        root: UIScriptRoot = uiscript.serialize_uiscript(raw)
        self.assertEqual(len(root.children), 1)
        self.assertIsInstance(root, UIScriptRoot)
        self.assertIsInstance(root.children[0], UIScriptElement)
        self.assertEqual(len(root.children[0].children), 2)
        self.assertEqual(root.children[0]["clsid"], "GZWinGen")
        self.assertEqual(root.children[0]["iid"], "IGZWinGen")
        self.assertEqual(root.children[0]["area"], "(10,10,605,432)")
        self.assertEqual(root.children[0].children[0]["clsid"], "GZWinBMP")
        self.assertEqual(root.children[0].children[0]["iid"], "IGZWinBMP")
        self.assertEqual(root.children[0].children[0]["transparentbkg"], "yes")
        self.assertEqual(root.children[0].children[1]["clsid"], "GZWinText")
        self.assertEqual(root.children[0].children[1]["caption"], "Hello, World!")
        self.assertEqual(root.comments[0], "# This is a comment")
        self.assertEqual(root.children[0].attributes, {
            "clsid": "GZWinGen",
            "iid": "IGZWinGen",
            "area": "(10,10,605,432)"
        })

    def test_deserialize(self):
        """Check we can correctly deserialize to a UI script file"""
        root = UIScriptRoot()
        root.comments.append("# This is a test")
        root.children = [UIScriptElement()]
        root.children[0].attributes = {
            "clsid": "GZWinGen",
            "iid": "IGZWinGen",
            "area": "(10,10,605,432)"
        }
        root.children[0].children = [UIScriptElement(), UIScriptElement()]
        root.children[0].children[0].attributes = {
            "clsid": "GZWinBMP",
            "iid": "IGZWinBMP",
            "transparentbkg": "yes"
        }
        root.children[0].children[1].attributes = {
            "clsid": "GZWinText",
            "caption": "Hello, World!"
        }

        output = uiscript.deserialize_uiscript(root)
        expected = "# This is a test\r\n" \
                   "<LEGACY clsid=GZWinGen iid=IGZWinGen area=(10,10,605,432) >\r\n" \
                   "<CHILDREN>\r\n" \
                   "   <LEGACY clsid=GZWinBMP iid=IGZWinBMP transparentbkg=yes >\r\n" \
                   "   <LEGACY clsid=GZWinText caption=\"Hello, World!\" >\r\n" \
                   "</CHILDREN>\r\n"

        self.assertEqual(output, expected)

    def test_duplicate_attributes(self):
        """Check deserialization preserves duplicated attributes"""
        raw = """<LEGACY clsid=GZWinGen wparam="0x123" wparam="0x030000f0" wparam="0x030000f2" z=789 >\r\n"""
        root = uiscript.serialize_uiscript(raw)
        self.assertEqual(root.children[0].attributes, {
            "clsid": "GZWinGen",
            "wparam": ["0x123", "0x030000f0", "0x030000f2"],
            "z": "789"
        })
        output = uiscript.deserialize_uiscript(root)
        self.assertEqual(output, raw)

    def test_duplicate_attributes_with_whitespace(self):
        """Check deserialization preserves duplicated attributes that also contain whitespace"""
        raw = """<LEGACY captionres={12345678,12345678} wparam="0x030000f0,string,currentNeighborhoodType!=university and EPInstalled=EP6" wparam="0x030000f2,string,currentNeighborhoodType!=university and EPInstalled=EP6" winflag_visible=no >\r\n"""
        root = uiscript.serialize_uiscript(raw)
        self.assertEqual(root.children[0].attributes, {
            "captionres": "{12345678,12345678}",
            "wparam": [
                "0x030000f0,string,currentNeighborhoodType!=university and EPInstalled=EP6",
                "0x030000f2,string,currentNeighborhoodType!=university and EPInstalled=EP6"
            ],
            "winflag_visible": "no",
        })
        output = uiscript.deserialize_uiscript(root)
        self.assertEqual(output, raw)

    def test_list_all_elements(self):
        """Check we can list all elements in a UI script file"""
        root = uiscript.UIScriptRoot()

        for c in range(10):
            element = uiscript.UIScriptElement()
            element.attributes = {"testdata": str(c)}
            if c in [2, 4, 6, 8]:
                element.children = [uiscript.UIScriptElement()]
                element.children[0].attributes = {"testdata": str(c + 0.5)}
            root.children.append(element)

        all_elements = root.get_all_elements()

        self.assertEqual(len(all_elements), 14)
        self.assertEqual(all(isinstance(element, uiscript.UIScriptElement) for element in all_elements), True)
        self.assertEqual(all_elements[0].attributes, {"testdata": "0"})
        self.assertEqual(all_elements[2].attributes, {"testdata": "2"})
        self.assertEqual(all_elements[3].attributes, {"testdata": "2.5"})
        self.assertEqual(all_elements[4].attributes, {"testdata": "3"})
        self.assertEqual(all_elements[8].attributes, {"testdata": "6"})
        self.assertEqual(all_elements[9].attributes, {"testdata": "6.5"})

    def test_edit_all_elements(self):
        """Check elements are edited when using get_all_elements()"""
        root = uiscript.UIScriptRoot()
        for _ in range(10):
            element = uiscript.UIScriptElement()
            element.attributes = {"state": "old"}
            element.children = [uiscript.UIScriptElement(), uiscript.UIScriptElement()]
            element.children[0].attributes = {"state": "old"}
            element.children[1].attributes = {"state": "old"}
            root.children.append(element)

        all_elements = root.get_all_elements()
        self.assertEqual(len(all_elements), 30)
        all_elements[1].attributes["state"] = "new"
        all_elements[2].attributes["state"] = "new"
        all_elements[27].attributes["state"] = "new"

        all_elements_2 = root.get_all_elements()
        self.assertEqual(all_elements_2[1].attributes["state"], "new")
        self.assertEqual(all_elements_2[2].attributes["state"], "new")
        self.assertEqual(all_elements_2[27].attributes["state"], "new")
        self.assertEqual(root.children[0].children[0].attributes["state"], "new")
        self.assertEqual(root.children[0].children[1].attributes["state"], "new")
        self.assertEqual(root.children[9].attributes["state"], "new")

    def test_list_all_elements_by_attribute(self):
        """Check we can list filter elements in a UI script file"""
        root = uiscript.UIScriptRoot()

        for c in range(10):
            element = uiscript.UIScriptElement()
            element.attributes = {"testdata": str(c), "dummy": "1"}
            root.children.append(element)

        self.assertEqual(len(root.get_elements_by_attribute("testdata", "6")), 1)
        self.assertEqual(len(root.get_elements_by_attribute("dummy", "1")), 10)

    def test_multiline_values(self):
        """Check attributes with multi-line values have escaped newlines"""
        raw = """<LEGACY example="This is my\r\nmultiline=test\r\nstring" >\r\n"""
        root = uiscript.serialize_uiscript(raw)
        self.assertEqual(root.children[0].attributes, {
            "example": "This is my\\r\\nmultiline=test\\r\\nstring",
        })
        output = uiscript.deserialize_uiscript(root)
        self.assertEqual(repr(output), repr(raw))

    def test_multiline_stripped(self):
        """Our logic strips whitespace for multi-line values"""
        raw = """<LEGACY example="My whitespace   \r\nis being    \r\nstripped  " >\r\n"""
        expected = """<LEGACY example="My whitespace\r\nis being\r\nstripped  " >\r\n"""
        root = uiscript.serialize_uiscript(raw)
        output = uiscript.deserialize_uiscript(root)
        self.assertEqual(repr(output), repr(expected))

    def test_embedded_key_values(self):
        """Check key-value pairs inside an attribute's value are processed correctly"""
        raw = """<LEGACY wparam="0x030000f2,string,currentNeighborhoodtype!=university and EPInstalled!=EP6" >\r\n"""
        root = uiscript.serialize_uiscript(raw)
        self.assertEqual(root.children[0].attributes, {
            "wparam": "0x030000f2,string,currentNeighborhoodtype!=university and EPInstalled!=EP6",
        })
        output = uiscript.deserialize_uiscript(root)
        self.assertEqual(output, raw)
