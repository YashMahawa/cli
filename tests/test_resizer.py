import unittest
from argparse import Namespace
from caelestia.subcommands.resizer import WindowRule, _parse_match_arg
from caelestia.subcommands.resizer import Command

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

    def test_numeric_bounds_predicates(self):
        rule_lte = WindowRule("", "", "100", "100", [], matches=[("initialWidth", "lte", "1000")])
        self.assertTrue(rule_lte.evaluate({"initialWidth": 600}))
        self.assertTrue(rule_lte.evaluate({"initialWidth": 1000}))
        self.assertFalse(rule_lte.evaluate({"initialWidth": 1024}))

        rule_gte = WindowRule("", "", "100", "100", [], matches=[("initialHeight", "gte", "200")])
        self.assertTrue(rule_gte.evaluate({"initialHeight": 300}))
        self.assertFalse(rule_gte.evaluate({"initialHeight": 100}))

    def test_default_popup_rules_composite_criteria(self):
        command = Command(Namespace(daemon=False))
        signin = next(rule for rule in command.window_rules if rule.name == "(?i)Sign In")

        # Main browser tab navigating to sign-in page (large initial size, browser initial title)
        main_browser_tab = {
            "title": "Account Sign In",
            "initialTitle": "Google Chrome",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [1920, 1080],
            "initialSize": [1920, 1080],
            "initialWidth": 1920,
            "initialHeight": 1080,
        }
        self.assertFalse(signin.evaluate(main_browser_tab))

        # OAuth popup with sign in initial title and bounded geometry
        oauth_popup = {
            "title": "Account Sign In",
            "initialTitle": "Account Sign In",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [600, 700],
            "initialSize": [600, 700],
            "initialWidth": 600,
            "initialHeight": 700,
        }
        self.assertTrue(signin.evaluate(oauth_popup))

    def test_unparented_popup_heuristic(self):
        command = Command(Namespace(daemon=False))
        command._apply_window_actions = lambda window_id, width, height, actions: True

        # Small unparented browser popup
        unparented_popup = {
            "address": "0x123",
            "title": "OAuth Login",
            "initialTitle": "OAuth Login",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [500, 600],
            "initialSize": [500, 600],
            "modal": False,
            "parent": "0x0",
            "xdg_toplevel_parent": "0x0",
        }
        self.assertTrue(command._apply_unparented_popup_heuristic("123", unparented_popup))

        # Large main browser window
        main_browser = {
            "address": "0x456",
            "title": "Google Chrome",
            "initialTitle": "Google Chrome",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [1920, 1080],
            "initialSize": [1920, 1080],
            "modal": False,
            "parent": "0x0",
            "xdg_toplevel_parent": "0x0",
        }
        self.assertFalse(command._apply_unparented_popup_heuristic("456", main_browser))

    def test_initial_props_tracking_and_close_event(self):
        command = Command(Namespace(daemon=False))

        open_info = {
            "address": "0xabc123",
            "title": "Google Chrome",
            "initialTitle": "Google Chrome",
            "class": "google-chrome",
            "size": [1920, 1080],
        }
        command._record_initial_props("abc123", open_info)

        # Runtime title update
        title_update_info = {
            "address": "0xabc123",
            "title": "Sign In - Google Accounts",
            "class": "google-chrome",
            "size": [1920, 1080],
        }
        enhanced = command._enhance_window_info("abc123", title_update_info)
        self.assertEqual(enhanced["initialTitle"], "Google Chrome")
        self.assertEqual(enhanced["title"], "Sign In - Google Accounts")

        # Close event clears cache
        command.applied_rules["abc123"] = "rule"
        command._handle_window_event("closewindow>>abc123")
        self.assertNotIn("abc123", command.applied_rules)
        self.assertNotIn("abc123", command.window_initial_props)
        
if __name__ == '__main__':
    unittest.main()
