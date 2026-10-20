# G1 Cheer UI - Wings Up + Wave Preview Build

This is a clean ROS 2 workspace. The `g1_cheer_ui` package is directly under `src/` so `colcon` can discover it.

## Assigned previews

- **Dance 1 / Wings Up** -> command `1`
- **Dance 2 / Wave** -> command `2`
- Dance 3 and Dance 4 remain unassigned.
- **STOP ROUTINE** -> command `0` immediately.

The GUI includes lightweight GIF previews extracted from the team's presentation. The original source videos remain in the project presentation; the repository stores only the preview assets needed by the GUI.

## GUI flow

1. Press **Dance 1 / Wings Up** or **Dance 2 / Wave**.
2. The routine preview plays in the center of the screen.
3. Selecting the routine does **not** publish a ROS command.
4. Press the START button to publish command `1` or `2`.
5. STOP ROUTINE immediately publishes command `0`.

## Build

```bash
cd ~/g1_cheer_ws
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install python3-pyqt6
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

Confirm ROS sees it:

```bash
ros2 pkg list | grep g1_cheer_ui
```

## Local laptop test

Terminal 1:

```bash
source /opt/ros/jazzy/setup.bash
source ~/g1_cheer_ws/install/setup.bash
ros2 run g1_cheer_ui cheer_receiver
```

Terminal 2:

```bash
source /opt/ros/jazzy/setup.bash
source ~/g1_cheer_ws/install/setup.bash
ros2 run g1_cheer_ui cheer_gui
```

## Command IDs

```text
0 = Stop routine
1 = Dance 1 / Wings Up
2 = Dance 2 / Wave
3 = Dance 3
4 = Dance 4
```
