from glob import glob
import os
from setuptools import find_packages, setup

package_name = 'g1_cheer_ui'

setup(
    name=package_name,
    version='0.3.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'media'), glob('media/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='UNCW G1 HCD Team',
    maintainer_email='cst8014@uncw.edu',
    description='Touchscreen command interface for UNCW Unitree G1 cheer routines.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'cheer_gui = g1_cheer_ui.cheer_gui:main',
            'cheer_receiver = g1_cheer_ui.cheer_receiver:main',
        ],
    },
)
