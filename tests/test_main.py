import ast
import contextlib
import io
import logging
import unittest
from argparse import Namespace
from unittest.mock import patch

import nsbox.__main__ as nsbox_main


class ArgParseTests(unittest.TestCase):
    def test_parse_args(self):
        subtests = (
            (["", "code"], Namespace(code="code", nsjail_args=[], run_args=["-c"])),
            (
                ["", "code", "--time_limit", "0"],
                Namespace(code="code", nsjail_args=["--time_limit", "0"], run_args=["-c"]),
            ),
            (
                ["", "code", "---", "-m", "timeit"],
                Namespace(code="code", nsjail_args=[], run_args=["-m", "timeit"]),
            ),
            (
                ["", "code", "--time_limit", "0", "---", "-m", "timeit"],
                Namespace(code="code", nsjail_args=["--time_limit", "0"], run_args=["-m", "timeit"]),
            ),
            (
                ["", "code", "--time_limit", "0", "---"],
                Namespace(code="code", nsjail_args=["--time_limit", "0"], run_args=[]),
            ),
            (["", "code", "---"], Namespace(code="code", nsjail_args=[], run_args=[])),
        )

        for argv, expected in subtests:
            with self.subTest(argv=argv, expected=expected), patch("sys.argv", argv):
                args = nsbox_main.parse_args()
                self.assertEqual(args, expected)

    @patch("sys.argv", [""])
    def test_parse_args_code_missing_exits(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                nsbox_main.parse_args()

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("the following arguments are required: code", stderr.getvalue())


class EntrypointTests(unittest.TestCase):
    """Integration tests of the CLI entrypoint."""

    def setUp(self):
        logging.getLogger("nsbox.nsjail").setLevel(logging.WARNING)

    @patch("sys.argv", ["", "print('hello'); import sys; print('error', file=sys.stderr)"])
    def test_main_prints_stdout(self):
        """Should print the stdout of the subprocess followed by its stderr."""
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            nsbox_main.main()

        self.assertEqual(stdout.getvalue(), "hello\nerror\n\n")

    @patch("sys.argv", ["", "import sys; sys.exit(22)"])
    def test_main_exits_with_returncode(self):
        """Should exit with the subprocess returncode if it's non-zero."""
        with self.assertRaises(SystemExit) as cm:
            nsbox_main.main()

        self.assertEqual(cm.exception.code, 22)

    def test_main_forwards_args(self):
        """Should forward NsJail args to NsJail and Python args to the Python subprocess."""
        code = "import sys, time; print(sys.orig_argv); time.sleep(2)"
        run_args = ["-R", "-dc"]
        args = ["", code, "--time_limit", "1", "---", *run_args]

        with patch("sys.argv", args), self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                nsbox_main.main()

        orig_argv = ast.literal_eval(stdout.getvalue().strip())
        self.assertListEqual([*run_args, code], orig_argv[-3:])
        self.assertEqual(cm.exception.code, 137, "The time_limit NsJail arg was not respected.")
