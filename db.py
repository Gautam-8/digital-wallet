from sqlite3 import Date
from typing import Annotated

from sqlalchemy import DateTime
from sqlmodel import Session, SQLModel, create_engine



sqlite_file_name = "wallet.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)



import datetime
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password: str
    phone_number: str | None = None
    balance: float = Field(default=0.00)
    created_at: str = Field(default_factory=datetime.datetime.utcnow)
    updated_at: str = Field(default_factory=datetime.datetime.utcnow)


class Transaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    transaction_type: str  # 'CREDIT', 'DEBIT', 'TRANSFER_IN', 'TRANSFER_OUT'
    amount: float
    description: str | None = None
    reference_transaction_id: int | None = Field(default=None, foreign_key="transaction.id")
    recipient_user_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: str = Field(default_factory=datetime.datetime.utcnow)

class TransferDetails(SQLModel, table=True):
    transfer_id: int | None = Field(default=None, primary_key=True)
    sender_user_id: int = Field(foreign_key="user.id")
    recipient_user_id: int = Field(foreign_key="user.id")
    amount: float
    description: str | None = None
    status: str
    created_at: str = Field(default_factory=datetime.datetime.utcnow)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session




