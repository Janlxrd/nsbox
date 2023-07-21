from tests.api import NsAPITestCase


class TestEvalResource(NsAPITestCase):
    PATH = "/eval"

    def test_post_valid_200(self):
        cases = [
            {"args": ["-c", "print('output')"]},
            {"input": "print('hello')"},
            {"input": "print('hello')", "args": ["-c"]},
            {"input": "print('hello')", "args": [""]},
            {"input": "pass", "args": ["-m", "timeit"]},
        ]
        for body in cases:
            with self.subTest():
                result = self.simulate_post(self.PATH, json=body)
                self.assertEqual(result.status_code, 200)
                self.assertEqual("output", result.json["stdout"])
                self.assertEqual(0, result.json["returncode"])

    def test_post_invalid_schema_400(self):
        body = {"stuff": "foo"}
        result = self.simulate_post(self.PATH, json=body)

        self.assertEqual(result.status_code, 400)

        expected = {
            "title": "Request data failed validation",
            "description": "{'stuff': 'foo'} is not valid under any of the given schemas",
        }

        self.assertEqual(expected, result.json)

    def test_post_invalid_data_400(self):
        bodies = ({"args": 400}, {"args": [], "files": [215]})
        expects = ["400 is not of type 'array'", "215 is not of type 'object'"]
        for body, expected in zip(bodies, expects):
            with self.subTest():
                result = self.simulate_post(self.PATH, json=body)

                self.assertEqual(result.status_code, 400)

                expected_json = {
                    "title": "Request data failed validation",
                    "description": expected,
                }
                self.assertEqual(expected_json, result.json)

    def test_files_path(self):
        """Normal paths should work with 200."""
        test_paths = [
            "file.txt",
            "./0.jpg",
            "path/to/file",
            "folder/../hm",
            "folder/./to/./somewhere",
            "traversal/but/../not/beyond/../root",
            r"backslash\\okay",
            r"backslash\okay",
            "numbers/0123456789",
        ]
        for path in test_paths:
            with self.subTest(path=path):
                body = {"args": ["test.py"], "files": [{"path": path}]}
                result = self.simulate_post(self.PATH, json=body)
                self.assertEqual(result.status_code, 200)
                self.assertEqual("output", result.json["stdout"])
                self.assertEqual(0, result.json["returncode"])

    def test_files_illegal_path_traversal(self):
        """Traversal beyond root should be denied with 400 error."""
        test_paths = [
            "../secrets",
            "../../dir",
            "dir/../../secrets",
            "dir/var/../../../file",
        ]
        for path in test_paths:
            with self.subTest(path=path):
                body = {"args": ["test.py"], "files": [{"path": path}]}
                result = self.simulate_post(self.PATH, json=body)
                self.assertEqual(result.status_code, 400)
                expected = {
                    "title": "Request file is invalid",
                    "description": f"File path '{path}' may not traverse beyond root",
                }
                self.assertEqual(expected, result.json)

    def test_files_illegal_path_absolute(self):
        """Absolute file paths should 400-error at json schema validation stage."""
        test_paths = [
            "/",
            "/etc",
            "/etc/vars/secrets",
            "/absolute",
            "/file.bin",
        ]
        for path in test_paths:
            with self.subTest(path=path):
                body = {"args": ["test.py"], "files": [{"path": path}]}
                result = self.simulate_post(self.PATH, json=body)
                self.assertEqual(result.status_code, 400)
                self.assertEqual("Request data failed validation", result.json["title"])
                self.assertIn("does not match", result.json["description"])

    def test_files_illegal_path_null_byte(self):
        """Paths containing \0 should 400-error at json schema validation stage."""
        test_paths = [
            r"etc/passwd\0",
            r"a\0b",
            r"\0",
            r"\\0",
            r"var/\0/path",
        ]
        for path in test_paths:
            with self.subTest(path=path):
                body = {"args": ["test.py"], "files": [{"path": path}]}
                result = self.simulate_post(self.PATH, json=body)
                self.assertEqual(result.status_code, 400)
                self.assertEqual("Request data failed validation", result.json["title"])
                self.assertIn("does not match", result.json["description"])

    def test_post_invalid_content_type_415(self):
        body = "{'input': 'foo'}"
        headers = {"Content-Type": "application/xml"}
        result = self.simulate_post(self.PATH, body=body, headers=headers)

        self.assertEqual(result.status_code, 415)

        expected = {
            "title": "415 Unsupported Media Type",
            "description": "application/xml is an unsupported media type.",
        }

        self.assertEqual(expected, result.json)

    def test_disallowed_method_405(self):
        result = self.simulate_get(self.PATH)
        self.assertEqual(result.status_code, 405)

    def test_options_allow_post_only(self):
        result = self.simulate_options(self.PATH)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers.get("Allow"), "POST")
