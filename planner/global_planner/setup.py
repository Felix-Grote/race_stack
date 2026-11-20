import os
from glob import glob
from setuptools import setup

package_name = 'global_planner'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name, package_name + '.route', package_name + '.optimizer',
              package_name + '.speed', package_name + '.annotation',
              package_name + '.operational_centre'],
    package_data={package_name + '.route': ['manifest.schema.json'],
                  package_name + '.annotation': ['ui.html', 'ui.js', 'win95.css'],
                  package_name + '.operational_centre': ['index.html', 'centre.css',
                                                         'centre.js', 'plots.js']},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/**/*.xml', recursive=True)),
        (os.path.join('share', package_name, 'rviz'), glob(os.path.join('rviz', '*.rviz'))),

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
            'global_planner = global_planner.global_planner_node:main',
            'mapping_node = global_planner.mapping_node:main',
            'global_trajectory_publisher = global_planner.global_trajectory_publisher:main',
            'annotation = global_planner.annotation.server:main',
            'operational_centre = global_planner.operational_centre.server:main'
        ],
    },
)
