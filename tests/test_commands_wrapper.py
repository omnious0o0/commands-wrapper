import importlib.machinery
import importlib.util
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

    def test_wrapper_name_from_command_name_normalizes_case(self):
        self.assertEqual(cw._wrapper_name_from_command_name("My Cmd"), "my-cmd")

    def test_wrapper_alias_from_command_name_preserves_case(self):
        self.assertEqual(cw._wrapper_alias_from_command_name("OAA"), "OAA")
        self.assertIsNone(cw._wrapper_alias_from_command_name("oaa"))

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
                    messages = cw.save_cmd(
                        "oaa",
                        {
                            "description": "lowercase",
                            "steps": [{"command": "echo conflict"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(messages)
            self.assertIn("conflicts with existing command", messages[0])

    def test_load_cmds_collects_parse_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands_file = Path(tmp) / "commands.yaml"
            commands_file.write_text("bad: [\n", encoding="utf-8")

            warnings = []
            loaded = cw.load_cmds([str(commands_file)], warnings=warnings)

            self.assertEqual(loaded, {})
            self.assertTrue(warnings)
            self.assertIn("failed to parse command file", warnings[0])

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
                    messages = cw.save_cmd(
                        "safe",
                        {
                            "description": "demo",
                            "steps": [{"command": "echo hi"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(messages)
            self.assertIn("failed to parse command file", messages[0])
            self.assertEqual(commands_file.read_text(encoding="utf-8"), "bad: [\n")

    def test_save_cmd_rolls_back_file_when_sync_fails(self):
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
                        side_effect=[["failed to write wrapper 'x': denied"], []],
                    ),
                ):
                    messages = cw.save_cmd(
                        "Bar",
                        {
                            "description": "second",
                            "steps": [{"command": "echo two"}],
                        },
                        str(commands_file),
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertTrue(messages)
            self.assertIn(
                "wrapper sync failed; source file was restored", "\n".join(messages)
            )
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)
            self.assertNotIn("Bar:", content)

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

    def test_remove_from_file_rolls_back_on_sync_failure(self):
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
                        side_effect=[["failed to write wrapper 'x': denied"], []],
                    ),
                ):
                    removed, err_message, sync_messages = cw.remove_from_file(
                        "Foo", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(removed)
            self.assertIn("source file was restored", err_message)
            self.assertTrue(sync_messages)
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)

    def test_rename_in_file_rolls_back_on_sync_failure(self):
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
                        side_effect=[["failed to write wrapper 'x': denied"], []],
                    ),
                ):
                    renamed, err_message, sync_messages = cw.rename_in_file(
                        "Foo", "Bar", str(commands_file)
                    )
            finally:
                os.chdir(prev_cwd)

            self.assertFalse(renamed)
            self.assertIn("source file was restored", err_message)
            self.assertTrue(sync_messages)
            content = commands_file.read_text(encoding="utf-8")
            self.assertIn("Foo:", content)
            self.assertNotIn("Bar:", content)

    def test_main_list_uses_non_conflict_sync_path(self):
        with (
            mock.patch.object(cw, "load_cmds", return_value={}),
            mock.patch.object(cw, "sync_binaries", return_value=[]) as sync_mock,
            mock.patch.object(cw, "_report_sync_messages", return_value=False),
            mock.patch.object(cw, "print_list") as list_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "list"]),
        ):
            cw.main()

        sync_mock.assert_called_once_with({}, report_conflicts=False)
        list_mock.assert_called_once_with({})

    def test_main_command_conflict_warning_only_mentions_target_command(self):
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
            mock.patch.object(
                cw,
                "_build_wrapper_map_with_conflicts",
                return_value=(
                    {"cw": "cw"},
                    [],
                    {"cc": "cc", "extract": "extract"},
                ),
            ),
            mock.patch.object(cw, "_warn") as warn_mock,
            mock.patch.object(sys, "argv", ["commands-wrapper", "cc"]),
        ):
            cw.main()

        exec_mock.assert_called_once_with("cc", db["cc"])
        warning_texts = [str(call.args[0]) for call in warn_mock.call_args_list]
        self.assertTrue(any("'cc'" in text for text in warning_texts))
        self.assertFalse(any("'extract'" in text for text in warning_texts))

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
