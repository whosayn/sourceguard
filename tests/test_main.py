import unittest

from sourceguard import main
from sourceguard.banrule import BanRule


class TestSourceguardRun(unittest.TestCase):

    def test_run_with_empty_diff(self):
        output = main.run("", {})
        self.assertEqual([], output)

    def test_run_with_valid_diff(self):
        diff = """
        --- /dev/null
        +++ b/path/to/file.py
        @@ -0,0 +1,10 @@
        + import os
        +
        + os.chdir(path_to_somewhere)
        """
        banrule = BanRule("os.path.join", "Some description", [])

        output = main.run(diff, {"*.py": [banrule]})
        self.assertEqual(output, [])

    def test_run_with_invalid_diff(self):
        diff = """
        --- /dev/null
        +++ b/path/to/file.py
        @@ -0,0 +1,10 @@
        + import os
        +
        + os.path.join("path1", "path2")
        """
        banrule = BanRule("os.path.join", "Some description", [])

        output = main.run(diff, {"*.py": [banrule]})
        self.assertEqual(output, [("path/to/file.py", "Some description")])

    def test_run_with_excluded_path(self):
        diff = """
        --- /dev/null
        +++ b/path/thirdparty/file.py
        @@ -0,0 +1,10 @@
        + import os
        +
        + os.path.join("path1", "path2")
        """
        banrule = BanRule("os.path.join", "Some description", ["*thirdparty*"])

        output = main.run(diff, {"*.py": [banrule]})
        self.assertEqual(output, [])


if __name__ == '__main__':
    unittest.main()
