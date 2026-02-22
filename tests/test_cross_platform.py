import importlib.util
from importlib.machinery import SourceFileLoader
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / ".commands-wrapper" / "commands-wrapper"
loader = SourceFileLoader("commands_wrapper_cli", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
if spec is None:
    raise RuntimeError("Failed to create module spec")
commands_wrapper = importlib.util.module_from_spec(spec)
loader.exec_module(commands_wrapper)


class SyncWrappersTests(unittest.TestCase):
    def test_sync_generates_posix_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "hello": {
                    "description": "demo",
                    "steps": [{"command": "echo hi"}],
                }
            }
            commands_wrapper.sync_binaries(db, bin_dir=tmp, platform_name="posix")

            for name in ("cw", "command-wrapper", "hello"):
                path = Path(tmp) / name
                self.assertTrue(path.exists(), f"missing wrapper {name}")
                content = path.read_text(encoding="utf-8")
                self.assertIn(commands_wrapper.WRAPPER_MARKER, content)
                self.assertTrue(os.access(path, os.X_OK), f"wrapper not executable: {name}")

    def test_sync_generates_windows_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "hello": {
                    "description": "demo",
                    "steps": [{"command": "echo hi"}],
                }
            }
            commands_wrapper.sync_binaries(db, bin_dir=tmp, platform_name="nt")

            expected = {
                "cw.cmd",
                "cw.ps1",
                "command-wrapper.cmd",
                "command-wrapper.ps1",
                "hello.cmd",
                "hello.ps1",
            }
            files = {p.name for p in Path(tmp).iterdir() if p.is_file()}
            self.assertEqual(expected, files)

            cmd_content = (Path(tmp) / "hello.cmd").read_text(encoding="utf-8")
            self.assertIn(commands_wrapper.WRAPPER_MARKER, cmd_content)
            self.assertIn("\"hello\" %*", cmd_content)

            ps1_content = (Path(tmp) / "hello.ps1").read_text(encoding="utf-8")
            self.assertIn(commands_wrapper.WRAPPER_MARKER, ps1_content)
            self.assertIn('"hello" @args', ps1_content)

    def test_sync_removes_stale_generated_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "obsolete.cmd"
            stale.write_text(f"REM {commands_wrapper.WRAPPER_MARKER}\n", encoding="utf-8")

            db = {
                "hello": {
                    "description": "demo",
                    "steps": [{"command": "echo hi"}],
                }
            }
            commands_wrapper.sync_binaries(db, bin_dir=tmp, platform_name="nt")
            self.assertFalse(stale.exists())


class ExecutionFallbackTests(unittest.TestCase):
    def test_exec_cmd_with_subprocess_fallback(self):
        original_pexpect = commands_wrapper.pexpect
        commands_wrapper.pexpect = None
        try:
            cfg = {
                "description": "fallback send test",
                "steps 10": [
                    {
                        "command": f"{shlex.quote(sys.executable)} -c \"import sys; print(sys.stdin.readline().strip())\"",
                    },
                    {"send": "FALLBACK_OK"},
                ],
            }
            commands_wrapper.exec_cmd("fallback", cfg)
        finally:
            commands_wrapper.pexpect = original_pexpect


if __name__ == "__main__":
    unittest.main(verbosity=2)
