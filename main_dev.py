import datetime
import json
import time
from typing import Counter
import paddle
from paddleocr import PaddleOCR, draw_ocr
import cv2
import numpy as np
from psycopg2 import Date
from motion_detector import MotionDetection
from decouple import config

import multiprocessing
import asyncio


from database_operations import add_data_to_database, get_db_config

from PaddleOCR.ppocr.utils.logging import get_logger # type: ignore
import logging
logger = get_logger()
logger.setLevel(logging.ERROR)

async def main():

    db_config = await get_db_config()

    cameras = db_config["cameras"]

    print(cameras)

    return

    cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
    print("Video source set" if cap.isOpened() else "Video source not set")

    # # Remove the existing model weights if they exist
    # if os.path.exists(config(MODEL_WEIGHTS_PATH)):
    #     shutil.rmtree(config(MODEL_WEIGHTS_PATH))

    # Download and initialize PaddleOCR again
    try:
        ocr = PaddleOCR(lang='en', cls=True, angle_classifier=True, use_gpu=False)
        # Your OCR code here
    except Exception as e:
        print(f"An error occurred: {e}")

    print("OCR initialized")

    md = MotionDetection()

    global info
    info = []
    infos = []

    card_already_in_holder = False

    count = 0

    print("Entered Loop")

    previously_saved_cnic = None

    while True:

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        ret, frame = cap.read()
        count += 1


        if count % 4  != 0:
            continue

        print(count, "at: ", datetime.datetime.now())

        if frame is None:
            print("Frame is None")
            print("Reconnecting to camera")
            cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
            print("Connected", "system started at: ", count)
            continue

        # if md.detect_motion(frame):
        #     print("Motion detected")
        #     continue

        cropped_frame = get_cropped_frame(frame)

        if cropped_frame is None:
            continue

        is_card_in_frame = check_if_card_in_frame(cropped_frame)

        if not card_already_in_holder:
            if not is_card_in_frame:
                print("Card not in holder")
                continue
        elif is_card_in_frame:
                print("Card already in holder")
                continue

        for _ in range(3):
            ret, frame = cap.read()
            if frame is None:
                print("Frame is None")
                print("Reconnecting to camera")
                cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
                print("Connected")
                continue
        
        cropped_frame = get_cropped_frame(frame)

        frame_list = []
        number_of_frames = 1
        current_info = do_OCR_on_cropped_frame(ocr, cropped_frame)

        img_counter = 0
        all_info = []
        save_image = None

        if current_info is None:
            print("No text detected", "at: ", datetime.datetime.now(), "type: ", type(current_info), "time: ", time.time())
            card_already_in_holder = False
            continue

        print("OCR done")

        print("checking if card already in holder", card_already_in_holder)
        if card_already_in_holder:
            print("Card already in holder")
            continue
        
        print("Card not in holder")
        print("Current info: ", current_info, "at: ", datetime.datetime.now(), "type: ", type(current_info), "time: ", time.time())
        name_and_cnic = extract_name_and_cnic(parse_data(current_info))

        name, cnics = name_and_cnic
        
        if name_and_cnic[1] is None:
            print("card not entered")
            continue

        start_time = time.time()
        db_start_insert_time = 0
        print("card entered", name_and_cnic, "at: ", start_time)

        # this is dev branch

        # for _ in range(2):
        #     ret, frame = cap.read()
        #     if frame is None:
        #         print("Frame is None")
        #         print("Reconnecting to camera")
        #         cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
        #         print("Connected")
        #         continue
        # for _ in range(number_of_frames):
        #     ret, frame = cap.read()
        #     if frame is None:
        #         print("Frame is None")
        #         print("Reconnecting to camera")
        #         cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
        #         print("Connected")
        #         continue
        #     frame_list.append(frame)
            
        # should_flip = is_upside_down(ocr, get_cropped_frame(frame_list[0]))
        # print("Should flip: ", should_flip)
        # for frame in frame_list:
            # frame = get_cropped_frame(frame)
            # corect_orientation_frame = correct_orientation(frame, should_flip)
            # cv2.imshow('frame', corect_orientation_frame)
            # current_info = do_OCR_on_cropped_frame(ocr, corect_orientation_frame)
            # if current_info is None:
                # continue
        name_and_cnic = extract_name_and_cnic(parse_data(current_info))
            # print(name_and_cnic)
        img_counter += 1
        if name_and_cnic[1] is not None and img_counter == number_of_frames:
            all_info = current_info
            # for _ in range(2):
            #     ret, frame = cap.read()
            #     if frame is None:
            #         print("Frame is None")
            #         print("Reconnecting to camera")
            #         cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
            #         print("Connected")
            # ret, frame = cap.read()
            # if frame is None:
            #     print("Frame is None")
            #     print("Reconnecting to camera")
            #     cap =cv2.VideoCapture(config("VIDEO_SOURCE"))
            #     print("Connected")
            # cropped_frame = get_cropped_frame(frame)
            save_image = cropped_frame
        print(name_and_cnic)
        info.append(name_and_cnic)
        
        frame_list = []

        if len(info) > 0:
            name_and_cnic = most_common_name_and_cnic(info)
            print("Name and CNIC:", name_and_cnic)
            db_start_insert_time = time.time()
            if previously_saved_cnic is None and name_and_cnic[1][0] is not None:
                print("New card detected, previoiusly saved cnic is None and now setting it to: ", name_and_cnic[1][0])
                add_data_to_database(name_and_cnic, all_info)
                previously_saved_cnic = name_and_cnic[1][0]
                card_already_in_holder = True
                if name_and_cnic[1][0] is not None and save_image is not None:
                    save_cnic_image(save_image, name_and_cnic[1][0] + ".jpg")
            elif previously_saved_cnic is not None and name_and_cnic[1] is not None and name_and_cnic[1][0] != previously_saved_cnic:
                print("New card detected, previoiusly saved cnic is not None and now setting it to: ", name_and_cnic[1][0])
                add_data_to_database(name_and_cnic, all_info)
                previously_saved_cnic = name_and_cnic[1][0]
                if name_and_cnic[1][0] is not None and save_image is not None:
                    save_cnic_image(save_image, name_and_cnic[1][0] + ".jpg")
                card_already_in_holder = True
            else:
                print("Card was already in holder", name_and_cnic[1][0], "did not save it again")
                card_already_in_holder = True
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
    cv2.destroyAllWindows()

    print("Total frames: ", count)

asyncio.run(main())