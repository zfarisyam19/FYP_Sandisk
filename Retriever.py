import json
import mysql.connector
from mysql.connector import errorcode
import requests
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import concurrent.futures


# CONFIGURATION
URLS = {
    "robotarm": "http://localhost:5000/dataRobotArm",
    "hand": "http://localhost:5000/dataHandGripper",
    "hololens": "http://localhost:5001/dataHoloLens"
}

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "fyp_data"
}

last_holo_log_time = 0

# DATABASE AUTO RECOVERY
def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS robot_arm_joint (
            id INT AUTO_INCREMENT PRIMARY KEY,
            robot_id VARCHAR(50),
            arm_side ENUM('left','right'),
            joint1 FLOAT,
            joint2 FLOAT,
            joint3 FLOAT,
            joint4 FLOAT,
            joint5 FLOAT,
            joint6 FLOAT,
            joint7 FLOAT,
            timestamp DATETIME,
            INDEX idx_robot (robot_id),
            INDEX idx_time (timestamp)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS robot_arm_tool (
            id INT AUTO_INCREMENT PRIMARY KEY,
            robot_id VARCHAR(50),
            arm_side ENUM('left','right'),
            x FLOAT,
            y FLOAT,
            z FLOAT,
            w FLOAT,
            timestamp DATETIME,
            INDEX idx_robot (robot_id),
            INDEX idx_time (timestamp)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hand_gripper (
            id INT AUTO_INCREMENT PRIMARY KEY,
            robot_id VARCHAR(50),
            gripper_side ENUM('left','right'),
            status INT,
            index_net_force FLOAT,
            index_torque_force FLOAT,

            pos1 FLOAT,
            pos2 FLOAT,
            pos3 FLOAT,
            pos4 FLOAT,
            pos5 FLOAT,

            cur1 FLOAT,
            cur2 FLOAT,
            cur3 FLOAT,
            cur4 FLOAT,
            cur5 FLOAT,

            timestamp DATETIME,

            INDEX idx_robot (robot_id),
            INDEX idx_time (timestamp)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hololens_battery (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(50) UNIQUE,

            state_of_charge FLOAT,
            charging INT,
            ac_online INT,

            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hololens_battery_log (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(50),
            state_of_charge FLOAT,
            charging INT,
            ac_online INT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            INDEX idx_device (device_id),
            INDEX idx_time (updated_at)
    )
""")


def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG, autocommit=False)
        return conn

    except mysql.connector.Error as err:

        if err.errno == errorcode.ER_BAD_DB_ERROR:
            print("[RECOVERY] Database missing. Creating database...")

            temp_conn = mysql.connector.connect(
                host=DB_CONFIG["host"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"]
            )

            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
            temp_cursor.execute(f"USE {DB_CONFIG['database']}")

            create_tables(temp_cursor)

            temp_conn.commit()
            temp_cursor.close()
            temp_conn.close()

            print("[RECOVERY] Database and tables created successfully.")

            return mysql.connector.connect(**DB_CONFIG, autocommit=False)

        else:
            raise err



# FETCH API
def fetch_url(url):
    try:
        response = requests.get(url, timeout=0.5)
        return response.json()
    except:
        return None


# SQL INSERT
sql_joint = """
INSERT INTO robot_arm_joint
(robot_id, arm_side, joint1, joint2, joint3, joint4, joint5, joint6, joint7, timestamp)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

sql_tool = """
INSERT INTO robot_arm_tool
(robot_id, arm_side, x, y, z, w, timestamp)
VALUES (%s,%s,%s,%s,%s,%s,%s)
"""

sql_hand = """
INSERT INTO hand_gripper
(robot_id, gripper_side, status, index_net_force, index_torque_force,
pos1, pos2, pos3, pos4, pos5,
cur1, cur2, cur3, cur4, cur5, timestamp)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

sql_holo = """
INSERT INTO hololens_battery
(device_id, state_of_charge, charging, ac_online)
VALUES (%s,%s,%s,%s)

ON DUPLICATE KEY UPDATE
state_of_charge = VALUES(state_of_charge),
charging = VALUES(charging),
ac_online = VALUES(ac_online),
updated_at = NOW()
"""

sql_holo_log = """
INSERT INTO hololens_battery_log
(device_id, state_of_charge, charging, ac_online)
VALUES (%s,%s,%s,%s)
"""


# MAIN PROCESS
def process_and_save(conn, cursor):

    global last_holo_log_time

    start_time = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch_url, URLS.values()))

    valid_records = [r for r in results if r]

    if not valid_records:
        return
    
    batch_joints = []
    batch_tools = []
    batch_hands = []
    batch_holo = []
    batch_holo_log = []
      

    try:
        for record in valid_records:

            device_type = record.get("device_type")
            robot_id = record.get("device_id")
            data = record.get("data", {})

            ts_str = record.get("timestamp", "")

            try:
                if ts_str:
       
                   ts = datetime.fromisoformat(ts_str.replace("Z", ""))
                   ts = ts.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
                   ts = ts.replace(tzinfo=None)  # remove timezone for MySQL DATETIME
                else:
                   ts = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).replace(tzinfo=None)

            except:
                   ts = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).replace(tzinfo=None)

            
            # ROBOT ARM
            if device_type == "robot_arm":

                for side in ["left", "right"]:

                    arm = data.get(side, {})
                    joint = arm.get("joint", {})
                    tool = arm.get("tool_link", {})

                    joint_values = (
                        robot_id, side,
                        joint.get("joint1"),
                        joint.get("joint2"),
                        joint.get("joint3"),
                        joint.get("joint4"),
                        joint.get("joint5"),
                        joint.get("joint6"),
                        joint.get("joint7"),
                        ts
                    )

                    tool_values = (
                        robot_id, side,
                        tool.get("x"),
                        tool.get("y"),
                        tool.get("z"),
                        tool.get("w"),
                        ts
                    )

                    batch_joints.append(joint_values)
                    batch_tools.append(tool_values)

            
            # HAND GRIPPER
            elif device_type == "hand_gripper":

                for side in ["left", "right"]:

                    hand = data.get(side, {})

                    pos = hand.get("position", [0,0,0,0,0])
                    cur = hand.get("current", [0,0,0,0,0])

                    hand_values = (
                        robot_id, side,
                        hand.get("status"),
                        hand.get("index_net_force"),
                        hand.get("index_torque_force"),

                        pos[0], pos[1], pos[2], pos[3], pos[4],
                        cur[0], cur[1], cur[2], cur[3], cur[4],

                        ts
                    )

                    batch_hands.append(hand_values)
            
            # Hololens
            elif device_type == "hololens":

                holo_values = (
                    robot_id,
                    data.get("StateOfCharge"),
                    data.get("Charging"),
                    data.get("AcOnline")
)

                batch_holo.append(holo_values)

                now = time.time()

                if now - last_holo_log_time >= 30:
                    batch_holo_log.append(holo_values)
                    last_holo_log_time = now

                




        if batch_joints:
            cursor.executemany(sql_joint, batch_joints)

        if batch_tools:
            cursor.executemany(sql_tool, batch_tools)

        if batch_hands:
            cursor.executemany(sql_hand, batch_hands)

        if batch_holo:
            cursor.executemany(sql_holo, batch_holo)

        if batch_holo_log:
            cursor.executemany(sql_holo_log, batch_holo_log)    

        conn.commit()

    except mysql.connector.Error as e:
        print(f"[DB ERROR] {e}")
        conn.rollback()
        raise e

    latency = time.perf_counter() - start_time

    print(
        f"[{datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).strftime('%H:%M:%S')}] "
        f"Robot:{len(batch_joints)} Hand:{len(batch_hands)} Holo:{len(batch_holo)} | "
        f"Time: {latency:.4f}s"
    )



if __name__ == "__main__":

    db = None

    while True:

        try:
            if db is None or not db.is_connected():
                db = get_db_connection()
                cursor = db.cursor()
                print("=== AUTO RECOVERY DATABASE PIPELINE ACTIVE ===")

            process_and_save(db, cursor)

            time.sleep(0.3)

        except mysql.connector.Error as err:
            print(f"[SYSTEM FAILURE] {err}")
            print("[RECOVERY] Retrying in 2 seconds...")
            time.sleep(2)
            db = None

        except KeyboardInterrupt:
            print("\nShutting down...")
            if db and db.is_connected():
                db.close()
            break

        except Exception as ex:
            print(f"[UNKNOWN ERROR] {ex}")
            time.sleep(2)