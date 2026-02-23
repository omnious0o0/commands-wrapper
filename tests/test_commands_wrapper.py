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


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class CommandsWrapperTests(unittest.TestCase):
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
                    os.name,
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
            self.assertTrue((target_bin / cw.SHORT_ALIAS).is_file())

    def test_wrapper_name_from_command_name_normalizes_case(self):
        self.assertEqual(cw._wrapper_name_from_command_name("My Cmd"), "my-cmd")

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

    def test_main_executes_case_insensitive_single_word_command(self):
        db = {
            "OAA": {
                "description": "demo",
                "steps": [{"command": "echo hi"}],
            }
        }

        with mock.patch.object(cw, "load_cmds", return_value=db), mock.patch.object(
            cw, "sync_binaries", return_value=[]
        ), mock.patch.object(
            cw, "_report_sync_messages", return_value=False
        ), mock.patch.object(cw, "exec_cmd") as exec_mock, mock.patch.object(
            sys, "argv", ["commands-wrapper", "oaa"]
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

        with mock.patch.object(cw, "load_cmds", return_value=db), mock.patch.object(
            cw, "sync_binaries", return_value=[]
        ), mock.patch.object(
            cw, "_report_sync_messages", return_value=False
        ), mock.patch.object(cw, "exec_cmd") as exec_mock, mock.patch.object(
            sys, "argv", ["commands-wrapper", "CLAW", "UPD"]
        ):
            cw.main()

        exec_mock.assert_called_once_with("claw upd", db["claw upd"])

    def test_main_list_uses_non_conflict_sync_path(self):
        with mock.patch.object(cw, "load_cmds", return_value={}), mock.patch.object(
            cw, "sync_binaries", return_value=[]
        ) as sync_mock, mock.patch.object(
            cw, "_report_sync_messages", return_value=False
        ), mock.patch.object(cw, "print_list") as list_mock, mock.patch.object(
            sys, "argv", ["commands-wrapper", "list"]
        ):
            cw.main()

        sync_mock.assert_called_once_with({}, report_conflicts=False)
        list_mock.assert_called_once_with({})

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

        install_script = SCRIPT_PATH.parent / "install.sh"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "fake-bin"
            work = root / "work"
            fake_bin.mkdir(parents=True)
            work.mkdir(parents=True)

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
