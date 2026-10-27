#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8

COMMAND_NAMES = {
    0: 'STOP',
    1: 'DANCE 1 - WINGS UP',
    2: 'DANCE 2 - WAVE',
    3: 'DANCE 3',
    4: 'DANCE 4',
    10: 'STEP FORWARD',
    11: 'STEP BACKWARD',
    12: 'STEP LEFT',
    13: 'STEP RIGHT',
}


class CheerCommandReceiver(Node):
    """Safe PC-side test receiver.

    This node does not command the robot. It only proves that the Pi GUI and
    the computer can exchange ROS 2 messages over Ethernet.
    """

    def __init__(self):
        super().__init__('g1_cheer_command_receiver')
        self.command_sub = self.create_subscription(
            UInt8, '/cheer_command', self._command_callback, 10
        )
        self.status_pub = self.create_publisher(String, '/cheer_status', 10)
        self.create_timer(1.0, self._publish_ready)
        self.last_command = None

        self.get_logger().info(
            'Cheer command receiver started. Robot output is disabled.'
        )

    def _publish_status(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)

    def _publish_ready(self):
        if self.last_command is None:
            self._publish_status('READY - COMPUTER CONNECTED')

    def _command_callback(self, msg: UInt8):
        command_id = int(msg.data)
        name = COMMAND_NAMES.get(command_id)

        if name is None:
            self.get_logger().warning(
                f'Ignoring unknown cheer command: {command_id}'
            )
            self._publish_status(f'UNKNOWN COMMAND {command_id}')
            return

        self.last_command = command_id
        self.get_logger().info(
            f'Received cheer command {command_id}: {name}'
        )

        if command_id == 0:
            self._publish_status('STOP RECEIVED - TEST MODE')
        else:
            self._publish_status(f'{name} RECEIVED - TEST MODE')


def main(args=None):
    rclpy.init(args=args)
    node = CheerCommandReceiver()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
