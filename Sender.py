"""
Sender.py  —  Flask API serving all three device endpoints
===========================================================
/dataRobotArm   → LIVE data from ROS 2 (your part)
/dataHandGripper → placeholder random data (hand team's part, unchanged)
/dataHoloLens   → placeholder random data (hololens team's part, unchanged)

Run:
    source /opt/ros/humble/setup.bash
    source ~/ros3_ws/install/setup.bash
    python3 Sender.py
"""

import json
import math
import random
import threading
import time
from datetime import datetime
from flask import Flask, Response

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from control_msgs.msg import JointTrajectoryControllerState
from tf2_ros import Buffer, TransformListener

app = Flask(__name__)

# =============================================================================
# ✏️  YOUR CONFIGURATION — edit these
# =============================================================================

ROBOT_ID = "RB001"

JOINT_STATES_TOPIC     = "/joint_states"
LEFT_CTRL_STATE_TOPIC  = "/left_arm_controller/state"
RIGHT_CTRL_STATE_TOPIC = "/right_arm_controller/state"

# Run: ros2 run tf2_tools view_frames → open frames.pdf → find root frame
TF_BASE_FRAME       = "base_link"
TF_LEFT_TOOL_FRAME  = "left_grasp_link"
TF_RIGHT_TOOL_FRAME = "right_grasp_link"

# Only these joints are extracted — everything else in /joint_states is ignored
LEFT_JOINT_NAMES  = ["l_j1", "l_j2", "l_j3", "l_j4", "l_j5", "l_j6", "l_j7"]
RIGHT_JOINT_NAMES = ["r_j1", "r_j2", "r_j3", "r_j4", "r_j5", "r_j6", "r_j7"]

CONVERT_TO_DEGREES = True   # True = degrees, False = radians

# =============================================================================
# SHARED ARM STATE  (ROS 2 thread writes, Flask thread reads)
# =============================================================================

_lock = threading.Lock()

def _empty_joints():
    return {f"joint{i}": None for i in range(1, 8)}

# ── CHANGE 1: added qx, qy, qz to _empty_pose ────────────────────────────────
def _empty_pose():
    return {"x": None, "y": None, "z": None,
            "qx": None, "qy": None, "qz": None, "qw": None}

_left_joints  = _empty_joints()
_right_joints = _empty_joints()
_left_pose    = _empty_pose()
_right_pose   = _empty_pose()
_left_actual  = _empty_joints()
_right_actual = _empty_joints()
_ros_timestamp = None

# =============================================================================
# HELPERS
# =============================================================================

def _rad_to_val(rad):
    return round(math.degrees(rad), 4) if CONVERT_TO_DEGREES else round(rad, 6)

def _extract_arm_joints(msg: JointState, joint_names: list) -> dict:
    result = _empty_joints()
    name_to_idx = {n: i for i, n in enumerate(msg.name)}
    for slot, jname in enumerate(joint_names, start=1):
        idx = name_to_idx.get(jname)
        if idx is not None and idx < len(msg.position):
            result[f"joint{slot}"] = _rad_to_val(msg.position[idx])
    return result

def _extract_ctrl_joints(msg: JointTrajectoryControllerState,
                          joint_names: list) -> dict:
    result = _empty_joints()
    name_to_idx = {n: i for i, n in enumerate(msg.joint_names)}
    for slot, jname in enumerate(joint_names, start=1):
        idx = name_to_idx.get(jname)
        if idx is not None:
            try:
                result[f"joint{slot}"] = _rad_to_val(msg.feedback.positions[idx])
            except (IndexError, AttributeError):
                pass
    return result

# =============================================================================
# ROS 2 NODE
# =============================================================================

class ArmSenderNode(Node):

    def __init__(self):
        super().__init__("arm_sender")

        self.create_subscription(JointState, JOINT_STATES_TOPIC,
                                 self._joint_cb, 10)
        self.create_subscription(JointTrajectoryControllerState,
                                 LEFT_CTRL_STATE_TOPIC, self._left_ctrl_cb, 10)
        self.create_subscription(JointTrajectoryControllerState,
                                 RIGHT_CTRL_STATE_TOPIC, self._right_ctrl_cb, 10)

        self._tf_buf = Buffer()
        self._tf_lis = TransformListener(self._tf_buf, self)
        self.create_timer(0.1, self._tf_timer)

        self.get_logger().info(
            f"ArmSenderNode ready | base: {TF_BASE_FRAME} | "
            f"left: {TF_LEFT_TOOL_FRAME} | right: {TF_RIGHT_TOOL_FRAME}"
        )

    def _joint_cb(self, msg: JointState):
        left  = _extract_arm_joints(msg, LEFT_JOINT_NAMES)
        right = _extract_arm_joints(msg, RIGHT_JOINT_NAMES)
        sec   = msg.header.stamp.sec
        nsec  = msg.header.stamp.nanosec
        ts    = datetime.utcfromtimestamp(sec + nsec * 1e-9).isoformat() + "Z"
        with _lock:
            _left_joints.update(left)
            _right_joints.update(right)
            global _ros_timestamp
            _ros_timestamp = ts

    def _left_ctrl_cb(self, msg: JointTrajectoryControllerState):
        with _lock:
            _left_actual.update(_extract_ctrl_joints(msg, LEFT_JOINT_NAMES))

    def _right_ctrl_cb(self, msg: JointTrajectoryControllerState):
        with _lock:
            _right_actual.update(_extract_ctrl_joints(msg, RIGHT_JOINT_NAMES))

    # ── CHANGE 2: capture qx, qy, qz, qw from TF ─────────────────────────────
    def _tf_timer(self):
        for frame, pose_dict in [
            (TF_LEFT_TOOL_FRAME,  _left_pose),
            (TF_RIGHT_TOOL_FRAME, _right_pose),
        ]:
            try:
                t  = self._tf_buf.lookup_transform(
                    TF_BASE_FRAME, frame, rclpy.time.Time()
                )
                tr = t.transform.translation
                ro = t.transform.rotation
                with _lock:
                    pose_dict["x"]  = round(tr.x, 6)
                    pose_dict["y"]  = round(tr.y, 6)
                    pose_dict["z"]  = round(tr.z, 6)
                    pose_dict["qx"] = round(ro.x, 6)   # ← NEW
                    pose_dict["qy"] = round(ro.y, 6)   # ← NEW
                    pose_dict["qz"] = round(ro.z, 6)   # ← NEW
                    pose_dict["qw"] = round(ro.w, 6)
            except Exception:
                pass

