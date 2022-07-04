import logging
from datetime import datetime

import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.config import Database as Database_

log = logging.getLogger(__name__)


class Database:
    def __init__(self, config: Database_) -> None:
        if config.engine == "postgres":
            engine_string = f"{config.username}:{config.password}@{config.host}:{config.port}/{config.name}"
            self.engine = db.create_engine("postgresql+psycopg2://" + engine_string)
        elif config.engine == "sqlite":
            self.engine = db.create_engine(
                "sqlite:///" + config.name + ".db?check_same_thread=false"
            )
        else:
            raise Exception(f"{config.engine} setup has not been defined")

        log.info(f"{config.engine} loaded")

        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.Base = declarative_base()

        class AmiiboStock(self.Base):  # type: ignore
            __tablename__ = "amiibo_stock"

            id = db.Column(db.Integer, primary_key=True)
            stockist = db.Column(db.String)
            price = db.Column(db.String)
            stock = db.Column(db.String)
            timestamp = db.Column(
                db.DateTime, default=datetime.now, onupdate=datetime.now
            )

        self.Base.metadata.create_all(self.engine)  # type: ignore
        log.info("amiibo_stock table loaded")
