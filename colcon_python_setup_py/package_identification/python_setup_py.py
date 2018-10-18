# Copyright 2016-2018 Dirk Thomas
# Licensed under the Apache License, Version 2.0

import ast
import distutils.core
import os
from pathlib import Path
import runpy
try:
    import setuptools
except ImportError:
    pass
import subprocess
import sys
from threading import Lock

from colcon_core.package_identification import logger
from colcon_core.package_identification \
    import PackageIdentificationExtensionPoint
from colcon_core.package_identification.python import \
    create_dependency_descriptor
from colcon_core.plugin_system import satisfies_version


class PythonPackageIdentification(PackageIdentificationExtensionPoint):
    """Identify Python packages with `setup.py` files."""

    # the priority needs to be lower than the extensions identifying packages
    # using the setup.cfg file
    PRIORITY = 90

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageIdentificationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')

    def identify(self, desc):  # noqa: D102
        if desc.type is not None and desc.type != 'python':
            return

        setup_py = desc.path / 'setup.py'
        if not setup_py.is_file():
            return

        kwargs = get_setup_arguments(setup_py)
        data = extract_data(**kwargs)

        if desc.type is not None and desc.type != 'python':
            logger.error('Package type already set to different value')
            raise RuntimeError('Package type already set to different value')
        desc.type = 'python'
        if desc.name is not None and desc.name != data['name']:
            logger.error('Package name already set to different value')
            raise RuntimeError('Package name already set to different value')
        desc.name = data['name']
        for key in ('build', 'run', 'test'):
            desc.dependencies[key] |= data['%s_depends' % key]

        path = str(desc.path)

        def getter(env):
            nonlocal path
            return get_setup_arguments_with_context(
                os.path.join(path, 'setup.py'), env)

        desc.metadata['get_python_setup_options'] = getter


cwd_lock = None


def get_setup_arguments(setup_py):
    """
    Capture the arguments of the setup() function in the setup.py file.

    The function is being run within the current Python interpreter.
    Therefore the processed setup.py file can not have any additional
    dependencies not available in the current environment.

    :param setup_py: the path to the setup.py file
    :returns: a dictionary containing the arguments of the setup() function
    :rtype: dict
    """
    global cwd_lock
    if not cwd_lock:
        cwd_lock = Lock()
    setup_py = Path(str(setup_py))
    assert setup_py.name == 'setup.py'
    # prevent side effects in other threads
    with cwd_lock:
        # change to the directory containing the setup.py file
        old_cwd = os.getcwd()
        os.chdir(str(setup_py.parent))
        try:
            data = {}
            mock_setup = create_mock_setup_function(data)
            # replace setup() function of distutils and setuptools
            # in order to capture its arguments
            try:
                distutils_setup = distutils.core.setup
                distutils.core.setup = mock_setup
                try:
                    setuptools_setup = setuptools.setup
                    setuptools.setup = mock_setup
                except NameError:
                    pass
                # evaluate the setup.py file
                runpy.run_path(str(setup_py))
            finally:
                distutils.core.setup = distutils_setup
                try:
                    setuptools.setup = setuptools_setup
                except NameError:
                    pass
            # filter out any data which doesn't work with ast.literal_eval
            for key, value in list(data.items()):
                try:
                    ast.literal_eval(repr(value))
                except SyntaxError:
                    del data[key]
            return data

        finally:
            os.chdir(old_cwd)


def create_mock_setup_function(data):
    """
    Create a mock function to capture its arguments.

    It can replace either distutils.core.setup or setuptools.setup.

    :param data: a dictionary which is updated with the captured arguments
    :returns: a function to replace distutils.core.setup and setuptools.setup
    :rtype: callable
    """
    def setup(*args, **kwargs):
        if args:
            raise RuntimeError(
                'setup() function invoked with positional arguments')
        data.update(kwargs)

    return setup


def extract_data(**kwargs):
    """
    Extract information from known keyword arguments to the setup function.

    The `name` attribute is required and returned under the `name` key.
    The following dependencies are stripped of their version specifier.
    The `setup_requires` items are returned as `build_depends`.
    The `install_requires` items are returned as `run_depends`.
    The `tests_require` items are returned as `test_depends`.

    :param dict kwargs: The keywords
    :rtype: dict
    :raises RuntimeError: if the keywords don't contain `name`
    """
    if 'name' not in kwargs:
        raise RuntimeError(
            "setup() function invoked without the keyword argument 'name'")
    data = {'name': kwargs['name']}

    mapping = {
        'setup_requires': 'build_depends',
        'install_requires': 'run_depends',
        'tests_require': 'test_depends',
    }
    for keyword, key in mapping.items():
        data[key] = set()
        for dep in kwargs.get(keyword, []):
            descriptor = create_dependency_descriptor(dep)
            data[key].add(descriptor)
    return data


def get_setup_arguments_with_context(setup_py, env):
    """
    Capture the arguments of the setup() function in the setup.py file.

    To provide a custom environment when introspecting the setup() function
    a separate Python interpreter is being used which can have an extended
    PYTHONPATH etc.

    :param setup_py: The path of the setup.py file
    :param dict env: The environment variables to use when invoking the file
    :returns: a dictionary containing the arguments of the setup() function
    :rtype: dict
    """
    pkg_path = Path(__file__).parents[3]
    if sys.platform == 'win32':
        pkg_path = str(pkg_path).replace(os.sep, os.altsep)
        setup_py = str(setup_py).replace(os.sep, os.altsep)
    code_lines = [
        'import sys',
        "sys.path.insert(0, '%s')" % pkg_path,
        'from colcon_python_setup_py.package_identification.python_setup_py'
        ' import get_setup_arguments',
        "print(repr(get_setup_arguments('%s')))" % setup_py]

    # invoke get_setup_arguments() in a separate interpreter
    cmd = [sys.executable, '-c', ';'.join(code_lines)]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, env=env, check=True)
    output = result.stdout.decode()

    return ast.literal_eval(output)