def ros2_thread():
    rclpy.init()
    node     = ArmSenderNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()

# =============================================================================
# HAND GRIPPER — original random placeholder (unchanged)
# =============================================================================

def _random_gripper():
    return {
        "status"             : random.randint(0, 1),
        "index_net_force"    : round(random.uniform(0, 15), 2),
        "index_torque_force" : round(random.uniform(0, 5), 2),
        "position"           : [random.randint(0, 20) for _ in range(5)],
        "current"            : [round(random.uniform(0, 1), 2) for _ in range(5)],
    }

try:
    with open("HandData.json", "r") as f:
        _hand_data = json.load(f)
except FileNotFoundError:
    _hand_data = [{"robot_id": "RB001"}]

# =============================================================================
# FLASK ENDPOINTS
# =============================================================================

# ── Robot Arm (LIVE from ROS 2) ───────────────────────────────────────────────

@app.route("/dataRobotArm", methods=["GET"])
def get_data_robot_arm():
    with _lock:
        left_j  = dict(_left_joints)
        right_j = dict(_right_joints)
        left_p  = dict(_left_pose)
        right_p = dict(_right_pose)
        left_a  = dict(_left_actual)
        right_a = dict(_right_actual)
        ts      = _ros_timestamp or (datetime.utcnow().isoformat() + "Z")

    # ── CHANGE 3: send full quaternion qx, qy, qz, qw in tool_link ───────────
    formatted = {
        "device_type" : "robot_arm",
        "device_id"   : ROBOT_ID,
        "timestamp"   : ts,
        "data": {
            "left": {
                "joint"       : left_j,
                "joint_actual": left_a,
                "tool_link"   : {
                    "x" : left_p["x"],
                    "y" : left_p["y"],
                    "z" : left_p["z"],
                    "qx": left_p["qx"],   # ← NEW
                    "qy": left_p["qy"],   # ← NEW
                    "qz": left_p["qz"],   # ← NEW
                    "w" : left_p["qw"],   # qw → existing "w" DB column
                },
            },
            "right": {
                "joint"       : right_j,
                "joint_actual": right_a,
                "tool_link"   : {
                    "x" : right_p["x"],
                    "y" : right_p["y"],
                    "z" : right_p["z"],
                    "qx": right_p["qx"],  # ← NEW
                    "qy": right_p["qy"],  # ← NEW
                    "qz": right_p["qz"],  # ← NEW
                    "w" : right_p["qw"],
                },
            },
        }
    }
    return Response(json.dumps(formatted), mimetype="application/json")


# ── Hand Gripper (random placeholder — unchanged) ─────────────────────────────

@app.route("/dataHandGripper", methods=["GET"])
def get_data_hand():
    record = random.choice(_hand_data)
    formatted = {
        "device_type" : "hand_gripper",
        "device_id"   : record.get("robot_id", "RB001"),
        "timestamp"   : datetime.utcnow().isoformat() + "Z",
        "data": {
            "left" : _random_gripper(),
            "right": _random_gripper(),
        }
    }
    return Response(json.dumps(formatted), mimetype="application/json")


# ── HoloLens (random placeholder — unchanged) ─────────────────────────────────

@app.route("/dataHoloLens", methods=["GET"])
def get_data_hololens():
    formatted = {
        "device_type" : "hololens",
        "device_id"   : "HL001",
        "timestamp"   : datetime.utcnow().isoformat() + "Z",
        "data": {
            "StateOfCharge" : round(random.uniform(20, 100), 1),
            "Charging"      : random.randint(0, 1),
            "AcOnline"      : random.randint(0, 1),
        }
    }
    return Response(json.dumps(formatted), mimetype="application/json")


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    t = threading.Thread(target=ros2_thread, daemon=True)
    t.start()

    print("[Sender] Waiting for ROS 2 to initialise...")
    time.sleep(3)
    print(f"[Sender] Serving on port 5000")
    print(f"[Sender]   /dataRobotArm   → LIVE from ROS 2 (robot: {ROBOT_ID})")
    print(f"[Sender]   /dataHandGripper → random placeholder")
    print(f"[Sender]   /dataHoloLens    → random placeholder (stub only)")
    print(f"[Sender] TF base frame: {TF_BASE_FRAME}  ← update if wrong")

    app.run(host="0.0.0.0", port=5000, threaded=True)