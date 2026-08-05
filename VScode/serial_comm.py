# serial_comm.py
# PC와 ESP32가 USB 시리얼로 JSON 명령을 주고받는 코드

import json
import time
import serial


class ArmSerial:

    def __init__(self, port, baudrate=115200):
        # 지정한 포트로 ESP32와 시리얼 연결
        print(f'Connecting to ESP32: {port}')

        self.ser = serial.Serial(port, baudrate, timeout=20)

        # ESP32가 재시작되고 준비될 때까지 대기
        time.sleep(2)

        # ping 명령으로 연결 상태 확인
        resp = self.ping()

        if resp.get('ok'):
            print('ESP32 connected')
        else:
            print(f'ESP32 did not respond: {resp}')

    def send(self, cmd):
        """명령을 JSON으로 보내고 ESP32의 응답을 받는다."""

        try:
            # 이전에 남아 있던 수신 데이터 제거
            self.ser.reset_input_buffer()

            # 딕셔너리를 JSON 문자열로 변환해 전송
            message = json.dumps(cmd) + '\n'
            self.ser.write(message.encode('utf-8'))

            # ESP32가 보낸 한 줄의 응답을 읽음
            response = self.ser.readline().decode('utf-8').strip()

            if not response:
                return {
                    'ok': False,
                    'error': 'No response from ESP32'
                }

            return json.loads(response)

        except json.JSONDecodeError:
            return {
                'ok': False,
                'error': 'Invalid ESP32 response'
            }

        except Exception as e:
            print(f'Serial error: {e}')
            return {
                'ok': False,
                'error': str(e)
            }

    def ping(self):
        # ESP32가 연결되어 있는지 확인
        return self.send({'cmd': 'ping'})

    def home(self):
        # 로봇팔을 기본 자세로 이동
        print('Moving home')
        return self.send({'cmd': 'home'})

    def move_to(self, x, y, z, grip=None):
        # 로봇팔을 지정된 좌표로 이동시키는 명령
        cmd = {
            'cmd': 'move_to',
            'x': x,
            'y': y,
            'z': z
        }

        # grip 값이 있으면 그리퍼 각도도 함께 전송
        if grip is not None:
            cmd['grip'] = grip

        print(f'Move: ({x:.1f}, {y:.1f}, {z:.1f})')
        return self.send(cmd)

    def grip_open(self):
        # 그리퍼 열기
        return self.send({
            'cmd': 'grip',
            'angle': -50
        })

    def grip_close(self):
        # 그리퍼 닫기
        return self.send({
            'cmd': 'grip',
            'angle': 50
        })

    def close(self):
        # 사용이 끝난 시리얼 포트 닫기
        if self.ser and self.ser.is_open:
            self.ser.close()
            print('Serial port closed')
