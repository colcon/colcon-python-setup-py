# Copyright 2016-2018 Dirk Thomas
# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from pathlib import Path
from tempfile import TemporaryDirectory

from colcon_core.package_descriptor import PackageDescriptor
from colcon_python_setup_py.package_augmentation.python_setup_py \
    import PythonPackageAugmentation
from colcon_python_setup_py.package_identification.python_setup_py \
    import _setup_information_cache
from colcon_python_setup_py.package_identification.python_setup_py \
    import PythonPackageIdentification
import pytest


def test_identify():
    extension = PythonPackageIdentification()
    augmentation_extension = PythonPackageAugmentation()

    with TemporaryDirectory(prefix='test_colcon_') as basepath:
        desc = PackageDescriptor(basepath)
        desc.type = 'other'
        assert extension.identify(desc) is None
        assert desc.name is None

        desc.type = None
        _setup_information_cache.clear()
        assert extension.identify(desc) is None
        assert desc.name is None
        assert desc.type is None

        basepath = Path(basepath)
        (basepath / 'setup.py').write_text(
            'from setuptools import setup\n\n'
            'setup(\n'
            "  name='pkg-name',\n"
            ')\n')
        _setup_information_cache.clear()
        assert extension.identify(desc) is None
        assert desc.name == 'pkg-name'
        assert desc.type == 'python'
        assert not desc.dependencies
        assert not desc.metadata

        augmentation_extension.augment_package(desc)
        assert set(desc.dependencies.keys()) == {'build', 'run', 'test'}
        assert not desc.dependencies['build']
        assert not desc.dependencies['run']
        assert not desc.dependencies['test']

        desc = PackageDescriptor(basepath)
        desc.name = 'other-name'
        _setup_information_cache.clear()
        with pytest.raises(RuntimeError) as e:
            extension.identify(desc)
        assert str(e.value).endswith(
            'Package name already set to different value')

        (basepath / 'setup.py').write_text(
            'from setuptools import setup\n\n'
            'setup(\n'
            "  name='other-name',\n"
            "  maintainer='Foo Bar',\n"
            "  maintainer_email='foobar@example.com',\n"
            '  setup_requires=[\n'
            "    'setuptools; sys_platform != \"win32\"',\n"
            "    'colcon-core; sys_platform == \"win32\"',\n"
            '  ],\n'
            '  install_requires=[\n'
            "    'runA > 1.2.3',\n"
            "    'runB',\n"
            '  ],\n'
            '  zip_safe=False,\n'
            ')\n')
        _setup_information_cache.clear()
        assert extension.identify(desc) is None
        assert desc.name == 'other-name'
        assert desc.type == 'python'
        assert not desc.dependencies
        assert not desc.metadata

        augmentation_extension.augment_package(desc)
        assert set(desc.dependencies.keys()) == {'build', 'run', 'test'}
        assert desc.dependencies['build'] == {'setuptools', 'colcon-core'}
        assert desc.dependencies['run'] == {'runA', 'runB'}
        dep = next(x for x in desc.dependencies['run'] if x == 'runA')
        assert dep.metadata['version_gt'] == '1.2.3'
