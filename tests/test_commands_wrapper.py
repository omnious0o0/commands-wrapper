import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / ".commands-wrapper" / "commands-wrapper"
)


def _load_cli_module():
    loader = importlib.machinery.SourceFileLoader(
        "commands_wrapper_cli", str(SCRIPT_PATH)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"unable to load CLI module spec from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cw = _load_cli_module()


class _MenuFakeWindow:
    def __init__(self, keys):
        self._keys = list(keys)

    def erase(self):
        return None

    def getmaxyx(self):
        return (24, 80)

    def addstr(self, *args, **kwargs):
        return None

    def refresh(self):
        return None

    def nodelay(self, _enabled):
        return None

    def getch(self):
        if not self._keys:
            return ord("\n")
        return self._keys.pop(0)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class CommandsWrapperTests(unittest.TestCase):
    def test_menu_uppercase_k_navigates_up(self):
        win = _MenuFakeWindow([ord("K"), ord("\n")])
        with mock.patch.multiple(
            cw,
            SEL=lambda: 0,
            DIM=lambda: 0,
            OK=lambda: 0,
            ERR=lambda: 0,
            HDR=lambda: 0,
        ):
            choice = cw.menu(win, "Test", ["one", "two", "three"])
        self.assertEqual(choice, 2)

    def test_menu_uppercase_j_navigates_down(self):
        win = _MenuFakeWindow([ord("J"), ord("\n")])
        with mock.patch.multiple(
            cw,
            SEL=lambda: 0,
            DIM=lambda: 0,
            OK=lambda: 0,
            ERR=lambda: 0,
            HDR=lambda: 0,
        ):
            choice = cw.menu(win, "Test", ["one", "two", "three"])
        self.assertEqual(choice, 1)

    def test_menu_plain_escape_cancels(self):
        win = _MenuFakeWindow([27])
        with (
            mock.patch.multiple(
                cw,
                SEL=lambda: 0,
                DIM=lambda: 0,
                OK=lambda: 0,
                ERR=lambda: 0,
                HDR=lambda: 0,
            ),
            mock.patch.object(cw, "_read_esc_followup_key", return_value=-1),
        ):
            choice = cw.menu(win, "Test", ["one", "two", "three"])
        self.assertIsNone(choice)

    def test_menu_alt_j_moves_down_instead_of_cancel(self):
        win = _MenuFakeWindow([27, ord("\n")])
        with (
            mock.patch.multiple(
                cw,
                SEL=lambda: 0,
                DIM=lambda: 0,
                OK=lambda: 0,
                ERR=lambda: 0,
                HDR=lambda: 0,
            ),
            mock.patch.object(cw, "_read_esc_followup_key", return_value=ord("j")),
        ):
            choice = cw.menu(win, "Test", ["one", "two", "three"])
        self.assertEqual(choice, 1)

    def test_handle_escape_in_form_returns_false_on_plain_escape(self):
        fields = [cw.Field("body", "Body", value="abc", multiline=True)]

        with mock.patch.object(cw, "_read_esc_followup_key", return_value=-1):
            keep_open = cw._handle_escape_in_form(object(), fields, 0)

        self.assertFalse(keep_open)

    @unittest.skipIf(cw.curses is None, "curses unavailable")
    def test_handle_escape_in_form_requeues_non_enter_key(self):
        fields = [cw.Field("body", "Body", value="abc", multiline=True)]

        with (
            mock.patch.object(cw, "_read_esc_followup_key", return_value=ord("x")),
            mock.patch.object(cw.curses, "ungetch") as ungetch_mock,
        ):
            keep_open = cw._handle_escape_in_form(object(), fields, 0)

        self.assertTrue(keep_open)
        ungetch_mock.assert_called_once_with(ord("x"))

    def test_handle_escape_in_form_alt_enter_inserts_newline(self):
        fields = [cw.Field("body", "Body", value="ab", multiline=True)]
        fields[0].cur_y = 0
        fields[0].cur_x = 1

        with mock.patch.object(cw, "_read_esc_followup_key", return_value=10):
            keep_open = cw._handle_escape_in_form(object(), fields, 0)

        self.assertTrue(keep_open)
        self.assertEqual(fields[0].get_value(), "a\nb")

    def test_configure_escape_key_delay_sets_low_delay(self):
        class FakeCurses:
            error = RuntimeError

            def __init__(self):
                self.values = []

            def set_escdelay(self, value):
                self.values.append(value)

        fake_curses = FakeCurses()
        with mock.patch.object(cw, "curses", fake_curses):
            cw._configure_escape_key_delay()

        self.assertEqual(fake_curses.values, [cw.ESC_KEY_DELAY_MS])

    def test_configure_escape_key_delay_ignores_curses_error(self):
        class FakeCurses:
            error = RuntimeError

            def set_escdelay(self, _value):
                raise RuntimeError("unsupported")

        with mock.patch.object(cw, "curses", FakeCurses()):
            cw._configure_escape_key_delay()

    def test_strip_add_yaml_flag_is_scoped_to_add(self):
        argv, has_yaml = cw._strip_add_yaml_flag(["commands-wrapper", "list", "--yaml"])
        self.assertEqual(argv, ["commands-wrapper", "list", "--yaml"])
        self.assertFalse(has_yaml)

    def test_strip_add_yaml_flag_for_add(self):
        argv, has_yaml = cw._strip_add_yaml_flag(
            ["commands-wrapper", "add", "--yaml", "my-cmd"]
        )
        self.assertEqual(argv, ["commands-wrapper", "add", "my-cmd"])
        self.assertTrue(has_yaml)

    def test_strip_add_yaml_flag_for_uppercase_add(self):
        argv, has_yaml = cw._strip_add_yaml_flag(
            ["commands-wrapper", "ADD", "--yaml", "my-cmd"]
        )
        self.assertEqual(argv, ["commands-wrapper", "ADD", "my-cmd"])
        self.assertTrue(has_yaml)

    def test_strip_add_yaml_flag_for_uppercase_yaml_flag(self):
        argv, has_yaml = cw._strip_add_yaml_flag(
            ["commands-wrapper", "add", "--YAML", "my-cmd"]
        )
        self.assertEqual(argv, ["commands-wrapper", "add", "my-cmd"])
        self.assertTrue(has_yaml)

    def test_wizard_add_returns_warning_state_when_sync_has_errors(self):
        with (
            mock.patch.object(
                cw,
                "form_input",
                return_value={"name": "demo", "desc": "desc", "timeout": ""},
            ),
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "_find_case_insensitive_conflict", return_value=None),
            mock.patch.object(
                cw, "steps_editor", return_value=[{"command": "echo hi"}]
            ),
            mock.patch.object(
                cw,
                "save_cmd",
                return_value=(True, ["failed to write wrapper 'x': denied"]),
            ),
            mock.patch.object(cw, "_report_sync_messages", return_value=True),
        ):
            result = cw._wizard_add(object())

        self.assertEqual(result, "saved_with_sync_issues")

    def test_wizard_add_returns_saved_state_when_sync_is_clean(self):
        with (
            mock.patch.object(
                cw,
                "form_input",
                return_value={"name": "demo", "desc": "desc", "timeout": ""},
            ),
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "_find_case_insensitive_conflict", return_value=None),
            mock.patch.object(
                cw, "steps_editor", return_value=[{"command": "echo hi"}]
            ),
            mock.patch.object(cw, "save_cmd", return_value=(True, [])),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
        ):
            result = cw._wizard_add(object())

        self.assertEqual(result, "saved")

    def test_wizard_add_returns_cancelled_when_form_cancelled(self):
        with mock.patch.object(cw, "form_input", return_value=None):
            result = cw._wizard_add(object())

        self.assertEqual(result, "cancelled")

    def test_wizard_add_returns_cancelled_when_steps_editor_cancelled(self):
        with (
            mock.patch.object(
                cw,
                "form_input",
                return_value={"name": "demo", "desc": "desc", "timeout": ""},
            ),
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "_find_case_insensitive_conflict", return_value=None),
            mock.patch.object(cw, "steps_editor", return_value=None),
        ):
            result = cw._wizard_add(object())

        self.assertEqual(result, "cancelled")

    def test_conflict_warning_avoids_leaking_absolute_paths(self):
        db = {
            "extract": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "fake-bin"
            target_bin = Path(tmp) / "target-bin"
            fake_bin.mkdir(parents=True)
            target_bin.mkdir(parents=True)

            conflict_command = fake_bin / "extract"
            conflict_command.write_text(
                "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
            )
            conflict_command.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}, clear=False):
                wrappers, messages, blocked = cw._build_wrapper_map_with_conflicts(
                    db,
                    str(target_bin),
                )

        self.assertNotIn("extract", wrappers)
        self.assertEqual(blocked, {"extract": "extract"})
        self.assertTrue(messages)
        self.assertIn("already used by another executable on PATH", messages[0])
        self.assertNotIn(str(fake_bin), messages[0])

    def test_sync_binaries_can_suppress_conflict_warnings(self):
        db = {
            "extract": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "fake-bin"
            target_bin = Path(tmp) / "target-bin"
            fake_bin.mkdir(parents=True)
            target_bin.mkdir(parents=True)

            conflict_command = fake_bin / "extract"
            conflict_command.write_text(
                "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
            )
            conflict_command.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}, clear=False):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(msg.startswith("WARN:") for msg in messages))
            wrapper_path = target_bin / cw.SHORT_ALIAS
            self.assertTrue(wrapper_path.is_file())
            content = wrapper_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("#!/usr/bin/env sh\n"))

    def test_sync_binaries_does_not_prune_generated_wrappers_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            stale_wrapper = target_bin / "stale-wrapper"
            stale_wrapper.write_text(
                f"#!/usr/bin/env sh\n# {cw.WRAPPER_MARKER}\nexit 0\n",
                encoding="utf-8",
            )
            stale_wrapper.chmod(0o755)

            messages = cw.sync_binaries(
                {},
                bin_dir=str(target_bin),
                platform_name="posix",
                report_conflicts=False,
                prune_stale=False,
            )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            self.assertTrue(stale_wrapper.exists())

    def test_sync_binaries_prunes_generated_wrappers_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            stale_wrapper = target_bin / "stale-wrapper"
            stale_wrapper.write_text(
                f"#!/usr/bin/env sh\n# {cw.WRAPPER_MARKER}\nexit 0\n",
                encoding="utf-8",
            )
            stale_wrapper.chmod(0o755)

            messages = cw.sync_binaries(
                {},
                bin_dir=str(target_bin),
                platform_name="posix",
                report_conflicts=False,
            )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            self.assertFalse(stale_wrapper.exists())

    def test_sync_binaries_targets_module_file_not_sys_argv(self):
        db = {
            "unit test sync target": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            with mock.patch.object(sys, "argv", ["/tmp/stale/cw"]):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            wrapper_path = target_bin / cw.SHORT_ALIAS
            content = wrapper_path.read_text(encoding="utf-8")
            module_path = cw.__file__
            self.assertIsNotNone(module_path)
            expected_target = cw.shlex.quote(os.path.realpath(str(module_path)))
            self.assertIn(f'exec {expected_target} "$@"', content)

    def test_sync_binaries_writes_original_case_wrapper_alias(self):
        db = {
            "OAA": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            self.assertTrue((target_bin / "oaa").is_file())
            self.assertTrue((target_bin / "OAA").is_file())

    def test_sync_binaries_writes_namespace_wrapper_for_multi_word_command(self):
        db = {
            "claw doc": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            self.assertTrue((target_bin / "claw-doc").is_file())
            namespace_wrapper = target_bin / "claw"
            self.assertTrue(namespace_wrapper.is_file())
            namespace_content = namespace_wrapper.read_text(encoding="utf-8")
            self.assertIn(' claw "$@"', namespace_content)

    def test_sync_binaries_marks_command_wrappers_with_wrapper_env(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "cd /tmp"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            wrapper_content = (target_bin / "oc").read_text(encoding="utf-8")
            self.assertIn("COMMANDS_WRAPPER_WRAPPER_ENTRY=1", wrapper_content)
            self.assertIn("COMMANDS_WRAPPER_WRAPPER_NAME=oc", wrapper_content)

    def test_sync_binaries_skips_primary_wrapper_name(self):
        db = {
            "commands-wrapper": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            target_bin = Path(tmp) / "target-bin"
            target_bin.mkdir(parents=True)

            with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
                messages = cw.sync_binaries(
                    db,
                    bin_dir=str(target_bin),
                    platform_name="posix",
                    report_conflicts=False,
                )

            self.assertFalse(any(not msg.startswith("WARN:") for msg in messages))
            self.assertFalse((target_bin / cw.PRIMARY_WRAPPER).is_file())

    def test_wrapper_name_from_command_name_normalizes_case(self):
        self.assertEqual(cw._wrapper_name_from_command_name("My Cmd"), "my-cmd")

    def test_wrapper_name_from_command_name_rejects_primary_wrapper(self):
        self.assertIsNone(cw._wrapper_name_from_command_name(cw.PRIMARY_WRAPPER))

    def test_wrapper_alias_from_command_name_preserves_case(self):
        self.assertEqual(cw._wrapper_alias_from_command_name("OAA"), "OAA")
        self.assertIsNone(cw._wrapper_alias_from_command_name("oaa"))

    def test_wrapper_alias_from_command_name_rejects_primary_wrapper(self):
        self.assertIsNone(cw._wrapper_alias_from_command_name("Commands-Wrapper"))

    def test_build_wrapper_map_adds_case_alias_wrapper(self):
        wrappers, errors = cw._build_wrapper_map(
            {
                "OAA": {
                    "description": "demo",
                    "steps": [{"command": "echo hi"}],
                }
            }
        )

        self.assertFalse(errors)
        self.assertEqual(wrappers.get("oaa"), "OAA")
        self.assertEqual(wrappers.get("OAA"), "OAA")

    def test_build_wrapper_map_adds_namespace_wrapper_for_multi_word_command(self):
        wrappers, errors = cw._build_wrapper_map(
            {
                "claw doc": {
                    "description": "demo",
                    "steps": [{"command": "echo hi"}],
                }
            }
        )

        self.assertFalse(errors)
        self.assertEqual(wrappers.get("claw-doc"), "claw doc")
        self.assertEqual(wrappers.get("claw"), "claw")

    def test_build_command_lookup_index_detects_case_collisions(self):
        index, errors = cw._build_command_lookup_index({"OAA": {}, "oaa": {}})

        self.assertIn("oaa", index)
        self.assertTrue(errors)
        self.assertIn("case-insensitive command name collision", errors[0])

    def test_resolve_command_name_case_insensitive(self):
        db = {
            "OAA": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }
        lookup_index, errors = cw._build_command_lookup_index(db)

        self.assertFalse(errors)
        self.assertEqual(cw._resolve_command_name("oaa", db, lookup_index), "OAA")

    def test_resolve_command_name_preserves_original_key(self):
        db = {
            "Foo ": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }
        lookup_index, errors = cw._build_command_lookup_index(db)

        self.assertFalse(errors)
        self.assertEqual(lookup_index["foo"], "Foo ")
        self.assertEqual(cw._resolve_command_name("foo", db, lookup_index), "Foo ")

    def test_main_executes_case_insensitive_single_word_command(self):
        db = {
            "OAA": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "oaa"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with("OAA", db["OAA"])

    def test_main_executes_case_insensitive_multi_word_command(self):
        db = {
            "claw upd": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "CLAW", "UPD"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with("claw upd", db["claw upd"])

    def test_main_rejects_unresolved_multi_word_for_non_cd_command(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(cw, "_error") as error_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "oc", "dev"]),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        exec_mock.assert_not_called()
        self.assertIn("'oc dev' not found", error_mock.call_args[0][0])

    def test_main_runs_followup_after_single_cd_command(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "cd /tmp"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(cw, "_run_followup_after_cd") as followup_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "oc", "dev"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with(
            "oc",
            db["oc"],
            allow_single_cd_shell=False,
        )
        followup_mock.assert_called_once()
        self.assertEqual(followup_mock.call_args.args[0], "oc")
        self.assertEqual(followup_mock.call_args.args[1], ["dev"])

    def test_main_wrapper_entry_single_cd_stores_pending_context(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "cd /tmp"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_apply_wrapper_cwd_context") as apply_mock,
            mock.patch.object(cw, "_remember_wrapper_cwd_context") as remember_mock,
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(cw.os, "getcwd", return_value="/tmp"),
            mock.patch.object(sys, "argv", ["commands-wrapper", "oc"]),
            mock.patch.dict(
                os.environ,
                {"COMMANDS_WRAPPER_WRAPPER_ENTRY": "1"},
                clear=False,
            ),
        ):
            cw.main()

        apply_mock.assert_not_called()
        exec_mock.assert_called_once_with(
            "oc",
            db["oc"],
            allow_single_cd_shell=False,
        )
        remember_mock.assert_called_once()
        self.assertEqual(remember_mock.call_args.args[1], "/tmp")

    def test_main_wrapper_entry_non_cd_applies_pending_context(self):
        db = {
            "dev": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_apply_wrapper_cwd_context") as apply_mock,
            mock.patch.object(cw, "_remember_wrapper_cwd_context") as remember_mock,
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "dev"]),
            mock.patch.dict(
                os.environ,
                {"COMMANDS_WRAPPER_WRAPPER_ENTRY": "1"},
                clear=False,
            ),
        ):
            cw.main()

        apply_mock.assert_called_once()
        remember_mock.assert_not_called()
        exec_mock.assert_called_once_with("dev", db["dev"])

    def test_main_prefers_exact_command_before_add_yaml_flag_handling(self):
        db = {
            "add --yaml demo": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(
                sys, "argv", ["commands-wrapper", "add", "--yaml", "demo"]
            ),
        ):
            cw.main()

        exec_mock.assert_called_once_with("add --yaml demo", db["add --yaml demo"])

    def test_main_remove_supports_multi_word_command_name(self):
        db = {
            "claw upd": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
                "_source": "/tmp/commands.yaml",
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(
                cw, "remove_from_file", return_value=(True, "", [])
            ) as remove_mock,
            mock.patch.object(cw, "_ok") as ok_mock,
            mock.patch.object(
                sys, "argv", ["commands-wrapper", "remove", "CLAW", "UPD"]
            ),
        ):
            cw.main()

        remove_mock.assert_called_once_with("claw upd", "/tmp/commands.yaml")
        ok_mock.assert_called_once_with("Removed 'claw upd'.")

    def test_main_remove_reports_source_errors(self):
        db = {
            "foo": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
                "_source": "/tmp/missing.yaml",
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(
                cw,
                "remove_from_file",
                return_value=(False, "source file not found: /tmp/missing.yaml", []),
            ),
            mock.patch.object(cw, "_error") as error_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "remove", "foo"]),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        error_mock.assert_called_once_with("source file not found: /tmp/missing.yaml")

    def test_main_remove_reports_sync_errors_after_removal(self):
        db = {
            "foo": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
                "_source": "/tmp/commands.yaml",
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(
                cw,
                "remove_from_file",
                return_value=(True, "", ["failed to write wrapper 'x': denied"]),
            ),
            mock.patch.object(cw, "_report_sync_messages", return_value=True),
            mock.patch.object(cw, "_ok") as ok_mock,
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "remove", "foo"]),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        ok_mock.assert_called_once_with("Removed 'foo'.")
        warn_mock.assert_called_once_with(
            "Removed 'foo', but wrapper sync reported errors."
        )

    def test_run_step_press_key_trims_special_key_names(self):
        class DummyProc:
            def __init__(self):
                self.calls = []

            def sendline(self, text=""):
                self.calls.append(("sendline", text))

            def send(self, text):
                self.calls.append(("send", text))

        proc = DummyProc()
        returned = cw.run_step(proc, {"press_key": "  Enter  "}, timeout=None)

        self.assertIs(returned, proc)
        self.assertEqual(proc.calls, [("sendline", "")])

    def test_run_step_send_wraps_process_io_errors(self):
        class DummyProc:
            def sendline(self, _text=""):
                raise BrokenPipeError("broken pipe")

        with self.assertRaises(ValueError) as exc:
            cw.run_step(DummyProc(), {"send": "hello"}, timeout=None)

        self.assertIn("unable to send input to running command", str(exc.exception))

    def test_exec_cmd_reports_finalize_value_errors(self):
        cfg = {
            "steps": [{"command": "echo hi"}],
        }
        proc = object()

        with (
            mock.patch.object(cw, "run_step", return_value=proc),
            mock.patch.object(
                cw,
                "_finalize_process",
                side_effect=ValueError(
                    "unable to determine exit status for command: echo hi"
                ),
            ),
            mock.patch.object(cw, "_error") as error_mock,
            self.assertRaises(SystemExit) as exc,
        ):
            cw.exec_cmd("demo", cfg)

        self.assertEqual(exc.exception.code, 1)
        error_mock.assert_called_once_with(
            "unable to determine exit status for command: echo hi"
        )

    def test_run_followup_after_cd_executes_named_wrapper_command(self):
        db = {
            "dev": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }
        lookup_index, errors = cw._build_command_lookup_index(db)

        self.assertFalse(errors)
        with mock.patch.object(cw, "exec_cmd") as exec_mock:
            cw._run_followup_after_cd("oc", ["dev"], db, lookup_index)

        exec_mock.assert_called_once_with("dev", db["dev"])

    def test_run_followup_after_cd_ignores_leading_double_dash(self):
        db = {
            "dev": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }
        lookup_index, errors = cw._build_command_lookup_index(db)

        self.assertFalse(errors)
        with mock.patch.object(cw, "exec_cmd") as exec_mock:
            cw._run_followup_after_cd("oc", ["--", "dev"], db, lookup_index)

        exec_mock.assert_called_once_with("dev", db["dev"])

    def test_wrapper_cwd_context_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "cwd-context.yaml"
            with mock.patch.object(
                cw,
                "_wrapper_cwd_context_path",
                return_value=str(context_path),
            ):
                cw._remember_wrapper_cwd_context(12345, "/tmp")
                consumed = cw._consume_wrapper_cwd_context(12345)
                consumed_again = cw._consume_wrapper_cwd_context(12345)

        self.assertEqual(consumed, "/tmp")
        self.assertIsNone(consumed_again)

    def test_pexpect_log_sink_accepts_text_and_bytes(self):
        stream = io.StringIO()
        sink = cw._PExpectLogSink(stream)

        sink.write("hello")
        sink.write(b" world")
        sink.flush()

        self.assertEqual(stream.getvalue(), "hello world")

    @unittest.skipIf(not cw.PEXPECT_AVAILABLE, "pexpect unavailable")
    def test_pexpect_adapter_detaches_logfile_read_by_default(self):
        class DummySpawn:
            def __init__(self):
                self.logfile_read = None

        dummy_spawn = DummySpawn()

        with (
            mock.patch.object(
                cw.pexpect, "spawn", return_value=dummy_spawn
            ) as spawn_mock,
            mock.patch.object(cw, "_shell_name", return_value="/bin/sh"),
        ):
            adapter = cw.PExpectProcessAdapter("echo hi", timeout=None)

        self.assertIs(adapter._proc, dummy_spawn)
        self.assertIsInstance(adapter._log_sink, cw._PExpectLogSink)
        self.assertIsNone(dummy_spawn.logfile_read)
        spawn_mock.assert_called_once_with(
            "/bin/sh",
            ["-c", "echo hi"],
            encoding="utf-8",
            codec_errors="replace",
            timeout=None,
        )

    @unittest.skipIf(not cw.PEXPECT_AVAILABLE, "pexpect unavailable")
    def test_pexpect_adapter_non_interactive_fallback_streams_once(self):
        class DummyProc:
            timeout = 1

            def __init__(self):
                self.logfile_read = None
                self.expect_logfile_read = None

            def interact(self):
                raise OSError("non-interactive")

            def expect(self, _pattern, timeout=None):
                self.expect_logfile_read = self.logfile_read
                return 0

        adapter = cw.PExpectProcessAdapter.__new__(cw.PExpectProcessAdapter)
        adapter._proc = DummyProc()
        adapter._log_sink = object()

        adapter.interact()

        self.assertIs(adapter._proc.expect_logfile_read, adapter._log_sink)
        self.assertIsNone(adapter._proc.logfile_read)

    @unittest.skipIf(not cw.PEXPECT_AVAILABLE, "pexpect unavailable")
    @unittest.skipIf(getattr(cw, "_termios", None) is None, "termios unavailable")
    def test_pexpect_adapter_interact_handles_termios_error(self):
        class DummyProc:
            timeout = 1

            def interact(self):
                raise cw._termios.error(25, "Inappropriate ioctl for device")

            def expect(self, _pattern, timeout=None):
                return 0

        adapter = cw.PExpectProcessAdapter.__new__(cw.PExpectProcessAdapter)
        adapter._proc = DummyProc()
        adapter._log_sink = object()
        adapter.interact()

    def test_find_source_cli_for_build_artifact_resolves_project_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_dir = root / "build" / "scripts-3.12"
            source_dir = root / ".commands-wrapper"
            build_dir.mkdir(parents=True)
            source_dir.mkdir(parents=True)

            build_cli = build_dir / "commands-wrapper"
            source_cli = source_dir / "commands-wrapper"
            build_cli.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            source_cli.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            resolved = cw._find_source_cli_for_build_artifact(str(build_cli))
            self.assertEqual(resolved, str(source_cli.resolve()))

    def test_find_source_cli_for_build_artifact_ignores_non_build_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "commands-wrapper"
            script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            resolved = cw._find_source_cli_for_build_artifact(str(script))
            self.assertIsNone(resolved)

    def test_reexec_if_stale_build_script_execs_source(self):
        with (
            mock.patch.object(
                cw,
                "_find_source_cli_for_build_artifact",
                return_value="/tmp/source-cli",
            ),
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(cw.os, "execv") as execv_mock,
            mock.patch.object(cw.sys, "argv", ["commands-wrapper", "list"]),
            mock.patch.object(cw.sys, "executable", "/usr/bin/python3"),
        ):
            cw._reexec_if_stale_build_script()

        warn_mock.assert_called_once()
        execv_mock.assert_called_once_with(
            "/usr/bin/python3",
            ["/usr/bin/python3", "/tmp/source-cli", "list"],
        )

    def test_reexec_if_stale_build_script_noop_without_source(self):
        with (
            mock.patch.object(
                cw,
                "_find_source_cli_for_build_artifact",
                return_value=None,
            ),
            mock.patch.object(cw.os, "execv") as execv_mock,
        ):
            cw._reexec_if_stale_build_script()

        execv_mock.assert_not_called()

    def test_save_cmd_rejects_case_insensitive_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'OAA:\n  description: uppercase\n  steps:\n    - command: "echo hi"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with mock.patch.dict(os.environ, env, clear=False):
                    saved, messages = cw.save_cmd(
                        "oaa",
                        {
                            "description": "lowercase",
                            "steps": [{"command": "echo conflict"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(saved)
            self.assertTrue(messages)
            self.assertIn("conflicts with existing command", messages[0])

    def test_save_cmd_allows_unrelated_update_despite_global_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                "Foo:\n"
                "  description: first\n"
                "  steps:\n"
                '    - command: "echo foo"\n'
                "foo:\n"
                "  description: colliding\n"
                "  steps:\n"
                '    - command: "echo foo2"\n'
                "Bar:\n"
                "  description: target\n"
                "  steps:\n"
                '    - command: "echo bar"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(cw, "sync_binaries", return_value=[]),
                ):
                    saved, messages = cw.save_cmd(
                        "Bar",
                        {
                            "description": "updated",
                            "steps": [{"command": "echo bar-updated"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(saved)
            self.assertEqual(messages, [])
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)
            self.assertIn("foo:", content)
            self.assertIn("Bar:", content)
            self.assertIn("description: updated", content)

    def test_load_cmds_collects_parse_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands_file = Path(tmp) / "commands.yaml"
            commands_file.write_text("bad: [\n", encoding="utf-8")

            warnings = []
            loaded = cw.load_cmds([str(commands_file)], warnings=warnings)

            self.assertEqual(loaded, {})
            self.assertTrue(warnings)
            self.assertIn("failed to parse command file", warnings[0])

    def test_scan_yaml_files_uses_deterministic_sorted_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "zeta.yaml").write_text("# z\n", encoding="utf-8")
            (directory / "Alpha.yml").write_text("# a\n", encoding="utf-8")
            (directory / ".hidden.yaml").write_text("# hidden\n", encoding="utf-8")
            (directory / "notes.txt").write_text("ignore\n", encoding="utf-8")

            files = cw._scan_yaml_files(str(directory))

            self.assertEqual(
                [Path(path).name for path in files],
                ["Alpha.yml", "zeta.yaml"],
            )

    def test_scan_yaml_files_breaks_casefold_ties_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "A.yaml").write_text("# upper\n", encoding="utf-8")
            (directory / "a.yaml").write_text("# lower\n", encoding="utf-8")

            files = cw._scan_yaml_files(str(directory))

            self.assertEqual([Path(path).name for path in files], ["A.yaml", "a.yaml"])

    def test_preferred_command_file_for_write_defaults_to_global_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            local_file = work / "commands.yaml"
            local_file.write_text("# local\n", encoding="utf-8")

            global_dir = xdg / "commands-wrapper"
            global_dir.mkdir(parents=True)
            global_file = global_dir / "commands.yaml"
            global_file.write_text("# global\n", encoding="utf-8")

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with mock.patch.dict(os.environ, env, clear=False):
                    target = cw._preferred_command_file_for_write()
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(target, str(global_file))

    def test_preferred_command_file_for_write_can_opt_in_to_local_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            local_file = work / "commands.yaml"
            local_file.write_text("# local\n", encoding="utf-8")

            global_dir = xdg / "commands-wrapper"
            global_dir.mkdir(parents=True)
            global_file = global_dir / "commands.yaml"
            global_file.write_text("# global\n", encoding="utf-8")

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
                "COMMANDS_WRAPPER_PREFER_LOCAL_WRITE": "1",
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with mock.patch.dict(os.environ, env, clear=False):
                    target = cw._preferred_command_file_for_write()
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(target, str(local_file))

    def test_sync_messages_with_load_warnings_disables_stale_prune(self):
        with mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock:
            messages = cw._sync_messages_with_load_warnings(
                {},
                ["failed to parse command file 'x': boom"],
            )

        sync_mock.assert_called_once_with(
            {},
            uninstall=False,
            report_conflicts=True,
            prune_stale=False,
        )
        self.assertIn("WARN: failed to parse command file", messages[0])
        self.assertTrue(
            any("skipped stale wrapper cleanup" in message for message in messages)
        )

    def test_sync_messages_can_disable_stale_prune_without_load_warnings(self):
        with mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock:
            messages = cw._sync_messages_with_load_warnings(
                {},
                [],
                prune_stale=False,
            )

        sync_mock.assert_called_once_with(
            {},
            uninstall=False,
            report_conflicts=True,
            prune_stale=False,
        )
        self.assertEqual(messages, [])

    def test_save_cmd_fails_on_invalid_existing_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text("bad: [\n", encoding="utf-8")

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with mock.patch.dict(os.environ, env, clear=False):
                    saved, messages = cw.save_cmd(
                        "safe",
                        {
                            "description": "demo",
                            "steps": [{"command": "echo hi"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(saved)
            self.assertTrue(messages)
            self.assertIn("failed to parse command file", messages[0])
            self.assertEqual(commands_file.read_text(encoding="utf-8"), "bad: [\n")

    def test_save_cmd_returns_error_when_parent_directory_creation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_file = Path(tmp) / "nested" / "commands.yaml"

            with mock.patch.object(cw.os, "makedirs", side_effect=OSError("denied")):
                saved, messages = cw.save_cmd(
                    "safe",
                    {
                        "description": "demo",
                        "steps": [{"command": "echo hi"}],
                    },
                    str(target_file),
                )

            self.assertFalse(saved)
            self.assertTrue(messages)
            self.assertIn("failed to create command directory", messages[0])

    def test_save_cmd_returns_error_when_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'Foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(
                        cw, "_atomic_write_text", side_effect=OSError("disk full")
                    ),
                ):
                    saved, messages = cw.save_cmd(
                        "Bar",
                        {
                            "description": "second",
                            "steps": [{"command": "echo two"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(saved)
            self.assertTrue(messages)
            self.assertIn("failed to write command file", messages[0])

    def test_save_cmd_keeps_file_when_sync_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'Foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(
                        cw,
                        "sync_binaries",
                        return_value=["failed to write wrapper 'x': denied"],
                    ) as sync_mock,
                ):
                    saved, messages = cw.save_cmd(
                        "Bar",
                        {
                            "description": "second",
                            "steps": [{"command": "echo two"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(saved)
            self.assertTrue(messages)
            self.assertIn("failed to write wrapper", "\n".join(messages))
            sync_mock.assert_called_once_with(
                mock.ANY,
                uninstall=False,
                report_conflicts=True,
                prune_stale=False,
            )
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)
            self.assertIn("Bar:", content)

    def test_cmd_add_yaml_exits_nonzero_on_case_insensitive_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'Foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    self.assertRaises(SystemExit) as exc,
                    mock.patch.object(cw, "_error") as error_mock,
                ):
                    cw.cmd_add_yaml(
                        "foo:\n"
                        "  description: conflict\n"
                        "  steps:\n"
                        '    - command: "echo two"\n'
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(exc.exception.code, 1)
            self.assertGreaterEqual(error_mock.call_count, 1)
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)
            self.assertNotIn("foo:\n", content)

    def test_cmd_add_yaml_exits_nonzero_on_exact_name_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    self.assertRaises(SystemExit) as exc,
                    mock.patch.object(cw, "_error") as error_mock,
                ):
                    cw.cmd_add_yaml(
                        "foo:\n"
                        "  description: second\n"
                        "  steps:\n"
                        '    - command: "echo two"\n'
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(exc.exception.code, 1)
            self.assertGreaterEqual(error_mock.call_count, 1)
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("description: first", content)
            self.assertNotIn("description: second", content)

    def test_cmd_add_yaml_persists_commands_when_sync_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text("", encoding="utf-8")

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }
            target_file = commands_file

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(
                        cw,
                        "sync_binaries",
                        return_value=["failed to write wrapper 'x': denied"],
                    ),
                    self.assertRaises(SystemExit) as exc,
                ):
                    target_file = Path(cw._preferred_command_file_for_write())
                    cw.cmd_add_yaml(
                        "new-cmd:\n"
                        "  description: synced later\n"
                        "  steps:\n"
                        '    - command: "echo hi"\n'
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(exc.exception.code, 1)
            self.assertTrue(target_file.exists())
            content = target_file.read_text(encoding="utf-8")
            self.assertIn("new-cmd:", content)

    def test_rename_in_file_rejects_case_insensitive_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                "Foo:\n"
                "  description: first\n"
                "  steps:\n"
                '    - command: "echo foo"\n'
                "Bar:\n"
                "  description: second\n"
                "  steps:\n"
                '    - command: "echo bar"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with mock.patch.dict(os.environ, env, clear=False):
                    renamed, err_message, sync_messages = cw.rename_in_file(
                        "Bar", "foo", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(renamed)
            self.assertIn("conflicts with existing command", err_message)
            self.assertEqual(sync_messages, [])

    def test_rename_in_file_allows_resolving_existing_global_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                "Foo:\n"
                "  description: first\n"
                "  steps:\n"
                '    - command: "echo foo"\n'
                "foo:\n"
                "  description: second\n"
                "  steps:\n"
                '    - command: "echo foo2"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(cw, "sync_binaries", return_value=[]),
                ):
                    renamed, err_message, sync_messages = cw.rename_in_file(
                        "Foo", "Bar", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(renamed)
            self.assertEqual(err_message, "")
            self.assertEqual(sync_messages, [])
            content = commands_file.read_text(encoding="utf-8")
            self.assertNotIn("Foo:", content)
            self.assertIn("Bar:", content)
            self.assertIn("foo:", content)

    def test_remove_from_file_keeps_changes_on_sync_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'Foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(
                        cw,
                        "sync_binaries",
                        return_value=["failed to write wrapper 'x': denied"],
                    ) as sync_mock,
                ):
                    removed, err_message, sync_messages = cw.remove_from_file(
                        "Foo", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(removed)
            self.assertEqual(err_message, "")
            self.assertTrue(sync_messages)
            sync_mock.assert_called_once_with(
                mock.ANY,
                uninstall=False,
                report_conflicts=True,
                prune_stale=False,
            )
            content = commands_file.read_text(encoding="utf-8")
            self.assertNotIn("Foo:", content)

    def test_rename_in_file_keeps_changes_on_sync_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            home = root / "home"
            xdg = root / "xdg"
            work.mkdir(parents=True)
            home.mkdir(parents=True)
            xdg.mkdir(parents=True)

            commands_file = work / "commands.yaml"
            commands_file.write_text(
                'Foo:\n  description: first\n  steps:\n    - command: "echo one"\n',
                encoding="utf-8",
            )

            env = {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
            }

            prev_cwd = os.getcwd()
            try:
                os.chdir(work)
                with (
                    mock.patch.dict(os.environ, env, clear=False),
                    mock.patch.object(
                        cw,
                        "sync_binaries",
                        return_value=["failed to write wrapper 'x': denied"],
                    ) as sync_mock,
                ):
                    renamed, err_message, sync_messages = cw.rename_in_file(
                        "Foo", "Bar", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(renamed)
            self.assertEqual(err_message, "")
            self.assertTrue(sync_messages)
            sync_mock.assert_called_once_with(
                mock.ANY,
                uninstall=False,
                report_conflicts=True,
                prune_stale=False,
            )
            content = commands_file.read_text(encoding="utf-8")
            self.assertNotIn("Foo:", content)
            self.assertIn("Bar:", content)

    def test_main_list_uses_non_conflict_sync_path(self):
        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "print_list") as list_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "list"]),
        ):
            cw.main()

        sync_mock.assert_called_once_with(
            {},
            report_conflicts=False,
            prune_stale=False,
        )
        list_mock.assert_called_once_with({})

    def test_main_list_disables_stale_prune_when_load_has_warnings(self):
        def load_cmds_with_warning(_files, warnings=None):
            if warnings is not None:
                warnings.append("failed to parse command file '/tmp/bad.yaml': boom")
            return {}

        with (
            mock.patch.object(cw, "load_cmds", side_effect=load_cmds_with_warning),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "print_list") as list_mock,
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "list"]),
        ):
            cw.main()

        sync_mock.assert_called_once_with(
            {},
            report_conflicts=False,
            prune_stale=False,
        )
        self.assertTrue(
            any(
                "Skipping stale wrapper cleanup because command files have warnings."
                in call.args[0]
                for call in warn_mock.call_args_list
            )
        )
        list_mock.assert_called_once_with({})

    def test_main_list_rejects_unexpected_trailing_tokens(self):
        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "print_list") as list_mock,
            mock.patch.object(cw, "_error") as error_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "list", "extra"]),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        list_mock.assert_not_called()
        error_mock.assert_called_once_with(f"Usage: {cw.PRIMARY_WRAPPER} list")

    def test_main_add_yaml_rejects_extra_positional_tokens(self):
        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "cmd_add_yaml") as add_yaml_mock,
            mock.patch.object(cw, "_error") as error_mock,
            mock.patch.object(
                sys,
                "argv",
                ["commands-wrapper", "add", "--yaml", "extra"],
            ),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        add_yaml_mock.assert_not_called()
        self.assertIn(
            f"Usage: {cw.PRIMARY_WRAPPER} add --yaml",
            error_mock.call_args[0][0],
        )

    def test_main_internal_cd_target_prints_destination(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "cd /tmp"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries") as sync_mock,
            mock.patch.object(cw, "print") as print_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "__cd-target", "oc"]),
            mock.patch.dict(
                os.environ, {"COMMANDS_WRAPPER_INTERNAL": "1"}, clear=False
            ),
        ):
            cw.main()

        sync_mock.assert_not_called()
        print_mock.assert_called_once_with("/tmp")

    def test_main_internal_cd_target_is_silent_for_non_cd_command(self):
        db = {
            "oc": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries") as sync_mock,
            mock.patch.object(cw, "print") as print_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "__cd-target", "oc"]),
            mock.patch.dict(
                os.environ, {"COMMANDS_WRAPPER_INTERNAL": "1"}, clear=False
            ),
        ):
            cw.main()

        sync_mock.assert_not_called()
        print_mock.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX hook output only")
    def test_main_hook_outputs_dispatch_function_and_identifier_wrappers(self):
        wrappers = {
            "oc": "oc",
            "claw-doc": "claw doc",
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(
                cw,
                "_build_wrapper_map_with_conflicts",
                return_value=(wrappers, [], {}),
            ),
            mock.patch.object(cw, "print") as print_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "hook"]),
        ):
            cw.main()

        printed_lines = [call.args[0] for call in print_mock.call_args_list]
        self.assertIn("__commands_wrapper_dispatch() {", printed_lines)
        self.assertIn('oc() { __commands_wrapper_dispatch oc "$@"; }', printed_lines)
        self.assertIn("alias claw-doc=\"commands-wrapper 'claw doc'\"", printed_lines)

    def test_main_command_execution_suppresses_wrapper_conflict_warnings(self):
        db = {
            "cc": {
                "description": "demo",
                "steps": [{"command": "echo cc"}],
            },
            "extract": {
                "description": "demo",
                "steps": [{"command": "echo extract"}],
            },
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "cc"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with("cc", db["cc"])
        warn_mock.assert_not_called()

    def test_wrapper_conflict_warnings_for_command_filters_unrelated_collisions(self):
        db = {
            "cc": {
                "description": "demo",
                "steps": [{"command": "echo cc"}],
            },
            "extract": {
                "description": "demo",
                "steps": [{"command": "echo extract"}],
            },
        }

        with mock.patch.object(
            cw,
            "_build_wrapper_map_with_conflicts",
            return_value=(
                {},
                ["wrapper name collision for 'extract': 'extract' vs 'extract two'"],
                {"cc": "cc", "extract": "extract"},
            ),
        ):
            warnings = cw._wrapper_conflict_warnings_for_command(
                db,
                "cc",
                "/tmp/target-bin",
            )

        self.assertTrue(any("'cc'" in message for message in warnings))
        self.assertFalse(any("collision" in message for message in warnings))

    def test_main_multi_word_command_suppresses_namespace_conflict_warning(self):
        db = {
            "claw doc": {
                "description": "demo",
                "steps": [{"command": "echo claw"}],
            },
            "extract": {
                "description": "demo",
                "steps": [{"command": "echo extract"}],
            },
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "claw", "doc"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with("claw doc", db["claw doc"])
        warn_mock.assert_not_called()

    def test_sync_binaries_uninstall_does_not_create_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = Path(tmp) / "missing-bin"
            self.assertFalse(missing_dir.exists())

            messages = cw.sync_binaries(
                {},
                uninstall=True,
                bin_dir=str(missing_dir),
                platform_name="posix",
            )

            self.assertEqual(messages, [])
            self.assertFalse(missing_dir.exists())

    def test_main_sync_uninstall_is_not_shadowed_by_user_command(self):
        db = {
            "sync --uninstall": {
                "description": "demo",
                "steps": [{"command": "echo should-not-run"}],
            }
        }

        with (
            mock.patch.object(cw, "load_cmds", return_value=db),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "exec_cmd") as exec_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "sync", "--uninstall"]),
        ):
            cw.main()

        exec_mock.assert_not_called()
        sync_mock.assert_called_once_with(db, uninstall=True)

    def test_main_sync_disables_stale_prune_when_load_has_warnings(self):
        def load_cmds_with_warning(_files, warnings=None):
            if warnings is not None:
                warnings.append("failed to parse command file '/tmp/bad.yaml': boom")
            return {}

        with (
            mock.patch.object(cw, "load_cmds", side_effect=load_cmds_with_warning),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "sync"]),
        ):
            cw.main()

        sync_mock.assert_called_once_with({}, uninstall=False, prune_stale=False)
        self.assertTrue(
            any(
                "Skipping stale wrapper cleanup because command files have warnings."
                in call.args[0]
                for call in warn_mock.call_args_list
            )
        )

    def test_main_sync_uninstall_keeps_default_prune_with_load_warnings(self):
        def load_cmds_with_warning(_files, warnings=None):
            if warnings is not None:
                warnings.append("failed to parse command file '/tmp/bad.yaml': boom")
            return {}

        with (
            mock.patch.object(cw, "load_cmds", side_effect=load_cmds_with_warning),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "sync", "--uninstall"]),
        ):
            cw.main()

        sync_mock.assert_called_once_with({}, uninstall=True)
        self.assertFalse(
            any(
                "Skipping stale wrapper cleanup because command files have warnings."
                in call.args[0]
                for call in warn_mock.call_args_list
            )
        )

    def test_main_sync_rejects_unexpected_args(self):
        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries") as sync_mock,
            mock.patch.object(cw, "_error") as error_mock,
            mock.patch.object(
                sys,
                "argv",
                ["commands-wrapper", "sync", "unexpected", "--uninstall"],
            ),
            self.assertRaises(SystemExit) as exc,
        ):
            cw.main()

        self.assertEqual(exc.exception.code, 1)
        sync_mock.assert_not_called()
        error_mock.assert_called_once_with(
            f"Usage: {cw.PRIMARY_WRAPPER} sync [--uninstall]"
        )

    @unittest.skipIf(os.name == "nt", "requires POSIX shell")
    def test_install_sh_local_source_does_not_require_curl_or_tar(self):
        if not Path("/bin/bash").is_file():
            self.skipTest("/bin/bash not available")

        install_script = SCRIPT_PATH.parent / "install.sh"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            fake_user_base = root / "fake-user-base"
            work = root / "work"
            fake_bin.mkdir(parents=True)
            fake_user_base.mkdir(parents=True)
            work.mkdir(parents=True)

            (work / "pyproject.toml").write_text(
                '[project]\nname = "dummy"\nversion = "0.0.0"\n',
                encoding="utf-8",
            )
            (work / "commands.yaml").write_text("# keep\n", encoding="utf-8")

            python_stub = fake_bin / "python3"
            python_stub.write_text(
                "#!/bin/bash\n"
                "set -e\n"
                'if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "--version" ]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = "-c" ]; then\n'
                '  code="$2"\n'
                '  if [[ "$code" == *"commands-wrapper"* ]]; then\n'
                f"    printf '%s\\n' '{fake_user_base}/bin/commands-wrapper'\n"
                "    exit 0\n"
                "  fi\n"
                f"    printf '%s\\n' '{fake_user_base}/bin'\n"
                "    exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            python_stub.chmod(python_stub.stat().st_mode | stat.S_IEXEC)

            env = os.environ.copy()
            env["PATH"] = str(fake_bin)

            result = subprocess.run(
                ["/bin/bash", str(install_script)],
                cwd=str(work),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("curl not found", result.stdout)
            self.assertNotIn("tar not found", result.stdout)

    @unittest.skipIf(os.name == "nt", "requires POSIX shell")
    def test_install_sh_remote_source_requires_mktemp(self):
        if not Path("/bin/bash").is_file():
            self.skipTest("/bin/bash not available")

        source_install_script = SCRIPT_PATH.parent / "install.sh"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            work = root / "work"
            fake_bin.mkdir(parents=True)
            work.mkdir(parents=True)

            install_script = work / "install.sh"
            install_script.write_text(
                source_install_script.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            install_script.chmod(0o755)

            python_stub = fake_bin / "python3"
            python_stub.write_text(
                "#!/bin/bash\n"
                'if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "--version" ]; then\n'
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            python_stub.chmod(python_stub.stat().st_mode | stat.S_IEXEC)

            for name in ("curl", "tar"):
                stub = fake_bin / name
                stub.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
                stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

            env = os.environ.copy()
            env["PATH"] = str(fake_bin)

            result = subprocess.run(
                ["/bin/bash", str(install_script)],
                cwd=str(work),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "mktemp not found (required for remote install).", result.stdout
            )

    def test_install_ps1_includes_exit_code_guards(self):
        install_ps1 = SCRIPT_PATH.parent / "install.ps1"
        content = install_ps1.read_text(encoding="utf-8")

        self.assertIn("$pyExitCode -eq 0", content)
        self.assertIn("$pythonExitCode -eq 0", content)
        self.assertIn("$LASTEXITCODE -ne 0", content)
        self.assertIn("function Get-PythonScriptsDir", content)
        self.assertIn("function Resolve-WrapperSyncCommand", content)
        self.assertIn("function Test-CommandsWrapperSourceRoot", content)
        self.assertIn(".commands-wrapper", content)
        self.assertIn("COMMANDS_WRAPPER_SOURCE_URL", content)
        self.assertIn("COMMANDS_WRAPPER_SOURCE_SHA256", content)
        self.assertIn("commands-wrapper.exe", content)

    def test_install_sh_uses_sysconfig_scripts_dir_and_no_pre_uninstall(self):
        install_sh = SCRIPT_PATH.parent / "install.sh"
        content = install_sh.read_text(encoding="utf-8")

        self.assertIn("sysconfig.get_path('scripts')", content)
        self.assertIn("COMMANDS_WRAPPER_SOURCE_SHA256", content)
        self.assertNotIn(
            "run_pip uninstall commands-wrapper -y &>/dev/null || true", content
        )

    def test_uninstall_sh_reports_failed_pip_uninstall(self):
        uninstall_sh = SCRIPT_PATH.parent / "uninstall.sh"
        content = uninstall_sh.read_text(encoding="utf-8")

        self.assertIn("failed to uninstall commands-wrapper.", content)
        self.assertNotIn(
            "run_pip uninstall commands-wrapper -y &>/dev/null || true", content
        )

    def test_auto_update_retries_with_diagnostics_after_initial_failure(self):
        update_args = [
            "install",
            "--upgrade",
            "--force-reinstall",
            cw.UPDATE_TARBALL_URL,
        ]

        with (
            mock.patch.dict(
                os.environ,
                {"COMMANDS_WRAPPER_UPDATE_SHA256": ""},
                clear=False,
            ),
            mock.patch.object(cw, "_run_pip", side_effect=[1, 0]) as run_pip_mock,
            mock.patch.object(cw, "find_yamls", return_value=[]),
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(cw, "_ok") as ok_mock,
            self.assertRaises(SystemExit) as exc,
        ):
            cw._auto_update()

        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(
            run_pip_mock.call_args_list,
            [
                mock.call(update_args, suppress_output=True),
                mock.call(update_args),
            ],
        )
        warn_mock.assert_called_once_with(
            "Initial update attempt failed; retrying with diagnostics."
        )
        ok_mock.assert_called_once_with("Update complete.")

    def test_auto_update_surfaces_retry_failure_exit_code(self):
        with (
            mock.patch.dict(
                os.environ,
                {"COMMANDS_WRAPPER_UPDATE_SHA256": ""},
                clear=False,
            ),
            mock.patch.object(cw, "_run_pip", side_effect=[1, 7]),
            mock.patch.object(cw, "_error") as error_mock,
            self.assertRaises(SystemExit) as exc,
        ):
            cw._auto_update()

        self.assertEqual(exc.exception.code, 7)
        error_mock.assert_called_once_with("update failed with exit code 7")

    def test_prepare_update_source_without_hash_uses_default_url(self):
        with mock.patch.dict(
            os.environ,
            {"COMMANDS_WRAPPER_UPDATE_SHA256": ""},
            clear=False,
        ):
            source, cleanup = cw._prepare_update_source()

        self.assertEqual(source, cw.UPDATE_TARBALL_URL)
        self.assertIsNone(cleanup)

    def test_auto_update_rejects_invalid_sha_override(self):
        with (
            mock.patch.dict(
                os.environ,
                {"COMMANDS_WRAPPER_UPDATE_SHA256": "invalid"},
                clear=False,
            ),
            mock.patch.object(cw, "_error") as error_mock,
            self.assertRaises(SystemExit) as exc,
        ):
            cw._auto_update()

        self.assertEqual(exc.exception.code, 1)
        error_mock.assert_called_once_with(
            "invalid COMMANDS_WRAPPER_UPDATE_SHA256 value"
        )

    def test_pip_uninstall_exits_zero_when_package_absent(self):
        with (
            mock.patch.object(cw, "sync_binaries", return_value=[]),
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "_run_pip", return_value=1) as run_pip_mock,
            mock.patch.object(cw, "_warn") as warn_mock,
            self.assertRaises(SystemExit) as exc,
        ):
            cw._pip_uninstall()

        self.assertEqual(exc.exception.code, 0)
        run_pip_mock.assert_called_once_with(
            ["show", cw.PRIMARY_WRAPPER], suppress_output=True
        )
        warn_mock.assert_called_once_with(f"{cw.PRIMARY_WRAPPER} is not installed.")

    def test_uninstall_ps1_includes_exit_code_guards(self):
        uninstall_ps1 = SCRIPT_PATH.parent / "uninstall.ps1"
        content = uninstall_ps1.read_text(encoding="utf-8")

        self.assertIn("$pyExitCode -eq 0", content)
        self.assertIn("$pythonExitCode -eq 0", content)
        self.assertIn("$LASTEXITCODE -ne 0", content)
        self.assertIn("$syncWarning", content)
        self.assertIn("function Get-PythonScriptsDir", content)
        self.assertIn("function Resolve-WrapperSyncCommand", content)
        self.assertIn("commands-wrapper.exe", content)
        self.assertNotIn("commands-wrapper sync --uninstall", content)

    @unittest.skipIf(shutil.which("pwsh") is None, "pwsh is not available")
    def test_install_ps1_falls_back_from_py_to_python(self):
        install_ps1 = SCRIPT_PATH.parent / "install.ps1"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            work = root / "work"
            fake_bin.mkdir(parents=True)
            work.mkdir(parents=True)

            _write_executable(
                fake_bin / "py",
                '#!/bin/sh\nif [ "$1" = "-3" ]; then shift; fi\nexit 7\n',
            )
            _write_executable(
                fake_bin / "python",
                "#!/bin/sh\nexit 0\n",
            )
            _write_executable(
                fake_bin / "commands-wrapper",
                "#!/bin/sh\nexit 0\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(install_ps1)],
                cwd=str(work),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("commands-wrapper installed.", result.stdout)

    @unittest.skipIf(shutil.which("pwsh") is None, "pwsh is not available")
    def test_install_ps1_warns_on_nonzero_sync_exit(self):
        install_ps1 = SCRIPT_PATH.parent / "install.ps1"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            work = root / "work"
            fake_bin.mkdir(parents=True)
            work.mkdir(parents=True)

            _write_executable(
                fake_bin / "py",
                '#!/bin/sh\nif [ "$1" = "-3" ]; then shift; fi\nexit 0\n',
            )
            _write_executable(
                fake_bin / "python",
                "#!/bin/sh\nexit 0\n",
            )
            _write_executable(
                fake_bin / "commands-wrapper",
                "#!/bin/sh\nexit 5\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(install_ps1)],
                cwd=str(work),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn(
                "Installed, but wrapper sync needs a new shell session.",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
