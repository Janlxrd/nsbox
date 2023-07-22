from __future__ import annotations

import logging
from typing import Union

import falcon
from falcon.media.validators.jsonschema import validate

from nsbox.nsjail import NsJail

__all__ = ("EvalResource",)

from nsbox.nsio import FileAttachment, ParsingError

log = logging.getLogger(__name__)

class EvalResource:
    """
    Evaluation of Python and Node.js code.

    Supported methods:

    - POST /eval
        Evaluate Python or Node.js code and return the result
    """

    REQ_SCHEMA = {
        "type": "object",
        "properties": {
            "language": {"type": "string", "enum": ["python", "nodejs", "csharp"]},
            "input": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            # Disallow starting with / or containing \0 anywhere
                            "pattern": r"^(?!/)(?!.*\\0).*$",
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        },
        "anyOf": [
            {"required": ["language", "input"]},
            {"required": ["language", "args"]},
        ],
    }

    def __init__(self, nsjail_py: NsJail, nsjail_js: NsJail, nsjail_cs: NsJail):
        self.nsjail_py = nsjail_py
        self.nsjail_js = nsjail_js
        self.nsjail_cs = nsjail_cs

    @validate(REQ_SCHEMA)
    def on_post(self, req: falcon.Request, resp: falcon.Response) -> None:
        """
        Evaluate Python or Node.js code and return stdout, stderr, and the return code.

        A list of arguments for the Python or Node.js subprocess can be specified as `args`.

        If `input` is specified, it will be appended as the last argument to `args`,
        and `args` will have a default argument of `"-c"` for Python and `"-e"` for Node.js.

        Either `input` or `args` must be specified.

        The return codes mostly resemble those of a Unix shell. Some noteworthy cases:

        - None
            The NsJail process failed to launch or the output was invalid Unicode
        - 137 (SIGKILL)
            Typically because NsJail killed the process due to time or memory constraints
        - 255
            NsJail encountered a fatal error

        Request body:

        >>> {
        ...    "language": "python",
        ...    "input": "print('Hello')"
        ... }

        >>> {
        ...    "language": "python",
        ...    "args": ["-c", "print('Hello')"]
        ... }

        >>> {
        ...    "language": "nodejs",
        ...    "input": "console.log('Hello');"
        ... }

        >>> {
        ...    "language": "nodejs",
        ...    "args": ["-e", "console.log('Hello');"]
        ... }

        >>> {
        ...    "language": "csharp",
        ...    "input": "Console.WriteLine('hi');"
        ... }

        Response format:

        >>> {
        ...     "stdout": "10000 loops, best of 5: 23.8 usec per loop",
        ...     "returncode": 0,
        ...     "files": [
        ...         {
        ...             "path": "output.png",
        ...             "size": 57344,
        ...             "content": "eJzzSM3...="  # Base64
        ...         }
        ...     ]
        ... }

        Status codes:

        - 200
            Successful evaluation; not indicative that the input code itself works
        - 400
           Input JSON schema is invalid
        - 415
            Unsupported content type; only application/JSON is supported
        """
        body: dict[str, Union[str, list[str], list[dict[str, str]]]] = req.media
        language = body.get("language")

        if language not in ["python", "nodejs", "csharp"]:
            raise falcon.HTTPBadRequest(title="Invalid language", description="Supported languages are 'python', 'nodejs' and 'csharp'")

        if language == "python":
            if "input" in body:
                body.setdefault("args", ["-c"])
                body["args"].append(body["input"])
            try:
                result = self.nsjail_py.run_code(
                    run_args=body["args"],
                    files=[FileAttachment.from_dict(file) for file in body.get("files", [])],
                )
            except ParsingError as e:
                raise falcon.HTTPBadRequest(title="Request file is invalid", description=str(e))
            except Exception:
                log.exception("An exception occurred while trying to process the request")
                raise falcon.HTTPInternalServerError
        elif language == "nodejs":
            if "input" in body:
                body.setdefault("args", ["-e"])
                body["args"].append(body["input"])
            try:
                result = self.nsjail_js.run_code(
                    run_args=body["args"],
                    files=[FileAttachment.from_dict(file) for file in body.get("files", [])],
                )
            except ParsingError as e:
                raise falcon.HTTPBadRequest(title="Request file is invalid", description=str(e))
            except Exception:
                log.exception("An exception occurred while trying to process the request")
                raise falcon.HTTPInternalServerError
        elif language == "csharp":
            if "input" in body:
                body.setdefault("args", ["-e"])
                body["args"].append(body["input"])
            try:
                result = self.nsjail_cs.run_code(
                    run_args=body["args"],
                    files=[FileAttachment.from_dict(file) for file in body.get("files", [])],
                )
            except ParsingError as e:
                raise falcon.HTTPBadRequest(title="Request file is invalid", description=str(e))
            except Exception:
                log.exception("An exception occurred while trying to process the request")
                raise falcon.HTTPInternalServerError
        else:
            # This should never happen if the schema is correctly enforced, but it's a good practice to handle it.
            raise falcon.HTTPBadRequest(title="Invalid language", description="Supported languages are 'python', 'nodejs' and 'csharp'")

        resp.media = {
            "stdout": result.stdout,
            "returncode": result.returncode,
            "files": [f.as_dict for f in result.files],
        }