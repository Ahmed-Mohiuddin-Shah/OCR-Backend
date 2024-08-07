import json
import os
import re
import cv2
import numpy as np
from helpers import *
from decouple import config

def crop_frame(frame, start_x, start_y, width, height):
    """
    Crop the given frame using the specified dimensions.
    
    Args:
    - frame: The input frame.
    - start_x: The starting x-coordinate of the crop.
    - start_y: The starting y-coordinate of the crop.
    - width: The width of the crop.
    - height: The height of the crop.
    
    Returns:
    - The cropped frame.
    """
    return frame[start_y:start_y + height, start_x:start_x + width]

def get_cropped_frame(image):

    ROI = image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # cv2.imshow('gray', gray)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    # cv2.imshow('blur', blur)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    # cv2.imshow('thresh', thresh)

    # Find contours and filter for cards using contour area
    cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    threshold_min_area = 10000

    for c in cnts:
        area = cv2.contourArea(c)
        if area > threshold_min_area:
            x,y,w,h = cv2.boundingRect(c)

            # Crop ROI
            ROI = image[y:y+h, x:x+w]

    return ROI

def extract_name_and_cnic(data):

    print(data)
    
    name = None
    n_confidence = 0
    cnic = None
    c_confidence = 0
    
    # name_identifiers = ['name']
    cnic_pattern = re.compile(r'\b\d{5}-\d{7}-\d{1}\b')
    
    for i, entry in enumerate(data):
        # print(entry)
        text, confidence = entry
        # Check for name
        if text.lower() == 'name' or text.lower() == 'name:' or text.lower() == 'name;' or text.lower() == 'name,':
            # Assuming the actual name follows the identifier
            if i + 1 < len(data):
                if data[i + 1] == ':':
                    name, n_confidence = data[i + 2]
                if data[i + 1] == ';':
                    name, n_confidence = data[i + 2]
                if data[i + 1] == ',':
                    name, n_confidence = data[i + 2]
                else:
                    name, n_confidence = data[i + 1]
        
        # Check for CNIC using the pattern
        if cnic_pattern.match(text):
            cnic = text
            c_confidence = confidence
            if len(cnic) > 15:
                cnic = cnic[:15]
                c_confidence = confidence
    
    return name, n_confidence, cnic, c_confidence

def create_data_json(filename='data.json'):
    """Creates a data.json file with an empty list if it doesn't already exist."""
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump([], f)
        print(f"{filename} created.")
    else:
        print(f"{filename} already exists.")

def append_to_data_json(info, filename='data.json'):
    """Appends a stringified JSON object to the data.json file."""
    if not os.path.exists(filename):
        create_data_json(filename)

    with open(filename, 'r') as f:
        data = json.load(f)

    data.append(info)

    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"\n{info} Appended info to {filename}.\n")

def save_cnic_image(image, filename='image.jpg'):
    if not os.path.exists(config('CNIC_SAVE_PATH')):
        os.makedirs(config('CNIC_SAVE_PATH'))
    
    cv2.imwrite(f"{config('CNIC_SAVE_PATH')}/{filename}", image)
    print(f"Image saved as {filename}.")

def extract_card_details(data):
    # convert all text part into a string
    card_details_str = ""
    for text, _ in data:
        card_details_str += text + ","

    return card_details_str

def get_center_frame(frame):
    # get 50x50 pixel from the center of the frame
    # using current dimensions
    height, width = frame.shape[:2]
    x1 = width // 2 - 25
    x2 = width // 2 + 25
    y1 = height // 2 - 25
    y2 = height // 2 + 25
    return frame[y1:y2, x1:x2]

def get_lower_right_frame(frame):
    # get 50x50 pixel from the lower right corner of the frame
    # using current dimensions
    height, width = frame.shape[:2]
    x1 = width - 120
    x2 = width - 70
    y1 = height - 120
    y2 = height - 70
    return frame[y1:y2, x1:x2]

def check_if_card_in_frame(frame):

    frame = get_lower_right_frame(frame)
    # print("mean: ", np.mean(frame))
    
    if np.mean(frame) > 150:
        return False
    
    return True

def process_batch_ocr_results(ocr_results):
    boxes = ocr_results[0]
    texts = ocr_results[1]
    giberish = ocr_results[2]

    return boxes, texts, giberish

def get_mp_list_object_from_cam_id(cam_id, mp_list):
    for item in mp_list:
        if item["cam_id"] == cam_id:
            return item
    return None

def update_mp_list_object_from_cam_id(cam_id, mp_list, key, new_data):
    for item in mp_list:
        if item["cam_id"] == cam_id:
            item[key] = new_data
            return
    return None

def resize_to_largest(images):
    # Determine the largest dimensions
    max_height = max(image.shape[0] for image in images)
    max_width = max(image.shape[1] for image in images)
    
    # Resize all images to the largest dimensions
    resized_images = [cv2.resize(image, (max_width, max_height)) for image in images]
    return resized_images