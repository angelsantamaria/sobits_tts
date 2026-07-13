import os
from glob import glob
import subprocess
import sys

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py as build_py_orig

package_name = 'sobits_tts'

data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    (os.path.join('share', package_name, 'scripts'), glob('scripts/*.py')),
    (os.path.join('share', package_name, 'soundfile'), glob('soundfile/*')),
]


def add_recursive_files(src_dir, target_base):
    if not os.path.exists(src_dir):
        return

    for root, _, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        install_path = os.path.join(target_base, rel_path)
        file_list = [os.path.join(root, file_name) for file_name in files]
        if file_list:
            data_files.append((install_path, file_list))


class build_py(build_py_orig):
    def run(self):
        prepare_script = os.path.join(
            os.path.dirname(__file__),
            'scripts',
            'prepare_sobits_tts.py',
        )
        subprocess.run([sys.executable, prepare_script], check=True)
        super().run()


add_recursive_files('install/supertonic', os.path.join('share', package_name, 'install/supertonic'))

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=data_files,
    install_requires=[
        'setuptools',
        'numpy',
        'soundfile',
        'pygame',
        'av',
        'piper-tts',
        'onnxruntime',
    ],
    zip_safe=True,
    maintainer='sobits',
    maintainer_email='f22hakuti@gmail.com',
    description='TTS package for ROS 2',
    license='BSD-3-Clause',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'tts_action_server = sobits_tts.tts_action_server:main',
            'tts_action_client = sobits_tts.tts_action_client:main',
        ],
    },
    cmdclass={'build_py': build_py},
)
