import falcon

from nsbox.nsjail import NsJail

from .resources import EvalResource


class NsAPI(falcon.App):
    """
    The main entry point to the nsbox JSON API.

    Forward arguments to a new `NsJail` object.

    Routes:

    - /eval
        Evaluation of Python code

    Error response format:

    >>> {
    ...     "title": "415 Unsupported Media Type",
    ...     "description": "application/xml is an unsupported media type."
    ... }
    """

    def __init__(self, *args, **kwargs):
        super().__init__()

        nsjail_py = NsJail(*args, **kwargs)
        nsjail_js = NsJail(*args, config_path='./config/nsbox_js.cfg', **kwargs)
        nsjail_cs = NsJail(*args, config_path='./config/nsbox_py.cfg', **kwargs)
        self.add_route("/eval", EvalResource(nsjail_py, nsjail_js))
