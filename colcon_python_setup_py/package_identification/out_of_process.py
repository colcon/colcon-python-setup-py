import functools
import traceback


class OutOfProcessError(RuntimeError):
    """An exception raised from a different process."""

    def __init__(self, description):
        """
        Initialize self.

        :param description: The full formatted exception
        """
        self.description = description

    def __str__(self):
        """Return str(self)."""
        return self.description


def out_of_process(fn):
    """
    Wrap a function in a subprocess.

    Wrapped function will behave the same as the original function, except
    it will run in a different process and exceptions will be wrapped in an
    OutOfProcessError

    :param fn: Function to run in a separate process
    :return: Function that mimics `fn`.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        import multiprocessing

        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)

        def target():
            with child_conn:
                try:
                    result = fn(*args, **kwargs)
                    child_conn.send((True, result))
                except BaseException:
                    child_conn.send((False, traceback.format_exc()))

        with parent_conn:
            p = multiprocessing.Process(
                target=target,
                daemon=True, name='out_of_process ' + fn.__name__
            )
            try:
                p.start()
                ok, value = parent_conn.recv()
                if ok:
                    return value
                else:
                    raise OutOfProcessError(value)
            finally:
                p.terminate()

    return wrapper
