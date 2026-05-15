import json
import random
from datetime import datetime
from flask import Flask, Response

app = Flask(__name__) 

# Joint
def random_joint():
    return {
        f"joint{i}": round(random.uniform(30, 120), 2)
        for i in range(1, 8)
    }

def random_tool():
    return {
        "x": round(random.uniform(-1, 1), 3),
        "y": round(random.uniform(-1, 1), 3),
        "z": round(random.uniform(0, 1), 3),
        "w": round(random.uniform(0, 1), 3)
    }

# Hand Gripper
def random_gripper():
    return {
        "status": random.randint(0, 1),
        "index_net_force": round(random.uniform(0, 15), 2),
        "index_torque_force": round(random.uniform(0, 5), 2),
        "position": [random.randint(0, 20) for _ in range(5)],
        "current": [round(random.uniform(0, 1), 2) for _ in range(5)]
    }

 
# Load the JSON data 
with open('RobotArmData.json', 'r') as file:
    dataRobotArm = json.load(file)

with open('HandData.json', 'r') as file:
    dataHand = json.load(file)
 

# Robot arm endpoint
@app.route('/dataRobotArm', methods=['GET'])
def get_data_RobotArm():
    record = random.choice(dataRobotArm)

    formatted = {
        "device_type": "robot_arm",
        "device_id": record.get("robot_id", "UNKNOWN"),
        "timestamp": datetime.utcnow().isoformat() + "Z",

        "data": {
            "left": {
                "joint": random_joint(),
                "tool_link": random_tool()
            },
            "right": {
                "joint": random_joint(),
                "tool_link": random_tool()
            }
        }
    }

    return Response(json.dumps(formatted), mimetype='application/json')
    
# Hand Gripper Endpoint
@app.route('/dataHandGripper', methods=['GET'])
def get_data_hand():
    record = random.choice(dataHand)

    formatted = {
        "device_type": "hand_gripper",
        "device_id": record.get("robot_id"),
        "timestamp": datetime.utcnow().isoformat() + "Z",

        "data": {
            "left": random_gripper(),
            "right": random_gripper()
        }
    }

    return Response(json.dumps(formatted), mimetype='application/json')





# Run the Flask app and the update function in parallel 
if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=5000, threaded=True)