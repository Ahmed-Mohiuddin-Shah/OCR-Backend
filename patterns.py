import datetime
import cv2
import multiprocessing as mp

from PaddleOCR.tools.infer.predict_system import TextSystem

from helpers import check_if_card_in_frame, crop_frame, get_cropped_frame, process_batch_ocr_results

def pre_detection_pattern_for_cnic(camera_id: int, cam_url:str, crop: str, cam_type: str, frame_queue: mp.Queue):

    startX, startY, width, height = [int(i) for i in crop.split(",")]

    cap =cv2.VideoCapture(cam_url)

    print(f"Video source of {camera_id} set" if cap.isOpened() else f"Video source of {camera_id} not set")

    info = []
    infos = []

    card_already_in_holder = False
    is_card_in_frame = False
    previously_saved_cnic = None
    count = 0
    frame = None

    while True:

        ret, frame = cap.read()
        count += 1

        if count % 4  != 0:
            continue

        # print(count, "at: ", datetime.datetime.now())

        if frame is None:
            print("Frame is None")
            print("Reconnecting to camera")
            cap =cv2.VideoCapture(cam_url)
            print("Connected", "system started at: ", count)
            continue

        # db crop
        cropped_frame = crop_frame(frame, startX, startY, width, height)
        # auto crop
        cropped_frame = get_cropped_frame(cropped_frame)

        if cropped_frame is None:
            continue

        # is_card_in_frame = check_if_card_in_frame(cropped_frame)

        # if not is_card_in_frame:
        #     # print("Card not in holder")
        #     continue

        for _ in range(3):
            ret, frame = cap.read()
            if frame is None:
                print("Frame is None")
                print("Reconnecting to camera")
                cap =cv2.VideoCapture(cam_url)
                print("Connected")
                continue
        
        cropped_frame = crop_frame(frame, startX, startY, width, height)
        cropped_frame = get_cropped_frame(frame)

        queue_obj = {
            "camera_id": camera_id,
            "cam_type": cam_type,
            "timestamp": datetime.datetime.now(),
            "frame": cropped_frame
        }

        # print("Frame queue object created", queue_obj)

        frame_queue.put(queue_obj)

        # print("Frame added to queue")

def run_system(cams: list, frame_queue: mp.Queue, ocr_results_queue:mp.Queue, args):
    processes = []

    for cam in cams:
        if cam["type"] == "cnic":
            p = mp.Process(target=pre_detection_pattern_for_cnic, args=(cam["id"], cam["cam_url"], cam["crop"], cam["type"], frame_queue))
        else:
            continue
        p.start()
        processes.append(p)

    pocr = mp.Process(target=run_ocr, args=(args, frame_queue, ocr_results_queue))
    pocr.start()
    processes.append(pocr)

    pocr_post = mp.Process(target=post_detection_loop, args=(ocr_results_queue,))
    pocr_post.start()
    processes.append(pocr_post)

    for p in processes:
        p.join()

def post_detection_pattern_for_cnic(ocr_results_queue: mp.Queue):
    
    while True:

        pass

def post_detection_loop(ocr_results_queue: mp.Queue):

    while True:

        # print(ocr_results_queue.qsize())

        if ocr_results_queue.empty():
            continue
    
        result = ocr_results_queue.get()

def run_ocr(args, frame_queue: mp.Queue, ocr_results_queue: mp.Queue):

    frames = []
    timestamps = []
    cam_ids = []
    cam_types = []

    detections = []

    ts=TextSystem(args)

    while True:

        if len(frames) > 0:
            # print("Running OCR on frames")
            detections = ts(frames)
            frames = []

            boxes, texts, _ = process_batch_ocr_results(detections)

            print(texts)

            result_entry = {}

            for id, text in enumerate(texts):
                result_entry = {
                    "camera_id": cam_ids[id],
                    "cam_type": cam_types[id],
                    "timestamp": timestamps[id],
                    "texts": text
                }

                ocr_results_queue.put(result_entry)

        while not frame_queue.empty():
            queue_entry = frame_queue.get()

            cam_ids.append(queue_entry["camera_id"])
            cam_types.append(queue_entry["cam_type"])
            timestamps.append(queue_entry["timestamp"])
            frames.append(queue_entry["frame"])