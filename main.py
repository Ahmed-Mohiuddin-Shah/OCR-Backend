import multiprocessing as mp

from patterns import run_system
from database_operations import get_db_config

import asyncio

async def main():

    frame_queue = mp.Queue()
    ocr_results_queue = mp.Queue()
    previously_saved_cnic = mp.Manager().list(
        [
            {
                "cam_id": -1,
                "cnic": None,
            }
        ]
    )
    
    card_already_in_holder = mp.Manager().list(
        [
            {
                "cam_id": -1,
                "status": False
            }
        ]
    )

    db_config = await get_db_config()

    cameras = db_config["cameras"]

    run_system(
        cams=cameras,
        frame_queue=frame_queue, 
        ocr_results_queue=ocr_results_queue,
        previously_saved_cnic=previously_saved_cnic, 
        card_already_in_holder=card_already_in_holder
    )

if __name__ == "__main__":
    asyncio.run(main())