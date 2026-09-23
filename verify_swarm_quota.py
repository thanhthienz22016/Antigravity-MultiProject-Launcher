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
import shutil
import sqlite3
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
            "find_system_extensions_dir",
            "fast_seed_profile",
            "is_auth_or_transient_file",
            "get_all_antigravity_db_paths",
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


class TestProfileOptimizationAndSync(unittest.TestCase):
    """Test fast profile seeding, conversation sync, and auth isolation."""

    @staticmethod
    def _extract_top_level_func(code, func_name):
        """Extract a top-level function definition from source code, handling blank lines."""
        lines = code.split('\n')
        start = None
        for i, line in enumerate(lines):
            if line.startswith(f'def {func_name}(') or line.startswith(f'def {func_name} ('):
                start = i
                break
        if start is None:
            return None
        # Collect all lines belonging to this function (indented or blank until next top-level def/class)
        end = start + 1
        while end < len(lines):
            line = lines[end]
            # A non-empty, non-indented line that's not a comment = end of function
            if line and not line[0].isspace() and not line.startswith('#'):
                break
            end += 1
        return '\n'.join(lines[start:end])

    def setUp(self):
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        helper_globals = {
            "os": os,
            "sys": sys,
            "json": json,
            "re": re,
            "time": __import__("time"),
            "shutil": __import__("shutil"),
            "glob": __import__("glob"),
            "subprocess": __import__("subprocess"),
            "Path": __import__("pathlib").Path,
            "LEGACY_PROFILE_DIRS": {"profile_1", "profile_2", "profile_dev1", "profile_main"},
            "get_default_antigravity_path": lambda: "",
            "LOCAL_CONFIG_FILE": os.path.join(SCRIPT_DIR, "config.json"),
            "DESKTOP_CONFIG_FILE": os.path.join(r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher", "config.json"),
            "CONFIG_DIR": os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Antigravity_Swarm_Manager"),
            "CONFIG_FILE": os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Antigravity_Swarm_Manager", "config.json"),
        }

        # Extract functions using robust line-based extractor
        func_names = [
            "get_default_profile_data_dir",
            "is_valid_profile_data_dir",
            "is_auth_or_transient_file",
            "save_config",
            "load_config",
            "get_all_antigravity_db_paths",
            "fast_seed_profile",
        ]
        for fn in func_names:
            src = self._extract_top_level_func(code, fn)
            if src:
                exec(src, helper_globals)

        # These MUST be present
        self.assertIn("is_auth_or_transient_file", helper_globals)
        self.assertIn("fast_seed_profile", helper_globals)

        helper_globals["get_antigravity_db_path"] = lambda: ""

        self.is_auth_or_transient_file = helper_globals["is_auth_or_transient_file"]
        self.fast_seed_profile = helper_globals["fast_seed_profile"]
        self.is_valid_profile_data_dir = helper_globals.get("is_valid_profile_data_dir")
        self.get_default_profile_data_dir = helper_globals.get("get_default_profile_data_dir")
        self.load_config = helper_globals.get("load_config")
        self.save_config = helper_globals.get("save_config")
        self.get_all_antigravity_db_paths = helper_globals.get("get_all_antigravity_db_paths")

    def test_10_is_auth_or_transient_file(self):
        """Test detection of auth, token, cookie, and lock files for isolation."""
        blocked = [
            "oauth.json", "token.json", "credentials.json", "access_token",
            "auth_key.pem", "secret.txt", "cookie.sqlite", "Cookies",
            "session.lock", "temp.sock", "app.log", "cache.tmp", "DevToolsActivePort"
        ]
        for name in blocked:
            self.assertTrue(self.is_auth_or_transient_file(name), f"Should block: {name}")

        allowed = [
            "conversation_summaries.db", "brain", "settings.json",
            "keybindings.json", "extension.vsix", "antigravity.exe", "state.json"
        ]
        for name in allowed:
            self.assertFalse(self.is_auth_or_transient_file(name), f"Should allow: {name}")

    def test_11_fast_seed_profile_structure_and_isolation(self):
        """Test directory creation, data seeding, and strict credential isolation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys_user = os.path.join(tmp_dir, "sys_user")
            sys_gemini = os.path.join(sys_user, ".gemini")
            os.makedirs(os.path.join(sys_gemini, "antigravity", "brain", "conv1"), exist_ok=True)

            # Create mock runtime and conversation DB
            db_file = os.path.join(sys_gemini, "antigravity", "conversation_summaries.db")
            with open(db_file, "w", encoding="utf-8") as f:
                f.write("mock_db_content")

            conv_file = os.path.join(sys_gemini, "antigravity", "brain", "conv1", "state.json")
            with open(conv_file, "w", encoding="utf-8") as f:
                f.write("mock_state")

            # Create auth files that MUST be excluded
            token_file = os.path.join(sys_gemini, "antigravity", "token.json")
            with open(token_file, "w", encoding="utf-8") as f:
                f.write("secret_oauth_token")

            old_userprofile = os.environ.get("USERPROFILE")
            os.environ["USERPROFILE"] = sys_user

            try:
                prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_02")
                profile = {
                    "id": "profile_02",
                    "name": "Tài khoản 02",
                    "email": "dev2.antigravity@gmail.com",
                    "data_dir": prof_data_dir
                }

                ok = self.fast_seed_profile(profile)
                self.assertTrue(ok)

                # Verify profile structure
                prof_gemini = os.path.join(prof_data_dir, "UserProfile", ".gemini")
                self.assertTrue(os.path.isdir(prof_gemini))
                self.assertTrue(os.path.isdir(os.path.join(prof_data_dir, "extensions")))
                self.assertTrue(os.path.isdir(os.path.join(prof_data_dir, "Temp")))

                # Verify conversation DB is present
                prof_db = os.path.join(prof_gemini, "antigravity", "conversation_summaries.db")
                self.assertTrue(os.path.isfile(prof_db))

                # Verify brain context is present
                prof_conv = os.path.join(prof_gemini, "antigravity", "brain", "conv1", "state.json")
                self.assertTrue(os.path.isfile(prof_conv))

                # CRITICAL: Verify auth tokens are NOT copied
                prof_token = os.path.join(prof_gemini, "antigravity", "token.json")
                self.assertFalse(os.path.exists(prof_token), "FATAL: Auth token leaked to secondary profile!")

                # Verify seed marker
                marker = os.path.join(prof_data_dir, ".seed_info.json")
                self.assertTrue(os.path.isfile(marker))

                # Verify idempotent instant return
                t0 = __import__("time").time()
                ok2 = self.fast_seed_profile(profile, force=False)
                t_elapsed = __import__("time").time() - t0
                self.assertTrue(ok2)
                self.assertLess(t_elapsed, 0.05)
            finally:
                if old_userprofile is not None:
                    os.environ["USERPROFILE"] = old_userprofile
                else:
                    os.environ.pop("USERPROFILE", None)

    def test_12_treeview_column_indexing(self):
        """Test Treeview column values indexing to ensure data_dir resolves correctly."""
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("item_vals[5] if len(item_vals) > 5 else item_vals[3]", code)

    def test_13_tokenizer_whitelist_in_is_auth_or_transient_file(self):
        """Ensure tokenizer, tiktoken and state files are whitelisted and not stripped."""
        whitelist_cases = [
            "tokenizer", "tokenizers", "tiktoken", "sentencepiece_tokenizer.json",
            "state.json", "conversation.json", "session.json"
        ]
        for name in whitelist_cases:
            self.assertFalse(self.is_auth_or_transient_file(name), f"Should not block: {name}")

    def test_14_secondary_profile_token_preservation(self):
        """Ensure that if secondary profile logs in with own Gmail, its token is not deleted on re-seed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys_user = os.path.join(tmp_dir, "sys_user")
            sys_gemini = os.path.join(sys_user, ".gemini")
            os.makedirs(os.path.join(sys_gemini, "antigravity"), exist_ok=True)
            with open(os.path.join(sys_gemini, "antigravity", "token.json"), "w", encoding="utf-8") as f:
                f.write("primary_account_token")

            old_userprofile = os.environ.get("USERPROFILE")
            os.environ["USERPROFILE"] = sys_user

            try:
                prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_02")
                profile = {
                    "id": "profile_02",
                    "name": "Tài khoản 02",
                    "email": "dev2.antigravity@gmail.com",
                    "data_dir": prof_data_dir
                }

                # Seed profile first time
                self.fast_seed_profile(profile)

                # Simulate user logging into Gmail on Profile 02
                prof_gemini = os.path.join(prof_data_dir, "UserProfile", ".gemini", "antigravity")
                os.makedirs(prof_gemini, exist_ok=True)
                prof_token_file = os.path.join(prof_gemini, "token.json")
                with open(prof_token_file, "w", encoding="utf-8") as f:
                    f.write("secondary_dev2_gmail_oauth_token")

                # Re-seed with force=True
                self.fast_seed_profile(profile, force=True)

                # The secondary profile's own login token MUST be preserved
                self.assertTrue(os.path.isfile(prof_token_file), "Secondary Gmail token must be preserved!")
                with open(prof_token_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertEqual(content, "secondary_dev2_gmail_oauth_token")
            finally:
                if old_userprofile is not None:
                    os.environ["USERPROFILE"] = old_userprofile
                else:
                    os.environ.pop("USERPROFILE", None)

    def test_15_globalstorage_and_storage_json_seeding(self):
        """Ensure storage.json and globalStorage are properly seeded to prevent 'Setting up...' hang."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys_user = os.path.join(tmp_dir, "sys_user")
            sys_appdata = os.path.join(tmp_dir, "sys_appdata")
            antigravity_appdata = os.path.join(sys_appdata, "Antigravity")
            user_dir = os.path.join(antigravity_appdata, "User")
            os.makedirs(user_dir, exist_ok=True)

            with open(os.path.join(user_dir, "storage.json"), "w", encoding="utf-8") as f:
                f.write('{"telemetry.machineId": "mock"}')
            with open(os.path.join(antigravity_appdata, "storage.json"), "w", encoding="utf-8") as f:
                f.write('{"openedPathsList": []}')

            old_userprofile = os.environ.get("USERPROFILE")
            old_appdata = os.environ.get("APPDATA")
            os.environ["USERPROFILE"] = sys_user
            os.environ["APPDATA"] = sys_appdata

            try:
                prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_03")
                profile = {
                    "id": "profile_03",
                    "name": "Tài khoản 03",
                    "email": "dev3.antigravity@gmail.com",
                    "data_dir": prof_data_dir
                }

                self.fast_seed_profile(profile)

                # Check storage.json in profile
                prof_storage = os.path.join(prof_data_dir, "User", "storage.json")
                self.assertTrue(os.path.isfile(prof_storage), "User/storage.json must be seeded!")
                prof_root_storage = os.path.join(prof_data_dir, "storage.json")
                self.assertTrue(os.path.isfile(prof_root_storage), "Root storage.json must be seeded!")
            finally:
                if old_userprofile is not None:
                    os.environ["USERPROFILE"] = old_userprofile
                else:
                    os.environ.pop("USERPROFILE", None)
                if old_appdata is not None:
                    os.environ["APPDATA"] = old_appdata
                else:
                    os.environ.pop("APPDATA", None)

    def test_16_config_autofix_corrupted_data_dir(self):
        """Ensure load_config auto-repairs corrupted data_dir values (e.g. '⚪ Chưa đồng bộ', badges, empty)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            appdata = os.path.join(tmp_dir, "AppData", "Roaming")
            os.makedirs(appdata, exist_ok=True)
            cfg_dir = os.path.join(appdata, "Antigravity_Swarm_Manager")
            os.makedirs(cfg_dir, exist_ok=True)
            cfg_file = os.path.join(cfg_dir, "config.json")

            corrupted_config = {
                "antigravity_path": "",
                "profiles": [
                    {"id": "profile_01", "name": "Profile 1", "email": "dev1@gmail.com", "data_dir": "⚪ Chưa đồng bộ"},
                    {"id": "profile_02", "name": "Profile 2", "email": "dev2.antigravity@gmail.com", "data_dir": "⚪ Chưa đồng bộ"},
                    {"id": "profile_03", "name": "Profile 3", "email": "dev3@gmail.com", "data_dir": "🔴 3% (5h) / 🟢 68% (Tuần)"},
                    {"id": "profile_04", "name": "Profile 4", "email": "dev4@gmail.com", "data_dir": ""},
                    {"id": "profile_05", "name": "Profile 5", "email": "dev5@gmail.com", "data_dir": None},
                    {"id": "profile_06", "name": "Profile 6", "email": "dev6@gmail.com", "data_dir": "relative/path/profile_06"},
                ]
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(corrupted_config, f)

            old_appdata = os.environ.get("APPDATA")
            os.environ["APPDATA"] = appdata
            try:
                cfg = self.load_config(target_file=cfg_file)
                profiles = cfg.get("profiles", [])
                self.assertEqual(len(profiles), 10)

                # Check profile_02 preserved email and name
                p2 = next((p for p in profiles if p["id"] == "profile_02"), None)
                self.assertIsNotNone(p2)
                self.assertEqual(p2["email"], "dev2.antigravity@gmail.com")
                self.assertEqual(p2["name"], "Profile 2")

                for p in profiles:
                    data_dir = p.get("data_dir", "")
                    pid = p["id"]
                    self.assertIsInstance(data_dir, str)
                    self.assertTrue(len(data_dir) > 5)
                    self.assertNotIn("⚪", data_dir)
                    self.assertNotIn("Chưa đồng bộ", data_dir)
                    self.assertNotIn("🔴", data_dir)
                    self.assertNotIn("%", data_dir)
                    self.assertTrue(data_dir.endswith(pid) or "Antigravity_Profiles" in data_dir)
            finally:
                if old_appdata is not None:
                    os.environ["APPDATA"] = old_appdata
                else:
                    os.environ.pop("APPDATA", None)

    def test_17_profile_save_never_writes_display_strings(self):
        """Ensure save_config sanitizes profile data_dir and rejects quota display strings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            appdata = os.path.join(tmp_dir, "AppData", "Roaming")
            cfg_dir = os.path.join(appdata, "Antigravity_Swarm_Manager")
            os.makedirs(cfg_dir, exist_ok=True)
            cfg_file = os.path.join(cfg_dir, "config.json")

            old_appdata = os.environ.get("APPDATA")
            os.environ["APPDATA"] = appdata
            try:
                dirty_config = {
                    "profiles": [
                        {"id": "profile_02", "name": "P2", "email": "p2@gmail.com", "data_dir": "⚪ Chưa đồng bộ"},
                        {"id": "profile_03", "name": "P3", "email": "p3@gmail.com", "data_dir": "🟢 90% (5h)"},
                    ]
                }
                self.save_config(dirty_config)
                with open(cfg_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)

                saved_p2 = saved["profiles"][0]
                self.assertNotEqual(saved_p2["data_dir"], "⚪ Chưa đồng bộ")
                self.assertNotIn("Chưa đồng bộ", saved_p2["data_dir"])
                self.assertTrue(saved_p2["data_dir"].endswith("profile_02"))

                saved_p3 = saved["profiles"][1]
                self.assertNotIn("🟢", saved_p3["data_dir"])
                self.assertTrue(saved_p3["data_dir"].endswith("profile_03"))
            finally:
                if old_appdata is not None:
                    os.environ["APPDATA"] = old_appdata
                else:
                    os.environ.pop("APPDATA", None)

    def test_18_fast_seed_complete_directory_structure(self):
        """Verify complete directory hierarchy: UserProfile, extensions, Temp, Cache, antigravity_data, .gemini."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_04")
            profile = {
                "id": "profile_04",
                "name": "Tài khoản 04",
                "email": "dev4@gmail.com",
                "data_dir": prof_data_dir
            }
            ok = self.fast_seed_profile(profile, force=True)
            self.assertTrue(ok)

            expected_dirs = [
                prof_data_dir,
                os.path.join(prof_data_dir, "UserProfile"),
                os.path.join(prof_data_dir, "UserProfile", "AppData", "Roaming"),
                os.path.join(prof_data_dir, "UserProfile", "AppData", "Local"),
                os.path.join(prof_data_dir, "UserProfile", ".gemini", "antigravity"),
                os.path.join(prof_data_dir, "UserProfile", ".antigravity"),
                os.path.join(prof_data_dir, "extensions"),
                os.path.join(prof_data_dir, "Temp"),
                os.path.join(prof_data_dir, "Cache"),
                os.path.join(prof_data_dir, "antigravity_data"),
                os.path.join(prof_data_dir, "User"),
                os.path.join(prof_data_dir, "User", "globalStorage"),
            ]
            for d in expected_dirs:
                self.assertTrue(os.path.isdir(d), f"Missing required directory: {d}")
            self.assertTrue(os.path.isfile(os.path.join(prof_data_dir, ".seed_info.json")))

    def test_19_fast_seed_idempotency_fast_path(self):
        """Verify fast path returns in <50ms even when called repeatedly without master DB."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_05")
            profile = {"id": "profile_05", "name": "P5", "email": "p5@gmail.com", "data_dir": prof_data_dir}

            self.fast_seed_profile(profile, force=True)

            # Test 10 successive fast path calls with force=False
            t0 = __import__("time").time()
            for _ in range(10):
                res = self.fast_seed_profile(profile, force=False)
                self.assertTrue(res)
            total_duration = __import__("time").time() - t0

            # 10 iterations must complete in under 50ms total (<5ms per call)
            self.assertLess(total_duration, 0.05, f"Idempotency too slow: {total_duration*1000:.2f}ms")

    def test_20_fast_seed_fallback_storage_json(self):
        """Verify synthetic storage.json and User/storage.json are created when host files do not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys_user = os.path.join(tmp_dir, "sys_empty_user")
            sys_appdata = os.path.join(tmp_dir, "sys_empty_appdata")
            os.makedirs(sys_user, exist_ok=True)
            os.makedirs(sys_appdata, exist_ok=True)

            old_userprofile = os.environ.get("USERPROFILE")
            old_appdata = os.environ.get("APPDATA")
            os.environ["USERPROFILE"] = sys_user
            os.environ["APPDATA"] = sys_appdata

            try:
                prof_data_dir = os.path.join(tmp_dir, "profiles", "profile_06")
                profile = {"id": "profile_06", "name": "P6", "email": "dev6@gmail.com", "data_dir": prof_data_dir}

                ok = self.fast_seed_profile(profile, force=True)
                self.assertTrue(ok)

                # Verify root storage.json exists and has valid JSON
                root_storage = os.path.join(prof_data_dir, "storage.json")
                self.assertTrue(os.path.isfile(root_storage), "Synthetic root storage.json must exist")
                with open(root_storage, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIn("telemetry.firstSessionDate", data)

                # Verify User/storage.json exists and has valid JSON
                user_storage = os.path.join(prof_data_dir, "User", "storage.json")
                self.assertTrue(os.path.isfile(user_storage), "Synthetic User/storage.json must exist")
                with open(user_storage, "r", encoding="utf-8") as f:
                    udata = json.load(f)
                self.assertIn("telemetry.machineId", udata)
            finally:
                if old_userprofile is not None:
                    os.environ["USERPROFILE"] = old_userprofile
                else:
                    os.environ.pop("USERPROFILE", None)
                if old_appdata is not None:
                    os.environ["APPDATA"] = old_appdata
                else:
                    os.environ.pop("APPDATA", None)

    def test_21_legacy_profile_directories_ignored(self):
        """Ensure legacy directories (Profile_1, Profile_2, profile_dev1, profile_main) are skipped."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            appdata = os.path.join(tmp_dir, "AppData", "Roaming")
            prof_base = os.path.join(appdata, "Antigravity_Profiles")

            legacy_names = ["Profile_1", "Profile_2", "profile_dev1", "profile_main"]
            for leg in legacy_names:
                leg_db_dir = os.path.join(prof_base, leg, "UserProfile", ".gemini", "antigravity")
                os.makedirs(leg_db_dir, exist_ok=True)
                with open(os.path.join(leg_db_dir, "conversation_summaries.db"), "w") as f:
                    f.write("legacy_db_content")

            # Valid standard profile
            valid_db_dir = os.path.join(prof_base, "profile_01", "UserProfile", ".gemini", "antigravity")
            os.makedirs(valid_db_dir, exist_ok=True)
            with open(os.path.join(valid_db_dir, "conversation_summaries.db"), "w") as f:
                f.write("valid_db_content")

            old_appdata = os.environ.get("APPDATA")
            os.environ["APPDATA"] = appdata
            try:
                paths = self.get_all_antigravity_db_paths()
                for p in paths:
                    for leg in legacy_names:
                        self.assertNotIn(os.sep + leg + os.sep, p, f"Legacy dir leaked into DB search: {p}")
                self.assertTrue(any("profile_01" in p for p in paths), "Valid profile_01 DB should be discovered")
            finally:
                if old_appdata:
                    os.environ["APPDATA"] = old_appdata
                else:
                    os.environ.pop("APPDATA", None)

    def test_22_sqlite_explicit_close_no_winerror32(self):
        """Verify SQLite connections and cursors are explicitly closed, preventing WinError 32."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            master_db = os.path.join(tmp_dir, "master_conv.db")
            import sqlite3
            m_conn = sqlite3.connect(master_db)
            m_cur = m_conn.cursor()
            m_cur.execute("CREATE TABLE conversation_summaries (id TEXT PRIMARY KEY, title TEXT)")
            m_cur.execute("INSERT INTO conversation_summaries VALUES ('c1', 'Test')")
            m_conn.commit()
            m_cur.close()
            m_conn.close()

            prof_dir = os.path.join(tmp_dir, "profile_test")
            prof_gemini = os.path.join(prof_dir, "UserProfile", ".gemini", "antigravity")
            os.makedirs(prof_gemini, exist_ok=True)
            target_db = os.path.join(prof_gemini, "conversation_summaries.db")

            profile = {"id": "profile_02", "name": "P2", "email": "p2@gmail.com", "data_dir": prof_dir}

            sys_user = os.path.join(tmp_dir, "sys_user")
            sys_g = os.path.join(sys_user, ".gemini", "antigravity")
            os.makedirs(sys_g, exist_ok=True)
            shutil.copy2(master_db, os.path.join(sys_g, "conversation_summaries.db"))

            old_user = os.environ.get("USERPROFILE")
            os.environ["USERPROFILE"] = sys_user
            try:
                ok = self.fast_seed_profile(profile, force=True)
                self.assertTrue(ok)

                # Verify target db is not locked: we should be able to open, write and remove it immediately
                if os.path.isfile(target_db):
                    with open(target_db, "a+b") as f:
                        f.write(b"lock_check")
                    os.remove(target_db)
            finally:
                if old_user:
                    os.environ["USERPROFILE"] = old_user
                else:
                    os.environ.pop("USERPROFILE", None)

    def test_23_launch_stagger_minimum_interval(self):
        """Verify >=3.0s delay in batch launch loop, complete env isolation, and no direct Google API calls."""
        with open(SWARM_SCRIPT, "r", encoding="utf-8") as f:
            code = f.read()

        # 1. Staggered launch delay check: verify >= 3s in batch launch loop
        launch_delay_match = re.search(r"for prof, proj in to_launch:[\s\S]*?time\.sleep\((\d+(?:\.\d+)?)\)", code)
        self.assertIsNotNone(launch_delay_match, "Launch delay time.sleep not found in batch launch loop")
        delay_val = float(launch_delay_match.group(1))
        self.assertGreaterEqual(delay_val, 3.0, f"Staggered launch delay {delay_val}s is less than required 3.0s!")

        # 2. Environment isolation keys check
        required_env_keys = [
            'custom_env["USERPROFILE"]',
            'custom_env["APPDATA"]',
            'custom_env["LOCALAPPDATA"]',
            'custom_env["TEMP"]',
            'custom_env["TMP"]',
            'custom_env["GEMINI_HOME"]',
            'custom_env["ANTIGRAVITY_DATA_DIR"]'
        ]
        for key in required_env_keys:
            self.assertIn(key, code, f"Missing isolated environment variable assignment: {key}")

        # 3. Verify zero direct Google API network endpoints in code
        google_api_patterns = ["accounts.google.com/o/oauth2", "googleapis.com/oauth2", "oauth2.googleapis.com"]
        for g_api in google_api_patterns:
            self.assertNotIn(g_api, code, f"Forbidden direct Google API call detected: {g_api}")


def run_tests():
    """Run all verification tests and return exit code."""
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTest(loader.loadTestsFromTestCase(TestSwarmCodeStructure))
    suite.addTest(loader.loadTestsFromTestCase(TestQuotaExtractionLogic))
    suite.addTest(loader.loadTestsFromTestCase(TestWebSocketEngine))
    suite.addTest(loader.loadTestsFromTestCase(TestProfileOptimizationAndSync))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
