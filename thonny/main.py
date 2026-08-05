# main.py
# PC에서 보낸 JSON 명령을 ESP32가 받아 로봇팔을 제어하는 프로그램

# ESP32의 I2C 통신과 GPIO 핀을 사용하기 위한 모듈
from machine import I2C, Pin

# 서보모터를 천천히 움직일 때 사용할 지연 함수
from utime import sleep_ms

# USB 시리얼 통신 입력을 받기 위한 모듈
import sys
import uselect

# PC에서 전달받은 JSON 데이터를 처리하기 위한 모듈
import ujson as json

# 로봇팔 설정값과 역기구학 계산 코드
import config
import ik

# 여러 개의 서보모터를 제어하는 PCA9685 드라이버
from pca9685 import PCA9685


# ── PCA9685 및 서보모터 초기 설정 ────────────────────────

# ESP32와 PCA9685를 I2C 방식으로 연결한다.
# SCL과 SDA 핀 번호는 config.py에 설정되어 있다.
i2c = I2C(
    0,
    scl=Pin(config.I2C_SCL),
    sda=Pin(config.I2C_SDA),
    freq=400_000
)

# 설정된 I2C 주소로 PCA9685 제어 객체를 만든다.
pca = PCA9685(i2c, config.PCA_ADDR)

# 서보 이름을 이용해 config.SERVO 목록의 위치를 찾을 수 있게 만든다.
# 예: {"base": 0, "shoulder": 1, "elbow": 2, ...}
name_to_idx = {
    servo["name"]: index
    for index, servo in enumerate(config.SERVO)
}

# 각 관절의 현재 각도를 저장한다.
# 프로그램 시작 시에는 모든 관절이 0도라고 가정한다.
current = {
    servo["name"]: 0.0
    for servo in config.SERVO
}

# 로봇팔의 기본 자세를 정의한다.
# home 명령을 받으면 모든 관절을 이 각도로 움직인다.
HOME_POSE = {
    "base": 0,
    "shoulder": 0,
    "elbow": 0,
    "wrist_r": 0,
    "wrist_p": 0,
    "grip": 0,
}


def clamp(value, low, high):
    """
    값이 지정된 최소값과 최대값을 벗어나지 않게 제한한다.

    예:
    clamp(200, 0, 180) -> 180
    clamp(-20, 0, 180) -> 0
    """
    return max(low, min(high, value))


def write_servo(name, deg):
    """
    지정한 이름의 서보모터를 원하는 각도로 움직인다.

    name: 서보모터 이름
    deg: 로봇 관절 기준 목표 각도
    """

    # 서보 이름에 해당하는 설정값을 가져온다.
    idx = name_to_idx[name]
    servo = config.SERVO[idx]

    # 로봇 관절 기준 각도를 실제 서보모터의 절대 각도로 변환한다.
    #
    # 90       : 서보모터의 가운데 위치
    # dir      : 모터의 회전 방향(1 또는 -1)
    # offset   : 조립 오차를 보정하기 위한 값
    abs_deg = 90 + servo["dir"] * deg + servo["offset"]

    # 서보모터의 안전한 회전 범위를 벗어나지 않도록 제한한다.
    abs_deg = clamp(
        abs_deg,
        servo["min_deg"],
        servo["max_deg"]
    )

    # 각도를 PCA9685가 사용할 PWM 펄스 길이로 변환한다.
    # 0~180도의 각도 범위를 min_us~max_us 범위에 대응시킨다.
    pulse_us = int(
        servo["min_us"]
        - (servo["max_us"] - servo["min_us"]) * abs_deg / 180
    )

    # 계산한 PWM 신호를 해당 PCA9685 채널로 출력한다.
    pca.set_us(config.SERVO_CH[idx], pulse_us)

    # 움직인 후 현재 각도를 기록한다.
    current[name] = deg


def move_smooth(target, delay_ms=25):
    """
    서보모터가 목표 각도까지 한 번에 움직이지 않고
    여러 단계로 나누어 부드럽게 움직이게 한다.

    target 예:
    {"base": 30, "shoulder": 20}
    """

    # 움직이기 전 각 관절의 현재 각도를 저장한다.
    starts = {
        name: current.get(name, 0.0)
        for name in target
    }

    # 각 관절이 이동해야 하는 각도 차이를 계산한다.
    diffs = {
        name: target[name] - starts[name]
        for name in target
    }

    # 가장 많이 움직여야 하는 관절을 기준으로 이동 단계 수를 정한다.
    # 적어도 한 단계는 실행되도록 한다.
    steps = max(
        max(int(abs(diff)) for diff in diffs.values()),
        1
    )

    # 현재 각도에서 목표 각도까지 조금씩 이동한다.
    for step in range(1, steps + 1):
        ratio = step / steps

        for name in target:
            # 현재 단계에서 이동해야 할 중간 각도를 계산한다.
            deg = starts[name] + diffs[name] * ratio
            write_servo(name, deg)

        # 너무 빠르게 움직이지 않도록 잠시 기다린다.
        sleep_ms(delay_ms)


