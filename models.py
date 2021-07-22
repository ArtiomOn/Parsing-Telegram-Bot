from sqlalchemy import create_engine, MetaData, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from config import user, password, host, port, database

database_dsn = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
meta = MetaData()

Base = declarative_base()


class Note(Base):
    __tablename__ = "note"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    note = Column(String)
