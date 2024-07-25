import json
import os
import re
from typing import Counter
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np
from helpers import *
from decouple import config

def do_OCR_on_cropped_frame(ocr, frame):

    result = ocr.ocr(frame, cls=True)

    if len(result) == 0:
        return None

    for idx in range(len(result)):
        res = result[idx]
    return res

def is_upside_down(ocr, image):
    """
    Determine if the given image has text that is upside down by comparing confidence scores.
    
    Args:
    - ocr: The PaddleOCR instance.
    - image: The input image.
    
    Returns:
    - bool: True if the image is upside down, False otherwise.
    """
    # Perform OCR on the original image
    result_original = ocr.ocr(image, cls=True)
    if not result_original or not result_original[0]:
        return False

    original_confidence = np.mean([line[1][1] for line in result_original[0]])

    # Flip the image upside down
    flipped_image = cv2.flip(image, -1)

    # Perform OCR on the flipped image
    result_flipped = ocr.ocr(flipped_image, cls=True)
    if not result_flipped or not result_flipped[0]:
        return False

    flipped_confidence = np.mean([line[1][1] for line in result_flipped[0]])

    # Compare confidence scores
    return flipped_confidence > original_confidence

def correct_orientation(frame, should_flip):
    """
    Corrects the orientation of the given frame using PaddleOCR.
    
    Args:
    - frame: The input image frame.
    
    Returns:
    - The correctly oriented frame.
    """
    if should_flip:
        return cv2.flip(frame, -1)
    return frame

def most_common_name_and_cnic(data):
    # Separate names and CNICs into their own lists
    names = [name for name, cnic in data]
    cnics = [cnic for name, cnic in data]


    check_if_all_cnics_none = all(cnic is None for cnic in cnics)
    check_if_all_names_none = all(name is None for name in names)

    if check_if_all_cnics_none:
        return (None, 0), (None, 0)

    # remove none from cnics
    cnics = [cnic for cnic in cnics if cnic is not None]

    if not check_if_all_names_none:
        names = [name for name in names if name is not None]

    # Use Counter to count occurrences
    name_counter = Counter(names)
    cnic_counter = Counter(cnics)

    # Find the most common name and CNIC
    most_common_name = name_counter.most_common(1)
    most_common_cnic = cnic_counter.most_common(1)
    
    # Return the most common name and CNIC
    return most_common_name[0] if most_common_name else (None, 0), most_common_cnic[0] if most_common_cnic else (None, 0)

def get_cropped_frame(image):

    x1, y1 = 51, 207
    x2, y2 = 721, 751
    
    image = image[y1:y2, x1:x2]
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

    # cv2.imshow("Frame", ROI)
    return ROI

def check_if_majority_of_frame_is_white(image):
    # check if majority of frame is white
    if np.mean(image) > 170:
        return True
    else:
        return False
    
def parse_data(data):
    # Extract the text from the data
    text = [entry[1][0] for entry in data]

    return text

def extract_all_details_str(data):
    # Extract all details from the data
    details = ""
    for i, text in enumerate(data):
        if text is None:
            continue
        details += text + " "
    
    return details


def extract_name_and_cnic(data):
    
    name = None
    cnic = None
    
    # name_identifiers = ['name']
    cnic_pattern = re.compile(r'\b\d{5}-\d{7}-\d{1}\b')
    
    for i, text in enumerate(data):
        # Check for name
        if text.lower() == 'name' or text.lower() == 'name:' or text.lower() == 'name;' or text.lower() == 'name,':
            # Assuming the actual name follows the identifier
            if i + 1 < len(data):
                if data[i + 1] == ':':
                    name = data[i + 2]
                if data[i + 1] == ';':
                    name = data[i + 2]
                if data[i + 1] == ',':
                    name = data[i + 2]
                else:
                    name = data[i + 1]
        
        # Check for CNIC using the pattern
        if cnic_pattern.match(text):
            cnic = text
            if len(cnic) > 15:
                cnic = cnic[:15]
    
    return name, cnic

