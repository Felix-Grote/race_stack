import os
from glob import glob
from setuptools import setup

package_name = 'global_planner'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/**/*.xml', recursive=True)),
        (os.path.join('share', package_name, 'rviz'), glob(os.path.join('rviz', '*.rviz'))),
        (os.path.join('share', package_name, 'project_a'),
            glob('config/project_a/*.json')),
        (os.path.join('share', package_name, 'project_a', 'fixtures'),
            glob('config/project_a/fixtures/*.json')),
        (os.path.join('share', package_name, 'project_a', 'models'),
            glob('config/project_a/models/*.json')),
        (os.path.join('share', package_name, 'project_a', 'policies'),
            glob('config/project_a/policies/*.json')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ForzaETH',
    maintainer_email='nicolas.baumann@pbl.ee.ethz.ch',
    description='The global planner package',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'compile_route = global_planner.route_compile:main',
            'global_planner = global_planner.global_planner_node:main',
            'mapping_node = global_planner.mapping_node:main',
            'global_trajectory_publisher = global_planner.global_trajectory_publisher:main'
        ],
    },
)
