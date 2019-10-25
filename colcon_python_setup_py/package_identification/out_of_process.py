import functools
import traceback


class OutOfProcessError(RuntimeError):
    """An exception raised from a different process"""

    def __init__(self, description):
        self.description = description

    def __str__(self):
        return self.description


def out_of_process(fn):
    """Decorator to wrap a function call in a subprocess"""

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
