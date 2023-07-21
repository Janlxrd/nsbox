import logging
from unittest import mock

from falcon import testing

from nsbox.api import NsAPI
from nsbox.process import EvalResult


class NsAPITestCase(testing.TestCase):
    def setUp(self):
        super().setUp()

        self.patcher = mock.patch("nsbox.api.nsapi.NsJail", autospec=True)
        self.mock_nsjail = self.patcher.start()
        self.mock_nsjail.return_value.python3.return_value = EvalResult(
            args=[], returncode=0, stdout="output", stderr="error"
        )
        self.addCleanup(self.patcher.stop)

        logging.getLogger("nsbox.nsjail").setLevel(logging.WARNING)

        self.app = NsAPI()
