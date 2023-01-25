from pymongo import MongoClient
from coaster import Coaster, Track
import os
from datetime import datetime, timedelta
from dataclasses import asdict

DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
client = MongoClient(f'mongodb://{DB_USER}:{DB_PASS}@mongo:27017/')

db = client.get_database('coasterDB')
db.coasters.create_index("expire_at", expireAfterSeconds=0)


def load_coaster(_id: str) -> Coaster | None:
    if coaster := db.coasters.find_one({'_id': _id}):
        coaster['tracks'] = [Track(**track) for track in coaster['tracks']]
        del coaster['expire_at']
        return Coaster(**coaster)
    return None


def store_coaster(coaster: Coaster) -> None:
    coaster_dict = asdict(coaster)

    if coaster.sbno_date:
        coaster_dict['expire_at'] = datetime.utcnow() + timedelta(days=14)
    elif coaster.closing_date:
        coaster_dict['expire_at'] = datetime.utcnow() + timedelta(days=180)
    else:
        coaster_dict['expire_at'] = datetime.utcnow() + timedelta(days=30)

    db.coasters.insert_one(coaster_dict)