def is_majority_whitish(image, threshold=0.7):
    
    # Convert the image to grayscale
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Define a threshold to consider a pixel as white
    white_threshold = 170  # This can be adjusted based on your needs
    
    # Threshold the grayscale image to create a binary image
    _, binary_image = cv2.threshold(gray_image, white_threshold, 255, cv2.THRESH_BINARY)
    
    # Count the number of white pixels
    white_pixel_count = np.sum(binary_image == 255)
    
    # Calculate the total number of pixels
    total_pixels = binary_image.size
    
    # Calculate the proportion of white pixels
    white_pixel_ratio = white_pixel_count / total_pixels

    # print(white_pixel_ratio)
    
    # Check if the majority of the image is whitish
    is_whitish = white_pixel_ratio >= threshold
    
    return is_whitish


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

import psycopg2

def extract_card_details(data):
    card_details = []
    for item in data:
        # Extract the text detail from the second element of each item
        detail = item[1][0]
        card_details.append(detail)
    return card_details

# adds data to postgreSQL database
def add_data_to_database(name_and_cnic, all_info):
    while True:
        try:
            conn = psycopg2.connect(
                dbname=config('DB_NAME'),
                user=config('DB_USER'),
                password=config('DB_PASSWORD'),
                host=config('DB_HOST'),
                port=config('DB_PORT')
            )
            break
        except psycopg2.OperationalError:
            print("Error connecting to PostgreSQL. Retrying...")
            continue

    cur = conn.cursor()

    cnic = name_and_cnic[1][0]
    name = "Unknown" if name_and_cnic[0][0] is None else name_and_cnic[0][0]
    n_confidence = name_and_cnic[0][1]/5 if name != "Unknown" else 0

    if name_and_cnic[1][1] < 0.8:
        print(f"CNIC Confidence level too low: {name_and_cnic[1][1]}")
        return
    
    if cnic is None:
        print("CNIC not found")
        return

    check_if_cnic_exists_query = "SELECT * FROM cnic WHERE cnic = %s"

    cur.execute(check_if_cnic_exists_query, (cnic,))
    result = cur.fetchall()

    if len(result) > 0:
        print(f"Cnic already exists in database: {cnic}")

        result = result[0]
        
        name_confidence_database = result[2]

        if n_confidence > name_confidence_database:
            print("confidence level is higher than the one in database")
            print(f"Updating name for cnic: {cnic}")
            update_name_query = "UPDATE cnic SET name = %s, name_confidence = %s, all_details = %s WHERE cnic = %s"

            cur.execute(update_name_query, (name, n_confidence, extract_card_details(all_info), cnic))
            conn.commit()

        # return
    else:
        print(f"Cnic does not exist in database: {cnic}")
        cnic_img_path = f'cnics/{cnic}.jpg'


        print(extract_card_details(all_info))

        insert_query = "INSERT INTO cnic (cnic, name, name_confidence, all_details, cnic_img_path) VALUES (%s, %s, %s, %s, %s)"

        cur.execute(insert_query, (cnic, name, n_confidence, extract_card_details(all_info), cnic_img_path))
        conn.commit()



    add_timstamp_query = "INSERT INTO timestamp (cnic, timestamp) VALUES (%s, now())"

    cur.execute(add_timstamp_query, (cnic,))

    conn.commit()

    cur.close()

    conn.close()

    print(f"Data added to database: {name_and_cnic}")


def get_center_frame(frame):
    # get 50x50 pixel from the center of the frame
    # using current dimensions
    height, width = frame.shape[:2]
    x1 = width // 2 - 25
    x2 = width // 2 + 25
    y1 = height // 2 - 25
    y2 = height // 2 + 25
    return frame[y1:y2, x1:x2]

def check_if_card_in_frame(frame):

    frame = get_center_frame(frame)
    
    if np.mean(frame) > 150:
        return False
    
    return True