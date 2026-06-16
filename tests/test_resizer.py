import unittest
from caelestia.subcommands.resizer import WindowRule, _parse_match_arg

class TestWindowRule(unittest.TestCase):
    def test_legacy_exact(self):
        rule = WindowRule("Foo", "titleExact", "100", "100", [])
        self.assertTrue(rule.evaluate({"title": "Foo"}))
        self.assertFalse(rule.evaluate({"title": "Foobar"}))
        
    def test_legacy_contains(self):
        rule = WindowRule("Foo", "titleContains", "100", "100", [])
        self.assertTrue(rule.evaluate({"title": "A Foo B"}))
        self.assertFalse(rule.evaluate({"title": "A foo B"}))

    def test_legacy_regex(self):
        rule = WindowRule("^Foo.*Bar$", "titleRegex", "100", "100", [])
        self.assertTrue(rule.evaluate({"title": "Foo123Bar"}))
        self.assertFalse(rule.evaluate({"title": "Foo123Bar2"}))

    def test_legacy_initial_title(self):
        rule = WindowRule("Loading...", "initialTitle", "100", "100", [])
        self.assertTrue(rule.evaluate({"initialTitle": "Loading..."}))
        self.assertFalse(rule.evaluate({"initialTitle": "Done"}))
        
    def test_generic_match_exact(self):
        rule = WindowRule("", "", "100", "100", [], matches=[("class", "exact", "Gimp")])
        self.assertTrue(rule.evaluate({"class": "Gimp"}))
        self.assertFalse(rule.evaluate({"class": "Gimp2"}))

    def test_generic_match_alias(self):
        rule = WindowRule("", "", "100", "100", [], matches=[("window_class", "exact", "Gimp")])
        self.assertTrue(rule.evaluate({"class": "Gimp"}))

    def test_generic_match_multiple(self):
        rule = WindowRule("", "", "100", "100", [], matches=[
            ("class", "exact", "Browser"),
            ("workspace", "exact", "2")
        ])
        # Use realistic Hyprland format for workspace
        self.assertTrue(rule.evaluate({"class": "Browser", "workspace": {"id": 2, "name": "2"}}))
        self.assertFalse(rule.evaluate({"class": "Browser", "workspace": {"id": 1, "name": "1"}}))
        self.assertFalse(rule.evaluate({"class": "Term", "workspace": {"id": 2, "name": "2"}}))

    def test_generic_match_nested(self):
        rule = WindowRule("", "", "100", "100", [], matches=[("workspace.name", "exact", "special:scratchpad")])
        self.assertTrue(rule.evaluate({"workspace": {"id": -99, "name": "special:scratchpad"}}))
        self.assertFalse(rule.evaluate({"workspace": {"id": 1, "name": "1"}}))

    def test_parse_match_arg(self):
        self.assertEqual(_parse_match_arg("class=Gimp"), ("class", "exact", "Gimp"))
        self.assertEqual(_parse_match_arg("title:regex=^Foo.*"), ("title", "regex", "^Foo.*"))
        self.assertEqual(_parse_match_arg("title:contains=Bar"), ("title", "contains", "Bar"))
        
if __name__ == '__main__':
    unittest.main()
