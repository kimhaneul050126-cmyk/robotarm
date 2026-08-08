# serial_comm.py
# PC -> ESP32 JSON serial communication

import json
import time
import serial


class ArmSerial:
    def __init__(self, port, baudrate=115200):
        self.ser = None

        try:
            print(f"Connecting to ESP32: {port}")

            self.ser = serial.Serial(
                port,
                baudrate,
                timeout=0.2,
                write_timeout=3
            )

            # COM 포트를 여는 순간 ESP32가 재부팅될 수 있음
            time.sleep(3)
            self.ser.reset_input_buffer()

            response = self.ping()

            if response.get("ok"):
                print("ESP32 connected")
            else:
                print("ESP32 connection failed:", response)

        except Exception as error:
            print("Serial open error:", error)

    def send(self, command, response_timeout=20):
        if self.ser is None or not self.ser.is_open:
            return {"ok": False, "error": "Serial port is not open"}

        try:
            self.ser.reset_input_buffer()

            text = json.dumps(command) + "\n"
            self.ser.write(text.encode("utf-8"))
            self.ser.flush()

            print("Sent:", text.strip())

            deadline = time.time() + response_timeout

            while time.time() < deadline:
                raw = self.ser.readline().decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if not raw:
                    continue

                try:
                    response = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # 명령 echo는 무시하고 ok가 있는 실제 응답만 받음
                if "ok" in response:
                    print("ESP32 response:", response)
                    return response

            return {"ok": False, "error": "No response from ESP32"}

        except Exception as error:
            print("Serial error:", error)
            return {"ok": False, "error": str(error)}

    def ping(self):
        return self.send({"cmd": "ping"}, response_timeout=8)

    def home(self):
        print("Moving home")
        return self.send({"cmd": "home"}, response_timeout=20)

    def move_to(self, x, y, z, grip=None):
        command = {
            "cmd": "move_to",
            "x": float(x),
            "y": float(y),
            "z": float(z)
        }

        if grip is not None:
            command["grip"] = float(grip)

        print(f"Move: ({x:.1f}, {y:.1f}, {z:.1f})")
        return self.send(command, response_timeout=20)

    def grip_open(self):
        return self.send({"cmd": "grip", "angle": -50})

    def grip_close(self):
        return self.send({"cmd": "grip", "angle": 50})

    def test_servo(self, name, angle):
        """0=중립 기준의 상대각도로 관절 하나 직접 테스트"""
        return self.send({
            "cmd": "servo",
            "name": name,
            "angle": float(angle)
        })

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
            print("Serial port closed")
