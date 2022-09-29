import logging
from datetime import datetime

import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.config import Database as Database_
from stockist.stockist import Stock

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
            Website = db.Column(db.String)
            Title = db.Column(db.String)
            Price = db.Column(db.String)
            Stock = db.Column(db.String)
            Colour = db.Column(db.String)
            URL = db.Column(db.String)
            Image = db.Column(db.String)
            timestamp = db.Column(
                db.DateTime, default=datetime.now, onupdate=datetime.now
            )

        class LastScraped(self.Base):  # type: ignore
            __tablename__ = "last_scraped"

            stockist = db.Column(db.String, primary_key=True)
            timestamp = db.Column(
                db.DateTime, default=datetime.now, onupdate=datetime.now
            )

        self.Base.metadata.create_all(self.engine)  # type: ignore
        log.info("database tables loaded")

    def get_table_object(self, table_name: str):
        self.Base.metadata.reflect(self.engine)  # type: ignore
        return self.Base.metadata.tables.get(table_name)  # type: ignore

    def get_last_github_check(self):
        table_object = self.get_table_object(table_name="last_scraped")
        return self.session.query(table_object).filter_by(stockist="github.com").first()

    def get_days_since_last_github_check(self):
        if self.get_last_github_check() is None:
            return 1
        return abs(self.get_last_github_check()[1] - datetime.now()).days

    def update_or_insert_last_scraped(self, stockist):
        table_object = self.get_table_object(table_name="last_scraped")
        check = self.session.query(table_object).filter_by(stockist=stockist).first()
        if check is None:
            self.engine.execute(table_object.insert().values(stockist=stockist))
        else:
            self.session.query(table_object).filter_by(stockist=stockist).update(
                {"timestamp": datetime.now()}
            )
            self.session.commit()
            self.session.flush()

    def check_first_run(self):
        table_object = self.get_table_object(table_name="amiibo_stock")
        return self.session.query(table_object).first()

    def check_then_add_or_update_amiibo(self, data):
        statistics = {"New": 0, "Updated": 0, "Deleted": 0}
        output = []
        table_object = self.get_table_object(table_name="amiibo_stock")
        check = (
            self.session.query(table_object).filter_by(Website=data[0]["Website"]).all()
        )
        if len(check) == 0:
            for datum in data:
                log.info(f"Adding {datum['Title']}")
                statistics["New"] += 1
                self.engine.execute(table_object.insert().values(datum))
            log.info(f"New items saved: {statistics['New']}")
            return data

        for item in check:
            matched = False
            for datum in data:
                if datum["URL"] == item.URL:
                    matched = True
                    if float(datum["Price"]) != float(item.Price):
                        datum["Stock"] = Stock.PRICE_CHANGE.value
                        datum["Colour"] = 0xFFFFFF
                        log.info(
                            f"Price changed for {item.Title} from {item.Price} to {datum['Price']}"
                        )
                        statistics["Updated"] += 1
                        self.session.query(table_object).filter_by(URL=item.URL).update(
                            {"Price": datum["Price"]}
                        )
                        self.session.commit()
                        self.session.flush()

                        output.append(datum)
                    break
            if not matched:
                builder = {
                    "Colour": 0xFF0000,
                    "Title": item.Title,
                    "Image": item.Image,
                    "URL": item.URL,
                    "Price": item.Price,
                    "Stock": Stock.DELISTED.value,
                    "Website": item.Website,
                }
                output.append(builder)
                log.info(f"{item.Title} is no longer listed")
                statistics["Deleted"] += 1
                self.session.query(table_object).filter_by(id=item.id).delete()
                self.session.commit()
                self.session.flush()

        for datum in data:
            matched = False
            for item in check:
                if datum["URL"] == item.URL:
                    matched = True
            if not matched:
                output.append(datum)
                log.info(f"Adding {datum['Title']}")
                statistics["New"] += 1
                self.engine.execute(table_object.insert().values(datum))

        log.info(
            f"Added: {statistics['New']}, Updated: {statistics['Updated']}, Deleted: {statistics['Deleted']}"
        )
        return output
