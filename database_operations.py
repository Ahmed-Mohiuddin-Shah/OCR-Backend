from database.cruds.timestamp import create_timestamp
from database.cruds.cnic import check_if_cnic_exists, update_cnic, create_cnic
from database.utils.database import get_db

from database.schemas.cnic import CnicCreate
from database.schemas.timestamp import TimestampCreate

from helpers import extract_card_details

import datetime

# adds data to postgreSQL database
async def add_data_to_database(name_and_cnic, all_info, camera_id):
    
    db = await anext(get_db())

    cnic = name_and_cnic[1][0]
    name = "Unknown" if name_and_cnic[0][0] is None else name_and_cnic[0][0]
    n_confidence = name_and_cnic[0][1]/5 if name != "Unknown" else 0

    if name_and_cnic[1][1] < 0.8:
        print(f"CNIC Confidence level too low: {name_and_cnic[1][1]}")
        return
    
    if cnic is None:
        print("CNIC not found")
        return

    db_cnic = check_if_cnic_exists(db, cnic)

    if db_cnic is not None:
        print(f"Cnic already exists in database: {cnic}")
        
        name_confidence_database = db_cnic.name_confidence

        if n_confidence > name_confidence_database:
            print("confidence level is higher than the one in database")
            print(f"Updating name for cnic: {cnic}")
            cnic_img_path = f'cnics/{cnic}.jpg'

            new_cnic = CnicCreate(
                cnic=cnic,
                name=name,
                name_confidence=n_confidence,
                all_details=extract_card_details(all_info),
                cnic_img_path=cnic_img_path
            )
            
            update_cnic(db, new_cnic)

            print("Name updated successfully")
    else:
        print(f"Cnic does not exist in database: {cnic}")
        cnic_img_path = f'cnics/{cnic}.jpg'


        print(extract_card_details(all_info))

        new_cnic = CnicCreate(
            cnic=cnic,
            name=name,
            name_confidence=n_confidence,
            all_details=extract_card_details(all_info),
            cnic_img_path=cnic_img_path
        )

        create_cnic(db, new_cnic)

        print("Cnic added successfully")

    timestamp = TimestampCreate(
        cnic=cnic,
        timestamp=datetime.datetime.now(),
        camera_id=camera_id,
    )

    new_timestamp = create_timestamp(db, timestamp)

    print(f"Data added to database: {name_and_cnic}, {new_timestamp.timestamp}")
