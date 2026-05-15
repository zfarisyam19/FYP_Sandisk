CREATE DATABASE IF NOT EXISTS fyp_data;
USE fyp_data;

-- 1. ROBOT ARM JOINT DATA
CREATE TABLE IF NOT EXISTS robot_arm_joint (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    robot_id VARCHAR(50) NOT NULL,
    arm_side ENUM('left','right') NOT NULL,

    joint1 DECIMAL(8,2),
    joint2 DECIMAL(8,2),
    joint3 DECIMAL(8,2),
    joint4 DECIMAL(8,2),
    joint5 DECIMAL(8,2),
    joint6 DECIMAL(8,2),
    joint7 DECIMAL(8,2),

    timestamp DATETIME NOT NULL,

    INDEX idx_joint_robot (robot_id),
    INDEX idx_joint_time (timestamp),
    INDEX idx_joint_robot_time (robot_id, timestamp)
);

-- 2. ROBOT ARM TOOL LINK POSITION
CREATE TABLE IF NOT EXISTS robot_arm_tool (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    robot_id VARCHAR(50) NOT NULL,
    arm_side ENUM('left','right') NOT NULL,

    x DECIMAL(10,3),
    y DECIMAL(10,3),
    z DECIMAL(10,3),
    w DECIMAL(10,3),

    timestamp DATETIME NOT NULL,

    INDEX idx_tool_robot (robot_id),
    INDEX idx_tool_time (timestamp),
    INDEX idx_tool_robot_time (robot_id, timestamp)
);

-- 3. HAND GRIPPER DATA
CREATE TABLE IF NOT EXISTS hand_gripper (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    robot_id VARCHAR(50) NOT NULL,
    gripper_side ENUM('left','right') NOT NULL,

    status TINYINT,
    index_net_force DECIMAL(8,2),
    index_torque_force DECIMAL(8,2),

    pos1 DECIMAL(8,2),
    pos2 DECIMAL(8,2),
    pos3 DECIMAL(8,2),
    pos4 DECIMAL(8,2),
    pos5 DECIMAL(8,2),

    cur1 DECIMAL(8,2),
    cur2 DECIMAL(8,2),
    cur3 DECIMAL(8,2),
    cur4 DECIMAL(8,2),
    cur5 DECIMAL(8,2),

    timestamp DATETIME NOT NULL,

    INDEX idx_hand_robot (robot_id),
    INDEX idx_hand_time (timestamp),
    INDEX idx_hand_robot_time (robot_id, timestamp)
);

-- 4. HOLOLENS BATTERY SUMMARY

CREATE TABLE IF NOT EXISTS hololens_battery (
 id INT AUTO_INCREMENT PRIMARY KEY,
 device_id VARCHAR(50) UNIQUE,
 state_of_charge FLOAT,
 charging INT,
 ac_online INT,
 updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
 ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hololens_battery_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50),
    state_of_charge FLOAT,
    charging INT,
    ac_online INT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_device (device_id),
    INDEX idx_time (updated_at)
);