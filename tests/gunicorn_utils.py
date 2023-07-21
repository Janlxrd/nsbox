import concurrent.futures
import contextlib
import multiprocessing
import time
from typing import Iterator

from gunicorn.app.wsgiapp import WSGIApplication


class _StandaloneApplication(WSGIApplication):
    def __init__(self, config_path: str = None, **kwargs):
        self.config_path = config_path
        self.options = kwargs

        super().__init__()

    def init(self, parser, opts, args):
        """Patch `opts` to simulate the config path being passed as a command-line argument."""
        super().init(parser, opts, args)
        opts.config = self.config_path

    def load_config(self):
        """Set the option kwargs in the config, then load the config as usual."""
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

        super().load_config()


def _proc_target(config_path: str, event: multiprocessing.Event, **kwargs) -> None:
    """Run a Gunicorn app with the given config and set `event` when Gunicorn is ready."""

    def when_ready(_):
        event.set()

    # Clear sys.argv to prevent Gunicorn from trying to interpret the command arguments
    # used to run the test as it's own arguments.
    import sys

    sys.argv = [""]

    app = _StandaloneApplication(config_path, when_ready=when_ready, **kwargs)

    import logging

    logging.disable(logging.INFO)

    app.run()


@contextlib.contextmanager
def run_gunicorn(config_path: str = "config/gunicorn.conf.py", **kwargs) -> Iterator[None]:
    """
    Run the nsbox app through separate Gunicorn process. Use as a context manager.

    `config_path` is the path to the Gunicorn config to use.
    Additional kwargs are interpreted as Gunicorn settings.

    Raise RuntimeError if Gunicorn terminates before it is ready.
    Raise TimeoutError if Gunicorn isn't ready after 60 seconds.
    """
    event = multiprocessing.Event()
    proc = multiprocessing.Process(target=_proc_target, args=(config_path, event), kwargs=kwargs)

    try:
        proc.start()

        # Wait 60 seconds for Gunicorn to be ready, but exit early if Gunicorn fails.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        concurrent.futures.wait(
            [executor.submit(proc.join), executor.submit(event.wait)],
            timeout=60,
            return_when=concurrent.futures.FIRST_COMPLETED,
        )
        # Can't use the context manager cause wait=False needs to be set.
        executor.shutdown(wait=False, cancel_futures=True)

        if proc.is_alive():
            if not event.is_set():
                raise TimeoutError("Timed out waiting for Gunicorn to be ready.")
        else:
            raise RuntimeError(f"Gunicorn terminated unexpectedly with code {proc.exitcode}.")

        yield
    finally:
        # See https://github.com/python-discord/nsbox/issues/177
        # Sleeping before terminating the process avoids a case where
        # terminating the process can take >30 seconds.
        time.sleep(0.2)

        proc.terminate()

        # Actually wait for the process to finish. There doesn't seem to be a
        # reliable way of checking if process ended or the timeout was reached,
        # so kill the process afterwards to be sure.
        proc.join(timeout=10)
        proc.kill()
