import cv2

class MotionDetection:
    def __init__(self):
        self.first_frame = None

    def detect_motion(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.first_frame is None:
            self.first_frame = gray
            return False
        delta_frame = cv2.absdiff(self.first_frame, gray)
        threshold_frame = cv2.threshold(delta_frame, 50, 255, cv2.THRESH_BINARY)[1]
        threshold_frame = cv2.dilate(threshold_frame, None, iterations=2)
        (cntr, _) = cv2.findContours(
            threshold_frame.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        motion_detected = False
        for contour in cntr:
            if cv2.contourArea(contour) < 150000:  # Adjust the threshold value as per your requirement
                continue
            motion_detected = True
        return motion_detected