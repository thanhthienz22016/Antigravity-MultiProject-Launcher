#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_swarm_quota.py - Automated Unit & Integration Tests for
Antigravity Swarm Manager Quota Tracking & Smart Focus Engine.
"""

import ast
import json
import os
import re
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SWARM_SCRIPT = os.path.join(SCRIPT_DIR, "Antigravity_Swarm_Manager.pyw")


class TestSwarmCodeStructure(unittest.TestCase):
    """Verify syntax, AST structure, and presence of critical components."""

    def test_01_syntax_and_ast_compilation(self):
        """Ensure Antigravity_Swarm_Manager.pyw has valid Python syntax and AST."""
        self.assertTrue(os.path.isfile(SWARM_SCRIPT), f"File not found: {SWARM_SCRIPT}")
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        # Parse AST
        parsed = ast.parse(code, filename=SWARM_SCRIPT)
        self.assertIsNotNone(parsed)
        # Compile code object
        compiled = compile(code, SWARM_SCRIPT, "exec")
        self.assertIsNotNone(compiled)

    def test_02_required_symbols_present(self):
        """Ensure all required quota and smart focus functions/classes are defined."""
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        required_symbols = [
            "bring_window_to_foreground",
            "find_all_antigravity_windows",
            "format_quota_badge",
            "format_quota_cell",
            "parse_quota_from_text_or_json",
            "extract_quota_from_sqlite",
            "get_cached_profile_quota",
            "save_cached_profile_quota",
            "probe_cdp_for_quota",
            "get_profile_quota",
            "CDP_QUOTA_JS",
            "SimpleWebSocket",
            "find_running_for_profile",
            "_update_launch_focus_button_state",
            "_start_quota_monitor_timer",
            "keybd_event",
            "VK_MENU",
        ]
        for sym in required_symbols:
            self.assertIn(sym, code, f"Required symbol '{sym}' missing from codebase")


class TestQuotaExtractionLogic(unittest.TestCase):
    """Test quota badge formatting and parsing algorithms."""

    def setUp(self):
        # We can safely import or extract the pure functions directly from the module
        # To avoid launching Tkinter root in headless environments, extract helper functions
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        # Isolate pure helper functions into a clean execution dict
        helper_globals = {
            "re": re,
            "json": json,
            "os": os,
            "time": __import__("time"),
            "urllib": __import__("urllib"),
            "socket": __import__("socket"),
            "struct": __import__("struct"),
            "base64": __import__("base64"),
        }
        # Execute only helper definitions
        pattern = (
            r"(def format_quota_badge\(.*?\):\n(?:    .*\n)+)"
            r"|(def format_quota_cell\(.*?\):\n(?:    .*\n)+)"
            r"|(def parse_quota_from_text_or_json\(.*?\):\n(?:    .*\n)+)"
            r"|(def get_cached_profile_quota\(.*?\):\n(?:    .*\n)+)"
            r"|(def save_cached_profile_quota\(.*?\):\n(?:    .*\n)+)"
        )
        for match in re.finditer(r"^def (?:format_quota_badge|format_quota_cell|parse_quota_from_text_or_json|get_cached_profile_quota|save_cached_profile_quota)\b[\s\S]*?(?=\n(?:def |class |# ---|\Z))", code, re.M):
            exec(match.group(0), helper_globals)

        self.format_quota_badge = helper_globals.get("format_quota_badge")
        self.format_quota_cell = helper_globals.get("format_quota_cell")
        self.parse_quota_from_text_or_json = helper_globals.get("parse_quota_from_text_or_json")
        self.get_cached_profile_quota = helper_globals.get("get_cached_profile_quota")
        self.save_cached_profile_quota = helper_globals.get("save_cached_profile_quota")

    def test_03_format_quota_badge(self):
        """Test percentage thresholds and color badge formatting."""
        # > 50 -> Green
        self.assertIn("🟢", self.format_quota_badge(100))
        self.assertIn("100%", self.format_quota_badge(100))
        self.assertIn("🟢", self.format_quota_badge(51))

        # 15..50 -> Yellow
        self.assertIn("🟡", self.format_quota_badge(50))
        self.assertIn("🟡", self.format_quota_badge(30))
        self.assertIn("🟡", self.format_quota_badge(15))

        # < 15 -> Red
        self.assertIn("🔴", self.format_quota_badge(14))
        self.assertIn("🔴", self.format_quota_badge(3))
        self.assertIn("🔴", self.format_quota_badge(0))

        # None -> ⚪ --%
        self.assertEqual("⚪ --%", self.format_quota_badge(None))

    def test_04_format_quota_cell(self):
        """Test cell string formatting for Treeviews."""
        # (94, 39)
        cell1 = self.format_quota_cell(94, 39)
        self.assertIn("🟢 94%", cell1)
        self.assertIn("🟡 39%", cell1)

        # (3, 68)
        cell2 = self.format_quota_cell(3, 68)
        self.assertIn("🔴 3%", cell2)
        self.assertIn("🟢 68%", cell2)

        # (None, None)
        cell3 = self.format_quota_cell(None, None)
        self.assertEqual("⚪ Chưa đồng bộ", cell3)

    def test_05_parse_quota_from_screenshot_text(self):
        """Test regex extraction against exact text matching the user's screenshot."""
        screenshot_text = """
Gemini Models
Weekly Limit Remaining
39%
You have used some of your weekly limit, it will fully refresh in 4 days
Five Hour Limit Remaining
94%
You have used some of your five hour limit, it will fully refresh in 2 hours

Claude and GPT models
Weekly Limit Remaining
68%
You have used some of your weekly limit, it will fully refresh in 2 days
Five Hour Limit Remaining
3%
You have used almost all of your five hour limit, it will fully refresh in 42 minutes
"""
        parsed = self.parse_quota_from_text_or_json(screenshot_text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("gemini_weekly"), 39)
        self.assertEqual(parsed.get("gemini_5h"), 94)
        self.assertEqual(parsed.get("claude_weekly"), 68)
        self.assertEqual(parsed.get("claude_5h"), 3)
        self.assertIn("2 hours", parsed.get("gemini_5h_refresh", ""))
        self.assertIn("42 minutes", parsed.get("claude_5h_refresh", ""))

    def test_06_parse_quota_from_json(self):
        """Test JSON payload parsing."""
        raw_json = json.dumps({
            "gemini_5h": 85,
            "gemini_weekly": 42,
            "gemini_5h_refresh": "1 hour 30 mins",
            "claude_5h": 12,
            "claude_weekly": 70,
            "claude_5h_refresh": "15 minutes"
        })
        parsed = self.parse_quota_from_text_or_json(raw_json)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("gemini_5h"), 85)
        self.assertEqual(parsed.get("gemini_weekly"), 42)
        self.assertEqual(parsed.get("claude_5h"), 12)
        self.assertEqual(parsed.get("claude_weekly"), 70)

    def test_06b_parse_quota_from_bytes(self):
        """Test parsing SQLite BLOB byte values."""
        raw_bytes = json.dumps({"gemini_5h": 77, "claude_5h": 33}).encode("utf-8")
        parsed = self.parse_quota_from_text_or_json(raw_bytes)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("gemini_5h"), 77)
        self.assertEqual(parsed.get("claude_5h"), 33)

    def test_05b_parse_phrasing_variations(self):
        """Test various 5-hour limit phrasing variants (hyphenated, spelled out, digit)."""
        variations = [
            "Gemini Models\nFive Hour Limit Remaining\n88%\nrefresh in 1 hour\nClaude models\n5-Hour Limit Remaining\n14%\nrefresh in 25 mins",
            "Gemini Models\n5 Hour Limit Remaining\n88%\nrefresh in 1 hour\nClaude and GPT models\nfive-hour limit remaining\n14%\nrefresh in 25 mins",
        ]
        for v in variations:
            parsed = self.parse_quota_from_text_or_json(v)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.get("gemini_5h"), 88)
            self.assertEqual(parsed.get("claude_5h"), 14)
            self.assertEqual(parsed.get("gemini_5h_refresh"), "1 hour")
            self.assertEqual(parsed.get("claude_5h_refresh"), "25 mins")

    def test_07_quota_cache_roundtrip(self):
        """Test saving and retrieving quota cache on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_data = {
                "gemini_5h": 90,
                "gemini_weekly": 50,
                "gemini_reset": "in 3 hours",
                "claude_5h": 20,
                "claude_weekly": 60,
                "claude_reset": "in 1 hour",
                "updated_at": 1700000000.0
            }
            ok = self.save_cached_profile_quota(tmp_dir, test_data)
            self.assertTrue(ok)

            cached = self.get_cached_profile_quota(tmp_dir)
            self.assertIsNotNone(cached)
            self.assertEqual(cached.get("gemini_5h"), 90)
            self.assertEqual(cached.get("claude_5h"), 20)
            self.assertEqual(cached.get("gemini_weekly"), 50)


class TestWebSocketEngine(unittest.TestCase):
    """Test RFC 6455 Pure-Python WebSocket implementation."""

    def test_08_frame_encoding_and_handshake_headers(self):
        """Test SimpleWebSocket frame encoding and masking."""
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        local_env = {
            "socket": __import__("socket"),
            "struct": __import__("struct"),
            "base64": __import__("base64"),
            "hashlib": __import__("hashlib"),
            "urllib": __import__("urllib"),
            "time": __import__("time"),
            "json": json,
            "threading": __import__("threading"),
            "os": os,
        }
        # Find SimpleWebSocket class definition
        class_match = re.search(r"class SimpleWebSocket:[\s\S]*?(?=\n\n(?:class |def |# ---|\Z))", code)
        self.assertIsNotNone(class_match)
        exec(class_match.group(0), local_env)

        SimpleWebSocket = local_env.get("SimpleWebSocket")
        self.assertIsNotNone(SimpleWebSocket)

        ws = SimpleWebSocket("ws://127.0.0.1:9222/devtools/page/test", connect=False)
        # Test frame encoding
        payload = '{"id":1,"method":"Runtime.evaluate"}'
        frame = ws._encode_frame(payload)
        self.assertIsInstance(frame, bytes)
        # First byte: 0x81 (FIN + text frame)
        self.assertEqual(frame[0], 0x81)
        # Second byte: masked bit set
        self.assertTrue(frame[1] & 0x80)

    def test_09_subtimeout_non_blocking(self):
        """Test that read_message does not exit prematurely when socket.timeout occurs before end_time."""
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        local_env = {
            "socket": __import__("socket"),
            "struct": __import__("struct"),
            "base64": __import__("base64"),
            "hashlib": __import__("hashlib"),
            "urllib": __import__("urllib"),
            "time": __import__("time"),
            "json": json,
            "threading": __import__("threading"),
            "os": os,
        }
        class_match = re.search(r"class SimpleWebSocket:[\s\S]*?(?=\n\n(?:class |def |# ---|\Z))", code)
        exec(class_match.group(0), local_env)
        SimpleWebSocket = local_env.get("SimpleWebSocket")

        ws = SimpleWebSocket("ws://127.0.0.1:9222/devtools/page/test", connect=False)
        ws.connected = True

        call_count = [0]
        class MockSocket:
            def settimeout(self, t):
                pass
            def recv(self, n):
                call_count[0] += 1
                if call_count[0] <= 2:
                    raise local_env["socket"].timeout("timed out")
                payload = b'{"id":99}'
                return bytes([0x81, len(payload)]) + payload
            def close(self):
                pass

        ws.sock = MockSocket()
        msg = ws.read_message(timeout=1.0)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.get("id"), 99)
        self.assertGreaterEqual(call_count[0], 3)


def run_tests():
    """Run all verification tests and return exit code."""
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTest(loader.loadTestsFromTestCase(TestSwarmCodeStructure))
    suite.addTest(loader.loadTestsFromTestCase(TestQuotaExtractionLogic))
    suite.addTest(loader.loadTestsFromTestCase(TestWebSocketEngine))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
