#!/usr/bin/env python3

import os
import queue
import signal
import sys
import threading

import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String, UInt8

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtGui import QMovie
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

COMMAND_STOP = 0
COMMAND_DANCE_1 = 1
COMMAND_DANCE_2 = 2
COMMAND_DANCE_3 = 3
COMMAND_DANCE_4 = 4

DANCE_NAMES = {
    COMMAND_DANCE_1: 'DANCE 1 - WINGS UP',
    COMMAND_DANCE_2: 'DANCE 2 - WAVE',
    COMMAND_DANCE_3: 'DANCE 3',
    COMMAND_DANCE_4: 'DANCE 4',
}

PREVIEW_FILES = {
    COMMAND_DANCE_1: 'dance1_wings_up.gif',
    COMMAND_DANCE_2: 'dance2_wave.gif',
}

class CheerCommandNode(Node):
    """ROS 2 side of the touchscreen UI.

    Selecting a dance only previews it. The high-level command is published
    only after the user presses START. STOP remains immediate.
    """

    def __init__(self):
        super().__init__('g1_cheer_touchscreen')
        self.command_pub = self.create_publisher(UInt8, '/cheer_command', 10)
        self.status_sub = self.create_subscription(
            String, '/cheer_status', self._status_callback, 10
        )
        self._command_queue = queue.Queue()
        self._latest_status = 'WAITING FOR COMPUTER'
        self._status_lock = threading.Lock()
        self.create_timer(0.05, self._publish_pending_command)

    def queue_command(self, command_id: int):
        self._command_queue.put(command_id)

    def _publish_pending_command(self):
        try:
            command_id = self._command_queue.get_nowait()
        except queue.Empty:
            return

        msg = UInt8()
        msg.data = command_id
        self.command_pub.publish(msg)
        self.get_logger().info(f'Sent cheer command: {command_id}')

    def _status_callback(self, msg: String):
        with self._status_lock:
            self._latest_status = msg.data

    def latest_status(self) -> str:
        with self._status_lock:
            return self._latest_status

class CheerWindow(QMainWindow):
    def __init__(self, ros_node: CheerCommandNode):
        super().__init__()
        self.ros_node = ros_node
        self.selected_dance = None
        self.preview_movie = None

        self.setWindowTitle('G1 Cheer Control')
        self.setMinimumSize(900, 650)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel('G1 CHEER CONTROL')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 30px; font-weight: 700;')
        layout.addWidget(title)

        self.connection_label = QLabel('WAITING FOR COMPUTER')
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet('font-size: 17px; padding: 4px;')
        layout.addWidget(self.connection_label)

        dance_grid = QGridLayout()
        dance_grid.setSpacing(12)
        self.dance_group = QButtonGroup(self)
        self.dance_group.setExclusive(True)

        buttons = [
            ('DANCE 1\nWINGS UP', COMMAND_DANCE_1, 0, 0),
            ('DANCE 2\nWAVE', COMMAND_DANCE_2, 0, 1),
            ('DANCE 3', COMMAND_DANCE_3, 1, 0),
            ('DANCE 4', COMMAND_DANCE_4, 1, 1),
        ]

        for text, command_id, row, column in buttons:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setMinimumHeight(72)
            button.setStyleSheet('font-size: 21px; font-weight: 600;')
            button.clicked.connect(
                lambda checked=False, c=command_id: self.select_dance(c)
            )
            self.dance_group.addButton(button, command_id)
            dance_grid.addWidget(button, row, column)

        layout.addLayout(dance_grid)

        self.selection_label = QLabel('SELECT A DANCE TO PREVIEW')
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_label.setStyleSheet(
            'font-size: 18px; font-weight: 600;'
        )
        layout.addWidget(self.selection_label)

        self.preview_label = QLabel('Preview will appear here')
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(520, 300)
        self.preview_label.setStyleSheet(
            'font-size: 18px; border: 2px solid #808080; border-radius: 8px;'
        )
        layout.addWidget(
            self.preview_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.start_button = QPushButton('START SELECTED DANCE')
        self.start_button.setMinimumHeight(82)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet(
            'font-size: 25px; font-weight: 700;'
        )
        self.start_button.clicked.connect(self.start_selected_dance)
        layout.addWidget(self.start_button)

        stop_button = QPushButton('STOP ROUTINE')
        stop_button.setMinimumHeight(82)
        stop_button.setStyleSheet('font-size: 25px; font-weight: 700;')
        stop_button.clicked.connect(self.stop_routine)
        layout.addWidget(stop_button)

        self.setCentralWidget(root)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(200)

    def select_dance(self, command_id: int):
        """Select and preview a routine without publishing a ROS command."""
        self.selected_dance = command_id
        name = DANCE_NAMES[command_id]
        self.selection_label.setText(
            f'{name} SELECTED - REVIEW PREVIEW, THEN PRESS START'
        )
        self.start_button.setText(f'START {name}')
        preview_ready = self.show_preview(command_id)
        self.start_button.setEnabled(preview_ready)

    def show_preview(self, command_id: int) -> bool:
        if self.preview_movie is not None:
            self.preview_movie.stop()
            self.preview_movie = None
            self.preview_label.setMovie(None)

        filename = PREVIEW_FILES.get(command_id)
        if filename is None:
            self.preview_label.setText(
                f'{DANCE_NAMES[command_id]} PREVIEW\nNOT ASSIGNED YET'
            )
            return False

        package_share = get_package_share_directory('g1_cheer_ui')
        preview_path = os.path.join(package_share, 'media', filename)

        movie = QMovie(preview_path)
        if not movie.isValid():
            self.preview_label.setText(
                f'{DANCE_NAMES[command_id]} PREVIEW COULD NOT BE LOADED'
            )
            return False

        movie.setScaledSize(QSize(300, 295))
        self.preview_label.setText('')
        self.preview_label.setMovie(movie)
        self.preview_movie = movie
        movie.start()
        return True

    def start_selected_dance(self):
        if self.selected_dance is None:
            return

        self.ros_node.queue_command(self.selected_dance)
        self.selection_label.setText(
            f'{DANCE_NAMES[self.selected_dance]} START REQUESTED'
        )

    def stop_routine(self):
        self.ros_node.queue_command(COMMAND_STOP)
        self.selection_label.setText('STOP REQUESTED')

    def refresh_status(self):
        self.connection_label.setText(self.ros_node.latest_status())

def _spin_ros(node: CheerCommandNode):
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)

def main(args=None):
    rclpy.init(args=args)
    node = CheerCommandNode()

    app = QApplication(sys.argv)
    window = CheerWindow(node)
    window.show()

    ros_thread = threading.Thread(
        target=_spin_ros, args=(node,), daemon=True
    )
    ros_thread.start()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    exit_code = app.exec()

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
