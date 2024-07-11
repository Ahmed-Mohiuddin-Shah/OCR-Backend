import cv2
import numpy as np
import imutils

# Load image, grayscale, blur, Otsu's threshold
image = cv2.imread('test.png')
# image = cv2.imread('test1.jpg')

image = imutils.resize(image, width=500)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (3, 3), 0)
thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

# Find contours and filter for cards using contour area
cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]
threshold_min_area = 400
number_of_contours = 0
for c in cnts:
    area = cv2.contourArea(c)
    if area > threshold_min_area:
        cv2.drawContours(image, [c], 0, (36,255,12), 3)
        number_of_contours += 1

print("Contours detected:", number_of_contours)
cv2.imshow('thresh', thresh)
cv2.imshow('image', image)
cv2.waitKey()