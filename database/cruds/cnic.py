from sqlalchemy.orm import Session
from database.models import Cnic
from database.schemas import CnicCreate

def get_cnics(db: Session, skip: int = 0):
    return db.query(Cnic).offset(skip).all()

def create_cnic(db: Session, cnic: CnicCreate):
    db_cnic = Cnic(**cnic.model_dump())
    db.add(db_cnic)
    db.commit()
    db.refresh(db_cnic)

    return db_cnic

def get_cnic_by_id(db: Session, cnic_id: int):
    return db.query(Cnic).filter(Cnic.id == cnic_id).first()

def get_total_cnics_count(db: Session):
    return db.query(Cnic).count()
