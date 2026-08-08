# config_vision.py
# PC 쪽 설정값 모아두는 파일

# ── 시리얼 포트 ──────────────────────────────────────────
# Thonny 에서 확인한 포트 번호로 변경
SERIAL_PORT = 'COM3'       # Windows
SERIAL_BAUD = 115200

# SERIAL_PORT = '/dev/ttyUSB0'  # Linux
# SERIAL_PORT = '/dev/cu.usbserial-xxxx'  # Mac

# ── 카메라 ───────────────────────────────────────────────
# 휴대폰 IP 카메라 주소
# IP Webcam 앱: http://폰IP:8080/video
# DroidCam:     http://폰IP:4747/video
CAMERA_URL = 'http://172.20.10.1:8081/video'

# 웹캠 쓸 경우 (USB 웹캠)
# CAMERA_URL = 0

# ── ArUco 마커 ───────────────────────────────────────────
ARUCO_DICT    = 'DICT_4X4_50'   # 마커 종류
MARKER_CM     = 4.0              # 실제 마커 크기 (cm) - 인쇄 후 측정

# ── 물체 인식 색상 (HSV) ──────────────────────────────────
# 파란색 기준 - 실제 물체 색에 맞게 조정
COLOR_LOWER = (95, 30, 45)
COLOR_UPPER = (125, 255, 255)

# ── 로봇팔 설정 ──────────────────────────────────────────
# 마커 원점에서 로봇팔 베이스까지 거리 (cm) 마커0 기준으로 재기 
# 실제 세팅 후 측정해서 수정  (오른쪽 음수 / 뒤쪽 양수 )
BASE_OFFSET_X = 24.3 + 3 # 앞뒤 거리
BASE_OFFSET_Y = -9.9  # 좌우 거리

# 집기/놓기 높이 (cm)
PICK_Z   =  7.0    # 물체 집을 때 높이
HOVER_Z  = 22.0    # 이동할 때 높이
PLACE_Z  =  10.0    # 놓을 때 높이

# 놓을 위치 (cm) - 로봇팔 베이스 기준
PLACE_POSITION = {'x': -15.0, 'y': 15.0, 'z': PLACE_Z}
