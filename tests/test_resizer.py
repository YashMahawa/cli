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

        # Small unparented browser popup with auth title
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

        # Unparented popup with popup role
        unparented_role_popup = {
            "address": "0x124",
            "title": "Small Helper",
            "initialTitle": "Small Helper",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "role": "pop-up",
            "size": [400, 500],
            "initialSize": [400, 500],
            "modal": False,
            "parent": "0x0",
            "xdg_toplevel_parent": "0x0",
        }
        self.assertTrue(command._apply_unparented_popup_heuristic("124", unparented_role_popup))

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

    def test_unparented_popup_heuristic_negative_pwa_and_browser(self):
        command = Command(Namespace(daemon=False))
        command._apply_window_actions = lambda window_id, width, height, actions: True

        # Small normal browser window (sized 800x600, no auth/popup semantics)
        small_browser = {
            "address": "0x789",
            "title": "GitHub - Where the world builds software",
            "initialTitle": "GitHub - Where the world builds software",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [800, 600],
            "initialSize": [800, 600],
            "modal": False,
            "parent": "0x0",
            "xdg_toplevel_parent": "0x0",
        }
        self.assertFalse(command._apply_unparented_popup_heuristic("789", small_browser))

        # PWA window (Spotify Web Player, sized 800x600, no auth/popup semantics)
        pwa_window = {
            "address": "0x790",
            "title": "Spotify - Web Player: Music for everyone",
            "initialTitle": "Spotify - Web Player: Music for everyone",
            "class": "chrome-spotify.com__-Default",
            "initialClass": "chrome-spotify.com__-Default",
            "size": [800, 600],
            "initialSize": [800, 600],
            "modal": False,
            "parent": "0x0",
            "xdg_toplevel_parent": "0x0",
        }
        self.assertFalse(command._apply_unparented_popup_heuristic("790", pwa_window))

    def test_delayed_client_metadata_handling(self):
        command = Command(Namespace(daemon=False))
        signin = next(rule for rule in command.window_rules if rule.name == "(?i)Sign In")

        # 1. Main browser window open event when hyprctl has not populated client yet (size [0, 0])
        delayed_main_window = {
            "address": "0xdef1",
            "title": "Google Chrome",
            "initialTitle": "Google Chrome",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [0, 0],
            "initialSize": [0, 0],
            "initialWidth": 0,
            "initialHeight": 0,
        }
        command._record_initial_props("def1", delayed_main_window, fallback_title="Google Chrome", fallback_class="google-chrome")

        # Unpopulated 0x0 geometry must NOT satisfy initialWidth <= 1000
        self.assertFalse(signin.evaluate(delayed_main_window))

        # 2. Later hyprctl populates client size [1920, 1080] on runtime title change to "Account Sign In"
        populated_main_window = {
            "address": "0xdef1",
            "title": "Account Sign In",
            "class": "google-chrome",
            "size": [1920, 1080],
        }
        command._record_initial_props("def1", populated_main_window)
        enhanced = command._enhance_window_info("def1", populated_main_window)

        # Initial size in cache was updated to [1920, 1080], not permanently stuck at [0, 0]
        self.assertEqual(enhanced["initialWidth"], 1920)
        self.assertEqual(enhanced["initialHeight"], 1080)

        # Main window sized 1920x1080 does not satisfy initialWidth <= 1000
        self.assertFalse(signin.evaluate(enhanced))

        # 3. Popup window with delayed client metadata initially [0, 0] then updated to [600, 700]
        delayed_popup = {
            "address": "0xdef2",
            "title": "Account Sign In",
            "initialTitle": "Account Sign In",
            "class": "google-chrome",
            "initialClass": "google-chrome",
            "size": [0, 0],
        }
        command._record_initial_props("def2", delayed_popup)
        self.assertFalse(signin.evaluate(delayed_popup))

        populated_popup = {
            "address": "0xdef2",
            "title": "Account Sign In",
            "class": "google-chrome",
            "size": [600, 700],
        }
        command._record_initial_props("def2", populated_popup)
        enhanced_popup = command._enhance_window_info("def2", populated_popup)
        self.assertEqual(enhanced_popup["initialWidth"], 600)
        self.assertEqual(enhanced_popup["initialHeight"], 700)
        self.assertTrue(signin.evaluate(enhanced_popup))

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
