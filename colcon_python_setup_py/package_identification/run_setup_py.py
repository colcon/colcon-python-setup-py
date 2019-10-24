# Copyright 2019 Rover Robotics via Dan Rose
# Licensed under the Apache License, Version 2.0

import distutils.core
import os


def run_setup_py(cwd, env, script_args=(), stop_after='run'):
    """
    Modify the current process and run setup.py.

    This should be run in a subprocess to not affect the state of the current
    process.

    :param str cwd: absolute path to a directory containing a setup.py script
    :param dict env: environment variables to set before running setup.py
    :param script_args: command-line arguments to pass to setup.py
    :param stop_after: tells setup() when to stop processing
    :returns: the public properties of a Distribution object, minus objects
      with are generally not picklable
    """
    # need to be in setup.py's parent dir to detect any setup.cfg
    os.chdir(cwd)

    os.environ.clear()
    os.environ.update(env)

    result = distutils.core.run_setup(
        'setup.py', script_args=script_args, stop_after=stop_after)

    return {
        key: value for key, value in result.__dict__.items()
        if (
            # Private properties
            not key.startswith('_') and
            # Getter methods
            not callable(value) and
            # Objects that are generally not picklable
            key not in ('cmdclass', 'distclass', 'ext_modules') and
            # These *seem* useful but always have the value 0.
            # Look for their values in the 'metadata' object instead.
            key not in result.display_option_names
        )
    }
