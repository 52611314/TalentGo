from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_database(url: str):
    engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 3})
    return engine, sessionmaker(engine, class_=Session, expire_on_commit=False)
