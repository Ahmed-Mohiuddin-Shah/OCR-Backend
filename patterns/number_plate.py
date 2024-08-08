import datetime
import json
import os
import time
import cv2
import multiprocessing as mp

from helpers import (
    get_mp_list_object_from_cam_id,
    update_mp_list_object_from_cam_id,
    find_best_plate,
    average_timestamp    
)

def pre_detection_pattern_for_num_plate_rfid(
    camera_id: int,
    cam_url: str,
    crop: str,
    cam_type: str,
    frame_queue: mp.Queue,
    number_plate_detect_cache,
):
    number_plate_detect_cache.append(
        {
            "cam_id": camera_id,
            "number_plates": [],
        }
    )

    startX, startY, width, height = [int(i) for i in crop.split(",")]
    cap = cv2.VideoCapture(cam_url)

    print(
        f"Video source of {camera_id} set"
        if cap.isOpened()
        else f"Video source of {camera_id} not set"
    )

    while True:
            
            ret, frame = cap.read()
    
            if frame is None:
                print("Frame is None")
                cap = cv2.VideoCapture(cam_url)
                continue
    
            frame = frame[startY : startY + height, startX : startX + width]
    
            frame_queue.put(
                {
                    "camera_id": camera_id,
                    "cam_type": cam_type,
                    "timestamp": datetime.datetime.now(),
                    "frame": frame,
                }
            )

            time.sleep(0.01)

def post_detection_pattern_for_num_plate_rfid(
    result: dict,
    number_plate_detect_cache,
):
    cam_id = result["camera_id"]
    timestamp = result["timestamp"]
    number_plates = result["texts"]

    print(number_plates, len(number_plates), cam_id)

    current_cache_number_plates = get_mp_list_object_from_cam_id(
        cam_id=cam_id, mp_list=number_plate_detect_cache
    )["number_plates"]

    if len(number_plates) > 0:
        current_cache_number_plates.append(
            [number_plates, timestamp]
        )
        print(current_cache_number_plates)
        update_mp_list_object_from_cam_id(
            cam_id=cam_id,
            mp_list=number_plate_detect_cache,
            key="number_plates",
            new_data=current_cache_number_plates,
        )
    else:
        current_cache_number_plates = get_mp_list_object_from_cam_id(
            cam_id=cam_id, mp_list=number_plate_detect_cache
        )["number_plates"]

        update_mp_list_object_from_cam_id(
            cam_id=cam_id,
            mp_list=number_plate_detect_cache,
            key="number_plates",
            new_data=[],
        )

        # print(current_cache_number_plates)

        timestamps = []
        plates = []

        for plate, _timestamp in current_cache_number_plates:
            timestamps.append(_timestamp)
            plates.append(plate)
        
        best_plate, plate_confidence = find_best_plate(plates)

        avg_timestamp = average_timestamp(timestamps)

        if best_plate:
            print(
                    f"Best plate: {best_plate} with confidence: {plate_confidence}"
                )
                # save to data.json

                # create data.json if not exists
            if not os.path.exists("data.json"):
                with open("data.json", "w") as f:
                    json.dump([], f)
                print("data.json created.")

                with open("data.json", "r") as f:
                    data = json.load(f)

                    data.append(
                    {
                        "plate": best_plate,
                        "confidence": plate_confidence,
                        "timestamp": avg_timestamp,
                    }

                    )

                with open("data.json", "w") as f:
                    json.dump(data, f, indent=4)
                print("Appended info to data.json.")
                
            else:
                print("No valid plate found")

