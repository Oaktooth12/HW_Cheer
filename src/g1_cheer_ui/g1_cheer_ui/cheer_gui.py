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

from PyQt6.QtCore import QElapsedTimer, QTimer, Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

COMMAND_STOP = 0
COMMAND_DANCE_1 = 1
COMMAND_DANCE_2 = 2
COMMAND_DANCE_3 = 3
COMMAND_DANCE_4 = 4

COMMAND_STEP_FORWARD = 10
COMMAND_STEP_BACKWARD = 11
COMMAND_STEP_LEFT = 12
COMMAND_STEP_RIGHT = 13

HOLD_TO_START_MS = 5000

DANCE_NAMES = {
    COMMAND_DANCE_1: 'DANCE 1 - WINGS UP',
    COMMAND_DANCE_2: 'DANCE 2 - WAVE',
    COMMAND_DANCE_3: 'DANCE 3',
    COMMAND_DANCE_4: 'DANCE 4',
}

PREVIEW_FILES = {
    COMMAND_DANCE_1: 'dance1_wings_up.mp4',
    COMMAND_DANCE_2: 'dance2_wave.mp4',
}


class CheerCommandNode(Node):
    """ROS 2 side of the touchscreen UI.

    The Pi only publishes high-level commands. The main G1 computer remains
    responsible for translating those commands into robot behavior.
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
        self.preview_ready = False
        self.walk_mode = False

        self.hold_elapsed = QElapsedTimer()
        self.hold_triggered = False

        self.setWindowTitle('G1 Cheer Control')
        self.setMinimumSize(1000, 650)
        self.resize(1200, 760)

        root = QWidget()
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(18, 14, 18, 18)
        main_layout.setSpacing(10)

        title = QLabel('G1 CHEER CONTROL')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            'font-size: 30px; font-weight: 800; padding: 2px;'
        )
        main_layout.addWidget(title)

        self.connection_label = QLabel('WAITING FOR COMPUTER')
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet(
            'font-size: 16px; font-weight: 600; padding: 4px;'
        )
        main_layout.addWidget(self.connection_label)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        # ---------------- LEFT CONTROL COLUMN ----------------
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        self.start_button = QPushButton(
            'HOLD 5 SEC\nTO START'
        )
        self.start_button.setMinimumSize(220, 110)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet(
            'font-size: 23px; font-weight: 800; '
            'background-color: #2e7d32; color: white; '
            'border-radius: 10px;'
        )
        self.start_button.pressed.connect(self.begin_start_hold)
        self.start_button.released.connect(self.end_start_hold)
        left_panel.addWidget(self.start_button)

        dance_label = QLabel('DANCE ROUTINES')
        dance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dance_label.setStyleSheet(
            'font-size: 16px; font-weight: 700; padding-top: 6px;'
        )
        left_panel.addWidget(dance_label)

        self.dance_group = QButtonGroup(self)
        self.dance_group.setExclusive(True)
        self.dance_buttons = []

        dance_buttons = [
            ('DANCE 1\nWINGS UP', COMMAND_DANCE_1),
            ('DANCE 2\nWAVE', COMMAND_DANCE_2),
            ('DANCE 3', COMMAND_DANCE_3),
            ('DANCE 4', COMMAND_DANCE_4),
        ]

        for text, command_id in dance_buttons:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setMinimumSize(220, 72)
            button.setStyleSheet(
                'font-size: 19px; font-weight: 650; padding: 6px;'
            )
            button.clicked.connect(
                lambda checked=False, c=command_id: self.select_dance(c)
            )
            self.dance_group.addButton(button, command_id)
            self.dance_buttons.append(button)
            left_panel.addWidget(button)

        left_panel.addStretch(1)

        # ---------------- CENTER PREVIEW COLUMN ----------------
        center_panel = QVBoxLayout()
        center_panel.setSpacing(10)

        self.selection_label = QLabel('SELECT A DANCE TO PREVIEW')
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_label.setWordWrap(True)
        self.selection_label.setStyleSheet(
            'font-size: 18px; font-weight: 700; padding: 6px;'
        )
        center_panel.addWidget(self.selection_label)

        self.preview_label = QLabel('Preview will appear here')
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            'font-size: 20px; background-color: #111111; color: white;'
        )

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet('background-color: #111111;')

        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumSize(500, 430)
        self.preview_stack.setStyleSheet(
            'border: 2px solid #808080; '
            'border-radius: 10px; '
            'background-color: #111111;'
        )
        self.preview_stack.addWidget(self.preview_label)
        self.preview_stack.addWidget(self.video_widget)
        self.preview_stack.setCurrentWidget(self.preview_label)

        self.video_player = QMediaPlayer(self)
        self.video_player.setVideoOutput(self.video_widget)
        self.video_player.mediaStatusChanged.connect(
            self._preview_media_status_changed
        )
        self.video_player.errorOccurred.connect(self._preview_error)

        center_panel.addWidget(
            self.preview_stack,
            1,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.action_label = QLabel(
            'Select a routine, review the preview, then hold START.'
        )
        self.action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action_label.setWordWrap(True)
        self.action_label.setStyleSheet(
            'font-size: 15px; padding: 4px;'
        )
        center_panel.addWidget(self.action_label)

        # ---------------- RIGHT CONTROL COLUMN ----------------
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        self.mode_button = QPushButton('MODE: DANCE')
        self.mode_button.setCheckable(True)
        self.mode_button.setMinimumSize(220, 76)
        self.mode_button.setStyleSheet(
            'font-size: 21px; font-weight: 800; '
            'border: 2px solid #555; border-radius: 9px;'
        )
        self.mode_button.toggled.connect(self.set_walk_mode)
        right_panel.addWidget(self.mode_button)

        walk_label = QLabel('ONE-STEP WALK CONTROL')
        walk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        walk_label.setStyleSheet(
            'font-size: 15px; font-weight: 700; padding-top: 10px;'
        )
        right_panel.addWidget(walk_label)

        walk_grid = QGridLayout()
        walk_grid.setHorizontalSpacing(8)
        walk_grid.setVerticalSpacing(8)

        self.walk_forward = self.make_walk_button(
            '▲\nFORWARD', COMMAND_STEP_FORWARD
        )
        self.walk_left = self.make_walk_button(
            '◀\nLEFT', COMMAND_STEP_LEFT
        )
        self.walk_right = self.make_walk_button(
            '▶\nRIGHT', COMMAND_STEP_RIGHT
        )
        self.walk_backward = self.make_walk_button(
            '▼\nBACK', COMMAND_STEP_BACKWARD
        )

        walk_grid.addWidget(self.walk_forward, 0, 1)
        walk_grid.addWidget(self.walk_left, 1, 0)
        walk_grid.addWidget(self.walk_right, 1, 2)
        walk_grid.addWidget(self.walk_backward, 2, 1)
        right_panel.addLayout(walk_grid)

        right_panel.addStretch(1)

        stop_label = QLabel('SOFTWARE MOTION STOP')
        stop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stop_label.setStyleSheet(
            'font-size: 14px; font-weight: 700;'
        )
        right_panel.addWidget(stop_label)

        self.stop_button = QPushButton('STOP MOTION')
        self.stop_button.setMinimumSize(220, 105)
        self.stop_button.setStyleSheet(
            'font-size: 25px; font-weight: 900; '
            'background-color: #c62828; color: white; '
            'border: 3px solid #8e0000; border-radius: 10px;'
        )
        self.stop_button.clicked.connect(self.stop_routine)
        right_panel.addWidget(self.stop_button)

        content_layout.addLayout(left_panel, 0)
        content_layout.addLayout(center_panel, 1)
        content_layout.addLayout(right_panel, 0)

        main_layout.addLayout(content_layout, 1)
        self.setCentralWidget(root)

        # Countdown for the 5-second hold-to-start action.
        self.hold_timer = QTimer(self)
        self.hold_timer.setInterval(100)
        self.hold_timer.timeout.connect(self.update_start_hold)

        # Refresh status coming back from the main computer.
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(200)

        self.update_mode_controls()

    def make_walk_button(self, text: str, command_id: int) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumSize(68, 68)
        button.setStyleSheet(
            'font-size: 15px; font-weight: 750; padding: 4px;'
        )
        button.clicked.connect(
            lambda checked=False, c=command_id: self.send_walk_step(c)
        )
        return button

    def select_dance(self, command_id: int):
        """Select and preview a routine without moving the robot."""
        if self.walk_mode:
            return

        # Changing the selected routine while one is active should stop motion.
        if self.hold_triggered:
            self.stop_routine()

        self.selected_dance = command_id
        name = DANCE_NAMES[command_id]

        self.preview_ready = self.show_preview(command_id)
        self.start_button.setEnabled(self.preview_ready and not self.walk_mode)

        if self.preview_ready:
            self.selection_label.setText(f'{name} SELECTED')
            self.action_label.setText(
                'Review the preview. Then press and hold the START button '
                'for 5 seconds. Keep holding while the routine runs.'
            )
        else:
            self.selection_label.setText(f'{name} SELECTED')
            self.action_label.setText(
                'This routine does not have a preview assigned yet.'
            )

        self.reset_start_button_text()

    def show_preview(self, command_id: int) -> bool:
        """Load and play the MP4 preview for the selected routine."""
        self.stop_preview()

        filename = PREVIEW_FILES.get(command_id)
        if filename is None:
            self.preview_label.setText(
                f'{DANCE_NAMES[command_id]}\nPREVIEW NOT ASSIGNED YET'
            )
            return False

        package_share = get_package_share_directory('g1_cheer_ui')
        preview_path = os.path.join(package_share, 'media', filename)

        if not os.path.isfile(preview_path):
            self.preview_label.setText(
                f'{DANCE_NAMES[command_id]}\nMP4 PREVIEW NOT FOUND'
            )
            return False

        self.preview_stack.setCurrentWidget(self.video_widget)
        self.video_player.setSource(QUrl.fromLocalFile(preview_path))
        self.video_player.setPosition(0)
        self.video_player.play()
        return True

    def stop_preview(self):
        """Stop video playback and return to the message panel."""
        self.video_player.stop()
        self.video_player.setSource(QUrl())
        self.preview_stack.setCurrentWidget(self.preview_label)

    def _preview_media_status_changed(self, status):
        """Loop the selected routine preview while it remains selected."""
        if (
            status == QMediaPlayer.MediaStatus.EndOfMedia
            and self.preview_ready
            and not self.walk_mode
        ):
            self.video_player.setPosition(0)
            self.video_player.play()

    def _preview_error(self, error, error_string):
        """Show a useful message if Qt cannot decode the MP4 preview."""
        if error == QMediaPlayer.Error.NoError:
            return

        self.video_player.stop()
        self.preview_ready = False
        self.start_button.setEnabled(False)
        self.preview_stack.setCurrentWidget(self.preview_label)
        self.preview_label.setText(
            'VIDEO PREVIEW ERROR\n'
            f'{error_string or "Check Qt multimedia / H.264 support"}'
        )

    def begin_start_hold(self):
        """Start the 5-second deliberate hold timer."""
        if (
            self.walk_mode
            or self.selected_dance is None
            or not self.preview_ready
        ):
            return

        self.hold_triggered = False
        self.hold_elapsed.start()
        self.hold_timer.start()
        self.update_start_hold()

    def update_start_hold(self):
        """Count down the 5-second hold and start the dance at zero."""
        if not self.hold_elapsed.isValid():
            return

        elapsed_ms = self.hold_elapsed.elapsed()
        remaining_ms = max(0, HOLD_TO_START_MS - elapsed_ms)

        if remaining_ms > 0:
            remaining_seconds = remaining_ms / 1000.0
            self.start_button.setText(
                f'KEEP HOLDING\n{remaining_seconds:.1f} SEC'
            )
            self.action_label.setText(
                'Keep holding START. Releasing before 5 seconds cancels.'
            )
            return

        if not self.hold_triggered:
            self.hold_triggered = True
            self.hold_timer.stop()

            self.ros_node.queue_command(self.selected_dance)
            self.start_button.setText(
                'DANCE ACTIVE\nKEEP HOLDING'
            )
            self.selection_label.setText(
                f'{DANCE_NAMES[self.selected_dance]} RUNNING'
            )
            self.action_label.setText(
                'Keep holding START to continue. '
                'Release START to stop the routine immediately.'
            )

    def end_start_hold(self):
        """Releasing START cancels the hold or stops an active dance."""
        self.hold_timer.stop()

        if self.hold_triggered:
            self.ros_node.queue_command(COMMAND_STOP)
            self.selection_label.setText('STOPPED - START RELEASED')
            self.action_label.setText(
                'Routine stopped. Hold START for 5 seconds to run it again.'
            )
        elif (
            not self.walk_mode
            and self.selected_dance is not None
            and self.preview_ready
        ):
            self.selection_label.setText(
                f'{DANCE_NAMES[self.selected_dance]} SELECTED'
            )
            self.action_label.setText(
                'Start cancelled. Hold START continuously for 5 seconds.'
            )

        self.hold_triggered = False
        self.hold_elapsed.invalidate()
        self.reset_start_button_text()

    def reset_start_button_text(self):
        if self.walk_mode:
            self.start_button.setText('START DISABLED\nWALK MODE')
        elif self.selected_dance is None:
            self.start_button.setText('HOLD 5 SEC\nTO START')
        else:
            self.start_button.setText(
                f'HOLD 5 SEC\n{DANCE_NAMES[self.selected_dance]}'
            )

    def set_walk_mode(self, enabled: bool):
        """Toggle between dance selection and one-step walking controls."""
        if self.hold_triggered or self.hold_timer.isActive():
            self.stop_routine()

        self.walk_mode = enabled
        self.mode_button.setText(
            'MODE: WALK' if enabled else 'MODE: DANCE'
        )

        if enabled:
            self.stop_preview()
            self.selection_label.setText('WALK MODE')
            self.preview_label.setText(
                'WALK MODE\n\nUse the directional controls on the right.\n'
                'Each press sends one step command.'
            )
            self.action_label.setText(
                'Dance controls are disabled while Walk Mode is active.'
            )
        else:
            if self.selected_dance is not None:
                self.preview_ready = self.show_preview(self.selected_dance)
                self.selection_label.setText(
                    f'{DANCE_NAMES[self.selected_dance]} SELECTED'
                )
                self.action_label.setText(
                    'Review the preview, then hold START for 5 seconds.'
                )
            else:
                self.preview_ready = False
                self.preview_label.setText('Preview will appear here')
                self.selection_label.setText('SELECT A DANCE TO PREVIEW')
                self.action_label.setText(
                    'Select a routine, review the preview, then hold START.'
                )

        self.update_mode_controls()
        self.reset_start_button_text()

    def update_mode_controls(self):
        for button in self.dance_buttons:
            button.setEnabled(not self.walk_mode)

        walk_enabled = self.walk_mode
        self.walk_forward.setEnabled(walk_enabled)
        self.walk_backward.setEnabled(walk_enabled)
        self.walk_left.setEnabled(walk_enabled)
        self.walk_right.setEnabled(walk_enabled)

        self.start_button.setEnabled(
            (not self.walk_mode) and self.preview_ready
        )

    def send_walk_step(self, command_id: int):
        if not self.walk_mode:
            return

        names = {
            COMMAND_STEP_FORWARD: 'STEP FORWARD',
            COMMAND_STEP_BACKWARD: 'STEP BACKWARD',
            COMMAND_STEP_LEFT: 'STEP LEFT',
            COMMAND_STEP_RIGHT: 'STEP RIGHT',
        }

        self.ros_node.queue_command(command_id)
        self.selection_label.setText(names[command_id])
        self.action_label.setText(
            'One-step command sent to the main computer.'
        )

    def stop_routine(self):
        """Immediate software motion-stop request."""
        self.hold_timer.stop()
        self.hold_triggered = False
        self.hold_elapsed.invalidate()

        self.ros_node.queue_command(COMMAND_STOP)
        self.selection_label.setText('STOP MOTION REQUESTED')
        self.action_label.setText(
            'Software stop command sent to the main computer.'
        )
        self.reset_start_button_text()

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
