"""Tests for scripts/surface_diff.py, on a scratch repository. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("surface_diff", ROOT / "scripts" / "surface_diff.py")
surface_diff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(surface_diff)

API = '''import argparse
from enum import Enum, StrEnum


class DataProductIdentifier(StrEnum):
    l1a_rad = "L1A-RAD"
    l1b_cam = "L1B-CAM"


class Mode(Enum):
    SCIENCE = 1
    SAFE = 2


class Reader:
    def read(self):
        pass

    def close(self):
        pass

    def _buffer(self):
        pass


def convert(x):
    return x


def _helper():
    pass


LIMIT = 3


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--start")
    p.add_argument("-v", "--verbose")
'''

PRODUCT = """attributes:
  ProductID: RAD # the product
  algorithm_version: null
variables:
  RADIANCE:
    dtype: float32
    dimensions: ["TIME", "CHANNEL"]
    attributes:
      long_name: Radiance
      units: W m-2 sr-1
  QUALITY:
    dtype: uint8
    dimensions:
      - TIME
    attributes:
      long_name: >
        Quality flag: one bit per check
      flag_meanings: ok bad
"""

DIMENSIONS = "TIME:\n  long_name: Time\nCHANNEL:\n  size: 4\n"


class Removed(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.tmp)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], check=True)
        self.write("pkg/api.py", API)
        self.write("pkg/old_module.py", "def gone():\n    pass\n")
        self.write("pkg/data/defs/rad.yml", PRODUCT)
        self.write("pkg/data/dimensions.yml", DIMENSIONS)
        self.write("pkg/data/settings.yml", "groups:\n  - name: a\n    size: 1\n")
        self.write("tests/test_api.py", "def test_convert():\n    pass\n")
        self.write("standards/profile.yaml", "surface:\n  identifiers: [DataProductIdentifier]\n")
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:someone/api.git"], check=True)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "init"], check=True)

    def write(self, rel: str, text: str) -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_it(self, *args: str) -> tuple[int, str, str]:
        return self.run_it_on("main", *args)

    def run_it_on(self, base: str, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = surface_diff.main([base, "--product-defs", "pkg/data/**", "--repo", "someone/api", *args])
        return rc, out.getvalue(), err.getvalue()

    def test_the_identifier_classes_come_from_the_standard(self):
        self.write("pkg/api.py", API.replace('    l1b_cam = "L1B-CAM"\n', "").replace("    SAFE = 2\n", ""))
        for identifiers, want in (
            ("[Mode]", ["identifier · Mode.SAFE · pkg/api.py", "enum · DataProductIdentifier.l1b_cam · pkg/api.py · L1B-CAM"]),
            ("[]", ["enum · DataProductIdentifier.l1b_cam · pkg/api.py · L1B-CAM", "enum · Mode.SAFE · pkg/api.py"]),
        ):
            with self.subTest(identifiers=identifiers):
                self.write("standards/profile.yaml", f"surface:\n  identifiers: {identifiers}\n")
                rc, out, err = self.run_it()
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(sorted(out.splitlines()), sorted(want))
        self.write("standards/profile.yaml", "surface: not yet recorded\n")
        rc, out, err = self.run_it()
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("leaves out surface", err)

    def test_nothing_removed_prints_nothing(self):
        self.write("pkg/api.py", API + "\n\ndef added():\n    pass\n")
        self.assertEqual(self.run_it(), (0, "", ""))

    def test_one_removal_of_each_kind(self):
        api = API.replace('    l1b_cam = "L1B-CAM"\n', "").replace("    SAFE = 2\n", "")
        api = api.replace("    def close(self):\n        pass\n\n", "").replace("LIMIT = 3\n", "")
        api = api.replace("def convert(x):", "def to_units(x):").replace('    p.add_argument("--start")\n', "")
        api = api.replace("    def _buffer(self):", "    def _fill(self):").replace("def _helper():", "def _other():")
        self.write("pkg/api.py", api)
        subprocess.run(["git", "mv", "pkg/old_module.py", "pkg/new_module.py"], check=True)
        product = PRODUCT.replace("  algorithm_version: null\n", "").replace("      flag_meanings: ok bad\n", "")
        product = product.replace('["TIME", "CHANNEL"]', '["TIME"]')
        self.write("pkg/data/defs/rad.yml", product.replace("  RADIANCE:", "  RADIANCE_SW:"))
        self.write("pkg/data/dimensions.yml", "TIME:\n  long_name: Time\n")
        self.write("pkg/data/settings.yml", "groups: []\n")
        self.write("tests/test_api.py", "")
        rc, out, err = self.run_it()
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(
            out.splitlines(),
            [
                "enum · Mode.SAFE · pkg/api.py",
                "identifier · DataProductIdentifier.l1b_cam · pkg/api.py · L1B-CAM",
                "name · LIMIT · pkg/api.py",
                "name · Reader.close · pkg/api.py",
                "name · convert · pkg/api.py",
                "option · --start · pkg/api.py",
                "attribute · QUALITY.flag_meanings · pkg/data/defs/rad.yml",
                "attribute · algorithm_version · pkg/data/defs/rad.yml",
                "dimension · CHANNEL · pkg/data/defs/rad.yml",
                "variable · RADIANCE · pkg/data/defs/rad.yml",
                "dimension · CHANNEL · pkg/data/dimensions.yml",
                "module · pkg.old_module · pkg/old_module.py",
            ],
        )

    def commit(self, message: str) -> None:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", message], check=True)

    def test_a_removed_re_export_and_all_entry_are_listed(self):
        init = (
            "from pkg.api import convert\n"
            "from pkg.api import Reader as Reader\n"
            "import pkg.api\n"
            "__all__ = ['convert', 'Reader', 'LIMIT']\n"
            "from pkg.api import LIMIT\n"
        )
        self.write("pkg/__init__.py", init)
        self.write("pkg/plain.py", "from pkg.api import convert\n")
        self.commit("exports")
        self.write("pkg/__init__.py", "import pkg.api\n__all__ = ['LIMIT']\nfrom pkg.api import LIMIT\n")
        self.write("pkg/plain.py", "")
        self.assertEqual(
            self.run_it()[1].splitlines(), ["name · Reader · pkg/__init__.py", "name · convert · pkg/__init__.py"]
        )

    def test_only_re_exports_are_listed_and_guarded_imports_are_not(self):
        self.write(
            "pkg/timing.py",
            "import numpy as np\n"
            "from pkg.api import convert\n"
            "from typing import TYPE_CHECKING\n"
            "__all__ = ['convert']\n"
            "__all__ += ['window']\n\n"
            "def window():\n"
            "    pass\n",
        )
        self.write(
            "pkg/__init__.py",
            "from typing import TYPE_CHECKING\n"
            "from pkg.api import LIMIT as LIMIT\n"
            "if TYPE_CHECKING:\n"
            "    from pkg.api import Reader\n"
            "if __name__ == '__main__':\n"
            "    args = None\n",
        )
        self.commit("timing")
        self.write("pkg/timing.py", "__all__ = []\n")
        self.write("pkg/__init__.py", "")
        self.assertEqual(
            self.run_it()[1].splitlines(),
            ["name · LIMIT · pkg/__init__.py", "name · convert · pkg/timing.py", "name · window · pkg/timing.py"],
        )

    def test_an_all_it_cannot_read_exits_1(self):
        self.write("pkg/__init__.py", "__all__ = ['LIMIT']\n")
        self.commit("init")
        self.write("pkg/__init__.py", "__all__ = sorted(['LIMIT'])\n")
        rc, out, err = self.run_it()
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("pkg/__init__.py:1: an __all__ that is not a literal list of strings", err)

    def test_enum_methods_class_fields_and_guarded_names_are_listed(self):
        self.write(
            "pkg/more.py",
            "from enum import StrEnum\n"
            "from pydantic import BaseModel\n\n"
            "class DataProductIdentifier(StrEnum):\n"
            "    l1b_rad = 'L1B-RAD'\n\n"
            "    @property\n"
            "    def data_level(self):\n"
            "        return 'L1B'\n\n"
            "    def get_bucket(self):\n"
            "        return 'b'\n\n"
            "class Settings(BaseModel):\n"
            "    kernel_dir: str\n"
            "    DEFAULT = 3\n"
            "    _hidden: int = 0\n\n"
            "try:\n"
            "    from fast import accel\n"
            "except ImportError:\n"
            "    def accel():\n"
            "        pass\n\n"
            "if True:\n"
            "    FLAG = 1\n",
        )
        self.commit("more")
        self.write(
            "pkg/more.py",
            "from enum import StrEnum\n"
            "from pydantic import BaseModel\n\n"
            "class DataProductIdentifier(StrEnum):\n"
            "    l1b_rad = 'L1B-RAD'\n\n"
            "class Settings(BaseModel):\n"
            "    pass\n",
        )
        self.assertEqual(
            self.run_it()[1].splitlines(),
            [
                "name · DataProductIdentifier.data_level · pkg/more.py",
                "name · DataProductIdentifier.get_bucket · pkg/more.py",
                "name · FLAG · pkg/more.py",
                "name · Settings.DEFAULT · pkg/more.py",
                "name · Settings.kernel_dir · pkg/more.py",
                "name · accel · pkg/more.py",
            ],
        )

    def test_a_removed_subcommand_and_a_changed_member_value_are_listed(self):
        self.write(
            "pkg/cli.py",
            "def main(sp, cli, app):\n"
            "    sp.add_parser('make-kernel')\n"
            "    cli.command('check')(main)\n"
            "    app.command(name='sync')(main)\n"
            "    app.command(help='no name')(main)\n",
        )
        self.commit("cli")
        self.write("pkg/cli.py", "def main(sp, cli, app):\n    pass\n")
        self.write("pkg/api.py", API.replace('"L1B-CAM"', '"L1B-CAMERA"'))
        self.assertEqual(
            self.run_it()[1].splitlines(),
            [
                "identifier · DataProductIdentifier.l1b_cam · pkg/api.py · L1B-CAM",
                "option · check · pkg/cli.py",
                "option · make-kernel · pkg/cli.py",
                "option · sync · pkg/cli.py",
            ],
        )

    def test_head_diffs_a_commit_and_not_the_working_tree(self):
        subprocess.run(["git", "checkout", "-qb", "change"], check=True)
        self.write("pkg/api.py", API.replace("LIMIT = 3\n", ""))
        self.commit("drop LIMIT")
        subprocess.run(["git", "checkout", "-q", "main"], check=True)
        self.write("pkg/api.py", API.replace("def convert(x):", "def to_units(x):"))
        self.assertEqual(self.run_it("--head", "change"), (0, "name · LIMIT · pkg/api.py\n", ""))
        self.assertEqual(self.run_it()[1], "name · convert · pkg/api.py\n")

    def test_a_deleted_module_lists_its_names_and_itself(self):
        (self.tmp / "pkg/old_module.py").unlink()
        self.assertEqual(
            self.run_it()[1].splitlines(), ["module · pkg.old_module · pkg/old_module.py", "name · gone · pkg/old_module.py"]
        )

    def test_a_definition_outside_the_globs_is_not_read(self):
        self.write("pkg/data/defs/rad.yml", "attributes:\n  ProductID: RAD\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(surface_diff.main(["main", "--product-defs", "other/**"]), 0)
        self.assertEqual(out.getvalue(), "")

    def test_a_binary_file_in_the_diff_is_skipped(self):
        (self.tmp / "pkg/data/kernel.bsp").write_bytes(bytes(range(256)))
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "kernel"], check=True)
        (self.tmp / "pkg/data/kernel.bsp").write_bytes(bytes(range(255, -1, -1)))
        self.write("pkg/api.py", API.replace("LIMIT = 3\n", ""))
        self.assertEqual(self.run_it(), (0, "name · LIMIT · pkg/api.py\n", ""))

    def test_it_reads_the_top_level_paths_from_a_subdirectory(self):
        self.write("pkg/api.py", API.replace("LIMIT = 3\n", ""))
        os.chdir(self.tmp / "pkg")
        for relative in ("false", "true"):
            with self.subTest(diff_relative=relative):
                subprocess.run(["git", "config", "diff.relative", relative], check=True)
                self.assertEqual(self.run_it(), (0, "name · LIMIT · pkg/api.py\n", ""))

    def test_a_non_ascii_path_is_read_as_written(self):
        self.write("pkg/données.py", "def gone():\n    pass\n\n\ndef kept():\n    pass\n")
        self.commit("données")
        self.write("pkg/données.py", "def kept():\n    pass\n")
        subprocess.run(["git", "mv", "pkg/old_module.py", "pkg/nouveau_modèle.py"], check=True)
        self.assertEqual(
            self.run_it(),
            (0, "name · gone · pkg/données.py\nmodule · pkg.old_module · pkg/old_module.py\n", ""),
        )

    def test_the_globs_default_to_the_profile_and_none_is_said(self):
        self.write("pkg/data/dimensions.yml", "TIME:\n  long_name: Time\n")

        def main() -> tuple[str, str]:
            got, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(got), contextlib.redirect_stderr(err):
                self.assertEqual(surface_diff.main(["main"]), 0)
            return got.getvalue(), err.getvalue()
        self.assertEqual(main(), ("", "surface_diff.py: product definitions not read: the profile names no depth.deep globs\n"))
        self.write("standards/profile.yaml", "surface:\n  identifiers: [DataProductIdentifier]\ndepth:\n  deep: ['pkg/data/**']\n")
        self.assertEqual(main(), ("dimension · CHANNEL · pkg/data/dimensions.yml\n", ""))

    def test_a_base_git_does_not_know_exits_1(self):
        rc, out, err = self.run_it_on("no-such-ref")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("surface_diff.py: git merge-base", err)

    def test_a_module_it_cannot_parse_exits_1(self):
        self.write("pkg/api.py", "def broken(:\n")
        rc, out, err = self.run_it()
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("surface_diff.py: pkg/api.py:", err)

    def test_a_definition_line_it_cannot_read_exits_1(self):
        self.write("pkg/data/defs/rad.yml", PRODUCT + "  - stray\n")
        rc, _, err = self.run_it()
        self.assertEqual(rc, 1)
        self.assertIn("a list item with no key above it", err)


if __name__ == "__main__":
    unittest.main()
