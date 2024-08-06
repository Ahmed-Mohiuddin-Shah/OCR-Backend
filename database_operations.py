from database.cruds.cam_type import get_cam_types
from database.cruds.camera import get_cameras
from database.cruds.timestamp import create_timestamp, check_if_card_entered_in_last
from database.cruds.cnic import check_if_cnic_exists, update_cnic, create_cnic
from database.utils.database import get_db

from database.schemas.cnic import CnicCreate
from database.schemas.timestamp import TimestampCreate

from helpers import extract_card_details
from decouple import config

import datetime

# adds data to postgreSQL database
async def add_data_to_database(name, n_confidence, cnic, c_confidence, all_info, timestamp:datetime.datetime.now, camera_id):
    
    db = await anext(get_db())

    name = "Unknown" if name is None else name
    n_confidence = n_confidence if name != "Unknown" else 0
    print(str(all_info))

    if c_confidence < 0.8:
        print("CNIC Confidence level is below threshold")
        return
    
    if cnic is None:
        print("CNIC not found")
        return

    db_cnic = check_if_cnic_exists(db, cnic)

    if check_if_card_entered_in_last(db, config('CARD_REPEATED_THRESHOLD_MINUTES'), cnic):
        print(f"Card already entered in last {config('CARD_REPEATED_THRESHOLD_MINUTES')} minutes: {cnic}")
        return

    if db_cnic is not None:
        print(f"Cnic already exists in database: {cnic}")
        
        name_confidence_database = db_cnic.name_confidence

        if n_confidence > name_confidence_database:
            print("name confidence level is higher than the one in database")
            print(f"Updating name for cnic: {cnic}")
            cnic_img_path = f'cnics/{cnic}.jpg'

            new_cnic = CnicCreate(
                cnic=cnic,
                name=name,
                name_confidence=n_confidence,
                all_details=str(all_info),
                cnic_img_path=cnic_img_path
            )
            
            update_cnic(db, new_cnic)

            print("Name updated successfully")
    else:
        print(f"Cnic does not exist in database: {cnic}")
        cnic_img_path = f'cnics/{cnic}.jpg'


        new_cnic = CnicCreate(
            cnic=cnic,
            name=name,
            name_confidence=n_confidence,
            all_details=str(all_info),
            cnic_img_path=cnic_img_path
        )

        create_cnic(db, new_cnic)

        print("Cnic added successfully")

    # convert timestamp to datetime object
    #   Input should be a valid number [type=float_type, input_value=datetime.datetime(2024, 8, 5, 14, 54, 16, 531276), input_type=datetime]
    

    timestamp = TimestampCreate(
        cnic=cnic,
        timestamp=timestamp,
        cam_id=camera_id
    )

    new_timestamp = create_timestamp(db, timestamp)

    print(f"Data added to database: {new_timestamp.cnic}, {new_timestamp.timestamp}, {new_timestamp.cam_id}")

async def get_db_config():
    db = await anext(get_db())

    config = {}

    cameras = get_cameras(db)
    types = get_cam_types(db)

    db_cameras = []

    for camera in cameras:
        for cam_type in types:
            if camera.type == cam_type.type:
                db_cameras.append({
                    "id": camera.id,
                    "name": camera.name,
                    "type": cam_type.type,
                    "cam_url": camera.cam_url,
                    "crop": camera.crop,
                })
    
    config["cameras"] = db_cameras

    return config