# ESP32 MicroPython용 main.py
# PCA9685 + USB 시리얼 로봇팔 제어

from machine import Pin, SoftI2C
import time
import sys

try:
    import select
except ImportError:
    import uselect as select


# =====================================================
# PCA9685 설정
# =====================================================

SDA_PIN = 21
SCL_PIN = 22
PCA9685_ADDRESS = 0x40
SERVO_FREQUENCY = 50

# 노트북의 각도 순서
# 0: 베이스
# 1: 어깨
# 2: 팔꿈치
# 3: 손목 좌우 회전
# 4: 손목 상하
# 5: 그리퍼
SERVO_CHANNELS = [0, 1, 2, 3, 4, 5]

# 서보 보호를 위한 각도 제한
SERVO_MIN_ANGLES = [10, 10, 10, 10, 10, 10]
SERVO_MAX_ANGLES = [170, 170, 170, 170, 170, 170]

# 일반적인 서보 펄스 범위
# 서보 모델에 따라 조절이 필요할 수 있음
SERVO_MIN_PULSE_US = 600
SERVO_MAX_PULSE_US = 2400


class PCA9685:
    MODE1 = 0x00
    MODE2 = 0x01
    LED0_ON_L = 0x06
    PRESCALE = 0xFE

    def __init__(self, i2c, address=0x40, frequency=50):
        self.i2c = i2c
        self.address = address
        self.frequency = frequency

        self._write_register(self.MODE1, 0x00)
        self._write_register(self.MODE2, 0x04)

        time.sleep_ms(10)
        self.set_frequency(frequency)

    def _write_register(self, register, value):
        self.i2c.writeto_mem(
            self.address,
            register,
            bytes([value & 0xFF])
        )

    def _read_register(self, register):
        data = self.i2c.readfrom_mem(
            self.address,
            register,
            1
        )
        return data[0]

    def set_frequency(self, frequency):
        prescale_value = (
            25000000.0 / (4096.0 * frequency)
        ) - 1.0

        prescale = int(prescale_value + 0.5)

        old_mode = self._read_register(self.MODE1)
        sleep_mode = (old_mode & 0x7F) | 0x10

        self._write_register(self.MODE1, sleep_mode)
        self._write_register(self.PRESCALE, prescale)
        self._write_register(self.MODE1, old_mode)

        time.sleep_ms(5)

        # Restart + Auto Increment + All Call
        self._write_register(self.MODE1, old_mode | 0xA1)

    def set_pwm(self, channel, on_count, off_count):
        register = self.LED0_ON_L + (4 * channel)

        data = bytearray(4)
        data[0] = on_count & 0xFF
        data[1] = (on_count >> 8) & 0x0F
        data[2] = off_count & 0xFF
        data[3] = (off_count >> 8) & 0x0F

        self.i2c.writeto_mem(
            self.address,
            register,
            data
        )

    def set_servo_angle(
        self,
        channel,
        angle,
        minimum_angle=10,
        maximum_angle=170
    ):
        # 서보의 안전 각도 범위로 제한
        if angle < minimum_angle:
            angle = minimum_angle

        if angle > maximum_angle:
            angle = maximum_angle

        pulse_us = (
            SERVO_MIN_PULSE_US
            + (angle / 180.0)
            * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)
        )

        period_us = 1000000.0 / self.frequency
        off_count = int((pulse_us / period_us) * 4096)

        if off_count < 0:
            off_count = 0

        if off_count > 4095:
            off_count = 4095

        self.set_pwm(channel, 0, off_count)


def parse_command(line):
    """
    A:90,90,90,90,90,90 형식의 명령을 읽습니다.
    """

    line = line.strip()

    if not line.startswith("A:"):
        return None

    values = line[2:].split(",")

    if len(values) != 6:
        return None

    try:
        return [int(value) for value in values]
    except ValueError:
        return None


def move_robot(angles):
    for index in range(6):
        channel = SERVO_CHANNELS[index]

        pca.set_servo_angle(
            channel,
            angles[index],
            SERVO_MIN_ANGLES[index],
            SERVO_MAX_ANGLES[index]
        )


# =====================================================
# I2C 및 PCA9685 시작
# =====================================================

i2c = SoftI2C(
    sda=Pin(SDA_PIN),
    scl=Pin(SCL_PIN),
    freq=400000
)

found_devices = i2c.scan()

print("I2C devices:", [
    hex(address) for address in found_devices
])

if PCA9685_ADDRESS not in found_devices:
    print("ERROR: PCA9685 0x40 not found")
    print("Check SDA=21, SCL=22, VCC and GND")

    while True:
        time.sleep(1)


pca = PCA9685(
    i2c,
    address=PCA9685_ADDRESS,
    frequency=SERVO_FREQUENCY
)

print("PCA9685 connected")


# 시작할 때 로봇팔을 중앙 각도로 이동
# 갑자기 움직일 수 있으므로 주의
center_angles = [90, 90, 90, 90, 90, 90]

for servo_index in range(6):
    pca.set_servo_angle(
        SERVO_CHANNELS[servo_index],
        center_angles[servo_index],
        SERVO_MIN_ANGLES[servo_index],
        SERVO_MAX_ANGLES[servo_index]
    )

    # 한꺼번에 움직일 때 발생하는 전류를 조금 줄임
    time.sleep_ms(100)


# =====================================================
# USB 시리얼 명령 수신
# =====================================================

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

print("READY: waiting for A:angle1,...,angle6")


while True:
    try:
        events = poller.poll(50)

        if events:
            line = sys.stdin.readline()
            angles = parse_command(line)

            if angles is not None:
                move_robot(angles)

    except KeyboardInterrupt:
        print("Robot control stopped")
        break

    except Exception as error:
        print("ERROR:", error)
        time.sleep_ms(100)
