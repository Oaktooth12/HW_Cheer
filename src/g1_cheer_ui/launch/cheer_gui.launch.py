from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='g1_cheer_ui',
            executable='cheer_gui',
            name='g1_cheer_touchscreen',
            output='screen',
        ),
    ])
