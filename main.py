from datetime import datetime, timezone
import json
import time
from typing import Counter
import paddle
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np
from psycopg2 import Date
from helpers import *
from motion_detector import MotionDetection
from decouple import config

# threading stuff

import threading
from queue import Queue


from ppocr.utils.logging import get_logger # type: ignore
import logging
logger = get_logger()
logger.setLevel(logging.ERROR)

global cap
cap = cv2.VideoCapture("test11.mp4")
print("Video source set" if cap.isOpened() else "Video source not set")


# # Remove the existing model weights if they exist
# if os.path.exists(config(MODEL_WEIGHTS_PATH)):
#     shutil.rmtree(config(MODEL_WEIGHTS_PATH))

# Download and initialize PaddleOCR again
try:
    ocr = PaddleOCR(lang='en', cls=True, angle_classifier=True, use_gpu=False)

    ocr_instances = [PaddleOCR(lang='en', cls=True, angle_classifier=True, use_gpu=False) for _ in range(5)]

    ocr_for_orientation = PaddleOCR(lang='en', cls=True, angle_classifier=True, use_gpu=False)

    # Your OCR code here
except Exception as e:
    print(f"An error occurred: {e}")

print("OCR initialized")

md = MotionDetection()

global info
info = []
infos = []

# Global List to store entries
global_list = []
global results_list
results_list = []


global card_already_in_holder
global previously_saved_cnic
card_already_in_holder = False
previously_saved_cnic = None

# Lock to synchronize threads for thread safe access to global_list
list_lock = threading.Lock()

def main_loop():

    global cap, info, card_already_in_holder, previously_saved_cnic, results_list

    count = 0
    print("Entered Loop")

    while True:

        ret, frame = cap.read()
        count += 1

        if count % 4  != 0:
            continue

        print(count, "at: ", datetime.now())

        if frame is None:
            break
            print("Frame is None")
            print("Reconnecting to camera")
            cap = cv2.VideoCapture(config("VIDEO_SOURCE"))
            print("Connected", "system started at: ", count)
            continue

        # if md.detect_motion(frame):
        #     print("Motion detected")
        #     continue

        cropped_frame = get_cropped_frame(frame)

        if cropped_frame is None:
            continue
        current_info = do_OCR_on_cropped_frame(ocr, cropped_frame)

        img_counter = 0
        all_info = []
        save_image = None

        if current_info is None:
            print("No text detected", "at: ", datetime.now(), "type: ", type(current_info), "time: ", time.time())
            card_already_in_holder = False
            continue

        print("OCR done")

        print("checking if card already in holder", card_already_in_holder)
        if card_already_in_holder:
            print("Card already in holder")
            continue
        
        print("Card not in holder")
        print("Current info: ", current_info, "at: ", datetime.now(), "type: ", type(current_info), "time: ", time.time())
        name_and_cnic = extract_name_and_cnic(parse_data(current_info))

        _, cnic = name_and_cnic
        
        if cnic is None:
            print("card not entered")
            continue

        start_time = time.time()
        db_start_insert_time = 0
        print("card entered", name_and_cnic, "at: ", start_time)

        if previously_saved_cnic is not None and cnic == previously_saved_cnic:
            print("Card already in holder")
            card_already_in_holder = True
            continue
        else:
            print("Card not in holder")
            card_already_in_holder = False
        
        previously_saved_cnic = cnic

        frame_list = []
        for _ in range(5):
            ret, frame = cap.read()
            if frame is None:
                print("Frame is None")
                print("Reconnecting to camera")
                cap = cv2.VideoCapture(config("VIDEO_SOURCE"))
                print("Connected")
                continue
            frame_list.append(frame)

        #get UTC timestamp for postgres timestamp with timezone
        timestamp = datetime.now(timezone.utc) 
        print("Timestamp: ", timestamp)
        entry = [frame_list, timestamp]

        with list_lock:
            global_list.append(entry)
            
        print("Added entry to global list:")
        frame_list = []        

        # if len(info) > 0:
        #     name_and_cnic = most_common_name_and_cnic(info)
        #     print("Name and CNIC:", name_and_cnic)
        #     db_start_insert_time = time.time()
        #     if previously_saved_cnic is None and name_and_cnic[1][0] is not None:
        #         print("New card detected, previoiusly saved cnic is None and now setting it to: ", name_and_cnic[1][0])
        #         add_data_to_database(name_and_cnic, all_info)
        #         previously_saved_cnic = name_and_cnic[1][0]
        #         card_already_in_holder = True
        #         if name_and_cnic[1][0] is not None and save_image is not None:
        #             save_cnic_image(save_image, name_and_cnic[1][0] + ".jpg")
        #     elif previously_saved_cnic is not None and name_and_cnic[1] is not None and name_and_cnic[1][0] != previously_saved_cnic:
        #         print("New card detected, previoiusly saved cnic is not None and now setting it to: ", name_and_cnic[1][0])
        #         add_data_to_database(name_and_cnic, all_info)
        #         previously_saved_cnic = name_and_cnic[1][0]
        #         if name_and_cnic[1][0] is not None and save_image is not None:
        #             save_cnic_image(save_image, name_and_cnic[1][0] + ".jpg")
        #         card_already_in_holder = True
        #     else:
        #         print("Card was already in holder", name_and_cnic[1][0], "did not save it again")
        #         card_already_in_holder = True

        end_time = time.time()
        db_end_insert_time = time.time()
        db_insert_time = db_end_insert_time - db_start_insert_time
        total_time = end_time - start_time
        total_time_in_milliseconds = total_time * 1000
        print("Time taken for card: ", total_time_in_milliseconds)
        print("Time taken for db insert: ", db_insert_time)

        info = []
        img_counter = 0

    cap.release()

    print("Total frames: ", count)
    print(results_list)

# Worker function to process entries from the global list
def worker_thread():
    while True:
        with list_lock:
            if global_list:
                entry = global_list.pop(0)
                images, timestamp = entry
            else:
                continue
        
        results = []
        all_info_list = []
        all_info = None
        threads = []

        should_flip = is_upside_down(ocr, get_cropped_frame(images[3]))

        def process_image(ocr_instance, image):
            image = get_cropped_frame(image)
            corect_orientation_frame = correct_orientation(image, should_flip)
            current_info = do_OCR_on_cropped_frame(ocr_instance, corect_orientation_frame)

            name_and_cnic = extract_name_and_cnic(parse_data(current_info))
            
            all_info_list.append(current_info)

            print(name_and_cnic)
            results.append(name_and_cnic)

        results = [None] * 5
        for i in range(5):
            t = threading.Thread(target=process_image, args=(ocr_instances[i], images[i]))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()

        threads = []

        all_info = all_info_list.pop()
        image = images[3]
        
        name_and_cnic = most_common_name_and_cnic(results)
        print("Name and CNIC:", name_and_cnic)

        result_entry = [name_and_cnic, all_info, image, timestamp]
        with list_lock:
            results_list.append(result_entry)
        # print("Processed entry and added to results list:", result_entry)

# Start the main loop in a separate thread
main_thread = threading.Thread(target=main_loop)
main_thread.start()

# Start the worker threads
for _ in range(5):
    t = threading.Thread(target=worker_thread)
    t.start()