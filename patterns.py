import asyncio
import datetime
import time
import cv2
import multiprocessing as mp

import os

import sys
import signal

from PaddleOCR.tools.infer.predict_system import TextSystem

from helpers import (
    check_if_card_in_frame,
    crop_frame,
    get_cropped_frame,
    process_batch_ocr_results,
    extract_name_and_cnic,
    get_mp_list_object_from_cam_id,
    update_mp_list_object_from_cam_id,
    extract_card_details,
    save_cnic_image,
    resize_to_largest,
)
from database_operations import add_data_to_database

def pre_detection_pattern_for_cnic(
    camera_id: int,
    cam_url: str,
    crop: str,
    cam_type: str,
    frame_queue: mp.Queue,
    previously_saved_cnic: mp.Manager,
    card_already_in_holder: mp.Manager,
):

    previously_saved_cnic.append(
        {
            "cam_id": camera_id,
            "cnic": None,
        }
    )

    card_already_in_holder.append({"cam_id": camera_id, "status": False})

    startX, startY, width, height = [int(i) for i in crop.split(",")]

    cap = cv2.VideoCapture(cam_url)

    print(
        f"Video source of {camera_id} set"
        if cap.isOpened()
        else f"Video source of {camera_id} not set"
    )

    is_card_in_frame = False

    count = 0
    frame = None

    while True:

        ret, frame = cap.read()
        count += 1

        if count % 4 != 0:
            continue

        # print(count, "at: ", datetime.datetime.now())

        if frame is None:
            print("Frame is None")
            print("Reconnecting to camera")
            cap = cv2.VideoCapture(cam_url)
            print("Connected", "system started at: ", count)
            continue

        # db crop
        cropped_frame = crop_frame(frame, startX, startY, width, height)
        # auto crop
        # cropped_frame = get_cropped_frame(cropped_frame)

        # if cropped_frame is None:
        #     continue
        # cv2.imshow(str(camera_id), cropped_frame)

        # # wait
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #     break

        is_card_in_frame = check_if_card_in_frame(cropped_frame)

        if not get_mp_list_object_from_cam_id(camera_id, card_already_in_holder)[
            "status"
        ]:
            if not is_card_in_frame:
                # print("Card not in holder")
                continue
        elif is_card_in_frame:
            # print("Card already in holder")
            continue

        for _ in range(3):
            ret, frame = cap.read()
            if frame is None:
                print("Frame is None")
                print("Reconnecting to camera")
                cap = cv2.VideoCapture(cam_url)
                print("Connected")
                continue

        if frame is None:
            print("Frame is None")
            print("Reconnecting to camera")
            cap = cv2.VideoCapture(cam_url)
            print("Connected")
            continue

        cropped_frame = crop_frame(frame, startX, startY, width, height)
        # cropped_frame = get_cropped_frame(cropped_frame)

        queue_obj = {
            "camera_id": camera_id,
            "cam_type": cam_type,
            "timestamp": datetime.datetime.now(),
            "frame": cropped_frame,
        }

        frame_queue.put(queue_obj)

def post_detection_pattern_for_cnic(
    result: dict, previously_saved_cnic: mp.Manager, card_already_in_holder: mp.Manager
):

    cam_id = result["camera_id"]
    timestamp = result["timestamp"]
    save_image = result["frame"]
    texts = result["texts"]

    if len(texts) == 0:
        update_mp_list_object_from_cam_id(
            cam_id, card_already_in_holder, "status", None
        )
        # print("No text detected")
        return

    if get_mp_list_object_from_cam_id(cam_id, card_already_in_holder)["status"]:
        # print("Card already in holder")
        return

    print("Card not in holder")
    name, n_confidence, cnic, c_confidence = extract_name_and_cnic(texts)

    print(f"Name: {name} with confidence: {n_confidence}")
    print(f"CNIC: {cnic} with confidence: {c_confidence}")

    if cnic is None:
        print("CNIC not detected")
        return

    start_time = time.time()
    print("card entered", cnic, "at: ", start_time)

    all_info = extract_card_details(texts)
    print("All info: ", all_info)

    previously_saved_cnic_current_camera = get_mp_list_object_from_cam_id(
        cam_id, previously_saved_cnic
    )["cnic"]

    if previously_saved_cnic_current_camera is None and cnic is not None:
        print(
            "New card detected, previoiusly saved cnic is None and now setting it to: ",
            cnic,
        )
        asyncio.run(
            add_data_to_database(
                name, n_confidence, cnic, c_confidence, all_info, timestamp, cam_id
            )
        )
        update_mp_list_object_from_cam_id(cam_id, previously_saved_cnic, "cnic", cnic)
        update_mp_list_object_from_cam_id(
            cam_id, card_already_in_holder, "status", True
        )
        if cnic is not None and save_image is not None:
            save_cnic_image(save_image, cnic + ".jpg")
    elif (
        previously_saved_cnic_current_camera is not None
        and cnic is not None
        and cnic != previously_saved_cnic_current_camera
    ):
        print(
            "New card detected, previoiusly saved cnic is not None and now setting it to: ",
            cnic,
        )
        asyncio.run(
            add_data_to_database(
                name, n_confidence, cnic, c_confidence, all_info, timestamp, cam_id
            )
        )
        update_mp_list_object_from_cam_id(cam_id, previously_saved_cnic, "cnic", cnic)
        update_mp_list_object_from_cam_id(
            cam_id, card_already_in_holder, "status", True
        )
        if cnic is not None and save_image is not None:
            save_cnic_image(save_image, cnic + ".jpg")
    else:
        print("Card was already in holder", cnic, "did not save it again")
        update_mp_list_object_from_cam_id(
            cam_id, card_already_in_holder, "status", True
        )

    end_time = time.time()
    print("card exited", cnic, "at: ", end_time)
    print("Time taken: ", end_time - start_time)

