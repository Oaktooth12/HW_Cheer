from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='g1_cheer_ui',
            executable='cheer_receiver',
            name='g1_cheer_command_receiver',
            output='screen',
        ),
    ])
