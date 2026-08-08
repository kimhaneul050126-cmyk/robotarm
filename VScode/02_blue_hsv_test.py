import cv2
import numpy as np

# 휴대폰 IP Camera Lite 주소
URL = "http://172.20.10.1:8081/video"

# 클릭 테스트로 찾은 파란색 HSV 범위
lower = np.array([90, 60, 70])
upper = np.array([125, 255, 255])

cap = cv2.VideoCapture(URL)

if not cap.isOpened():
    raise RuntimeError("카메라 스트림을 열 수 없습니다.")

print("Blue object detection test")
print("Click blue object to adjust HSV range")
print("Press q to quit")

frame_data = {"frame": None}


def on_mouse(event, x, y, flags, param):
    global lower, upper

    if event == cv2.EVENT_LBUTTONDOWN:
        frame = param["frame"]

        if frame is None:
            return

        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = hsv_frame[y, x]

        # 클릭 위치 기준으로 HSV 범위 자동 조정
        lower = np.array([
            max(0, h - 15),
            max(0, s - 50),
            max(0, v - 50)
        ])

        upper = np.array([
            min(179, h + 15),
            255,
            255
        ])

        print(f"Clicked HSV: H={h}, S={s}, V={v}")
        print(f"LOWER = {lower}")
        print(f"UPPER = {upper}")


# 창 크기를 조절 가능하게 만들기
cv2.namedWindow("Blue Detection", cv2.WINDOW_NORMAL)
cv2.namedWindow("Mask - White is Blue", cv2.WINDOW_NORMAL)
cv2.namedWindow("Blue Only", cv2.WINDOW_NORMAL)

# 각 창 표시 크기
cv2.resizeWindow("Blue Detection", 640, 480)
cv2.resizeWindow("Mask - White is Blue", 400, 300)
cv2.resizeWindow("Blue Only", 400, 300)

#cv2.setMouseCallback("Blue Detection", on_mouse, frame_data)
while True:
    ret, frame = cap.read()
    frame = cv2.resize(frame, (640, 360))

    if not ret:
        print("Cannot read camera frame")
        break

    frame_data["frame"] = frame.copy()

    # BGR 영상 → HSV 영상
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 파란색 부분만 흰색으로 남긴 마스크
    mask = cv2.inRange(hsv, lower, upper)

    # 노이즈 제거
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 파란색 영역의 윤곽 찾기
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    detected = False

    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        # 너무 작은 영역은 무시
        if area > 500:
            M = cv2.moments(largest)

            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                # 윤곽선과 중심점 표시
                cv2.drawContours(frame, [largest], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)

                cv2.putText(
                    frame,
                    f"Object: ({cx}, {cy}) Area: {int(area)}",
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                detected = True

    # 감지 상태 표시
    if detected:
        status = "DETECTED"
        status_color = (0, 255, 0)
    else:
        status = "SHOW BLUE OBJECT"
        status_color = (0, 0, 255)

    cv2.putText(
        frame,
        status,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        status_color,
        2
    )

    cv2.putText(
        frame,
        f"Lower: {lower}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 0),
        1
    )

    cv2.putText(
        frame,
        f"Upper: {upper}",
        (10, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 0),
        1
    )

    # 파란색 부분만 남긴 결과 영상
    result = cv2.bitwise_and(frame, frame, mask=mask)

    # 창 3개 표시
    cv2.imshow("Pink Detection", frame)
    cv2.imshow("Mask - White is Pink", mask)
    cv2.imshow("Pink Only", result)

    # q를 누르면 종료
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
