from sqlalchemy import create_engine, MetaData, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

from config import user, password, host, port, database

database_dsn = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
meta = MetaData()

Base = declarative_base()


class Note(Base):
    __tablename__ = "note"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    user_id = Column(Integer)
    note = Column(String)


class Translation(Base):
    __tablename__ = "translation"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    original_text = Column(String)
    translation_text = Column(String)
    original_language = Column(String)
    translation_language = Column(String)
    created_at = Column(DateTime)


class Search(Base):
    __tablename__ = 'balaboba_search'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    search_input = Column(String)
    search_result = Column(String)
    created_at = Column(DateTime)
