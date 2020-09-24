# Copyright 2016-2018 Dirk Thomas
# Licensed under the Apache License, Version 2.0

from colcon_core.package_augmentation \
    import PackageAugmentationExtensionPoint
from colcon_core.package_augmentation.python import \
    create_dependency_descriptor
from colcon_core.plugin_system import satisfies_version
from colcon_python_setup_py.package_identification.python_setup_py import \
    get_setup_information


class PythonPackageAugmentation(PackageAugmentationExtensionPoint):
    """Augment Python packages with information from `setup.py` files."""

    # the priority needs to be lower than the extensions augmenting packages
    # using the setup.cfg file
    PRIORITY = 90

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageAugmentationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')

    def augment_package(
        self, desc, *, additional_argument_names=None
    ):  # noqa: D102
        if desc.type != 'python':
            return
        if 'get_python_setup_options' in desc.metadata:
            return

        setup_py = desc.path / 'setup.py'
        if not setup_py.is_file():
            return

        config = get_setup_information(setup_py)

        for dependency_type, option_name in [
            ('build', 'setup_requires'),
            ('run', 'install_requires'),
            ('test', 'tests_require')
        ]:
            desc.dependencies[dependency_type] = {
                create_dependency_descriptor(d)
                for d in config[option_name] or ()}

        def getter(env):
            nonlocal setup_py
            return get_setup_information(setup_py, env=env)

        desc.metadata['get_python_setup_options'] = getter

        desc.metadata['version'] = config['metadata'].get('version')