def go_home():
    """
    로봇팔을 HOME_POSE에 정의된 기본 자세로 이동시킨다.
    """

    move_smooth(HOME_POSE)

    # PC에 작업 완료 결과를 JSON으로 전달하기 위한 데이터
    return {
        "ok": True,
        "message": "home complete"
    }


def go_to(x, y, z, grip=None):
    """
    로봇팔 끝부분을 지정한 3차원 좌표로 이동시킨다.

    x, y, z: 목표 위치
    grip: 그리퍼 각도(생략 가능)
    """

    # 역기구학(Inverse Kinematics)을 사용해
    # 목표 좌표에 도달하기 위한 관절 각도를 계산한다.
    result = ik.ik(x, y, z, elbow_up=True)

    # 계산 결과가 없으면 로봇팔이 도달할 수 없는 위치라는 뜻이다.
    if result is None:
        return {
            "ok": False,
            "error": "target is unreachable"
        }

    # 역기구학으로 계산한 관절 각도를 분리한다.
    base, shoulder, elbow = result

    # 각 서보모터가 이동할 목표 각도를 만든다.
    target = {
        "base": base,
        "shoulder": shoulder,
        "elbow": elbow,
        "wrist_r": 0,
        "wrist_p": 0,
    }

    # grip 값이 전달된 경우 그리퍼도 함께 움직인다.
    if grip is not None:
        target["grip"] = grip

    # 계산된 목표 각도까지 부드럽게 이동한다.
    move_smooth(target)

    return {
        "ok": True,
        "message": "move complete",
        "x": x,
        "y": y,
        "z": z,
    }


def handle_command(command):
    """
    PC에서 받은 JSON 명령의 cmd 값을 확인하고
    그에 맞는 기능을 실행한다.
    """

    # JSON에서 명령 종류를 가져온다.
    cmd = command.get("cmd")

    # ESP32가 정상적으로 연결되어 있는지 확인하는 명령
    if cmd == "ping":
        return {
            "ok": True,
            "message": "ESP32 ready"
        }

    # 로봇팔을 기본 자세로 이동시키는 명령
    if cmd == "home":
        return go_home()

    # 로봇팔을 지정한 좌표로 이동시키는 명령
    #
    # 입력 예:
    # {"cmd": "move_to", "x": 100, "y": 20, "z": 80}
    if cmd == "move_to":
        return go_to(
            float(command["x"]),
            float(command["y"]),
            float(command["z"]),
            command.get("grip")
        )

    # 그리퍼만 별도로 움직이는 명령
    #
    # 입력 예:
    # {"cmd": "grip", "angle": 30}
    if cmd == "grip":
        angle = float(command.get("angle", 0))
        move_smooth({"grip": angle})

        return {
            "ok": True,
            "message": "grip complete"
        }

    # 지원하지 않는 명령이 들어온 경우
    return {
        "ok": False,
        "error": "unknown command"
    }


# ── USB 시리얼 JSON 명령 수신 반복문 ─────────────────────

# USB 시리얼 입력이 들어왔는지 감시할 poll 객체를 만든다.
poller = uselect.poll()
poller.register(sys.stdin, uselect.POLLIN)

# ESP32 프로그램이 준비되었음을 PC에 알린다.
print(json.dumps({
    "ok": True,
    "message": "ESP32 command server ready"
}))

# ESP32가 실행되는 동안 계속해서 PC의 명령을 기다린다.
while True:

    # 최대 100ms 동안 USB 시리얼 입력을 기다린다.
    events = poller.poll(100)

    # 입력된 데이터가 없으면 처음으로 돌아가 다시 기다린다.
    if not events:
        continue

    # PC가 보낸 한 줄을 읽는다.
    line = sys.stdin.readline().strip()

    # 빈 줄이면 처리하지 않는다.
    if not line:
        continue

    try:
        # JSON 문자열을 파이썬 딕셔너리로 변환한다.
        command = json.loads(line)

        # 명령을 실행하고 결과를 받는다.
        response = handle_command(command)

    except Exception as error:
        # 잘못된 JSON이나 실행 오류가 발생하면 오류 내용을 반환한다.
        response = {
            "ok": False,
            "error": str(error)
        }

    # 실행 결과를 JSON 문자열로 바꾸어 PC로 전송한다.
    print(json.dumps(response))