def post_detection_loop(
    ocr_results_queue: mp.Queue,
    previously_saved_cnic: mp.Manager,
    card_already_in_holder: mp.Manager,
):

    while True:

        if ocr_results_queue.empty():
            continue

        result = ocr_results_queue.get()

        type = result["cam_type"]

        if type == "cnic":
            print("Post detection pattern for CNIC", result["camera_id"])
            post_detection_pattern_for_cnic(
                result, previously_saved_cnic, card_already_in_holder
            )
        else:
            continue

def run_ocr(args, frame_queue: mp.Queue, ocr_results_queue: mp.Queue):

    os.environ["CUDA_VISIBLE_DEVICES"] = "0"

    frames = []
    timestamps = []
    cam_ids = []
    cam_types = []

    detections = []

    ts = TextSystem(args)

    while True:

        if len(frames) > 0:
            # print("Running OCR on frames")

            resized_frames = resize_to_largest(frames)

            detections = ts(resized_frames)

            boxes, texts, _ = process_batch_ocr_results(detections)

            result_entry = {}

            for id, text in enumerate(texts):
                result_entry = {
                    "camera_id": cam_ids[id],
                    "cam_type": cam_types[id],
                    "frame": frames[id],
                    "timestamp": timestamps[id],
                    "texts": text,
                }

                ocr_results_queue.put(result_entry)
            frames = []
            timestamps = []
            cam_ids = []
            cam_types = []
            detections = []

        while not frame_queue.empty():
            queue_entry = frame_queue.get()

            cam_ids.append(queue_entry["camera_id"])
            cam_types.append(queue_entry["cam_type"])
            timestamps.append(queue_entry["timestamp"])
            frames.append(queue_entry["frame"])
            # print("Frame added to frames list")

def signal_handler(sig, frame, processes):
    print("Signal received, terminating processes...")
    for process in processes:
        process.terminate()
    for process in processes:
        process.join()
    print("All processes terminated")
    sys.exit(0)

def run_system(
    cams: list,
    frame_queue: mp.Queue,
    ocr_results_queue: mp.Queue,
    args,
    previously_saved_cnic: mp.Manager,
    card_already_in_holder: mp.Manager,
):
    processes = []

    for cam in cams:
        if cam["type"] == "cnic":
            p = mp.Process(
                target=pre_detection_pattern_for_cnic,
                args=(
                    cam["id"],
                    cam["cam_url"],
                    cam["crop"],
                    cam["type"],
                    frame_queue,
                    previously_saved_cnic,
                    card_already_in_holder,
                ),
            )
        else:
            continue
        p.start()
        processes.append(p)

    pocr = mp.Process(target=run_ocr, args=(args, frame_queue, ocr_results_queue))
    pocr.start()
    processes.append(pocr)

    pocr_post = mp.Process(
        target=post_detection_loop,
        args=(ocr_results_queue, previously_saved_cnic, card_already_in_holder),
    )
    pocr_post.start()
    processes.append(pocr_post)

    signal.signal(
        signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, processes)
    )

    for p in processes:
        p.join()