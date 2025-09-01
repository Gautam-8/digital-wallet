import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from db import Transaction, TransferDetails, User, get_session
from db import create_db_and_tables


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    phone_number: str | None = None



SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/users/")
def read_users(session: SessionDep):
    users = session.exec(select(User)).all()
    return users

@app.get("/users/{user_id}")
def read_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/users/")
def create_user(user: UserCreate, session: SessionDep):
    db_user = User(**user.dict())
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.get("/wallet/{user_id}/balance")
def get_balance(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.id,
        "balance": user.balance,
        "last_updated": user.updated_at
    }



@app.post("/wallet/{user_id}/add-money")
def add_money(user_id: int, amount: float, description: str, session: SessionDep):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user balance
    user.balance += amount
    user.updated_at = datetime.datetime.utcnow()
    session.add(user)
    
    # Create transaction record
    transaction = Transaction(
        user_id=user.id,
        transaction_type="CREDIT",
        amount=amount,
        description=description
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return {
        "transaction_id": transaction.id,
        "user_id": user.id,
        "amount": amount,
        "new_balance": user.balance,
        "transaction_type": transaction.transaction_type
    }


@app.post("/wallet/{user_id}/withdraw")
def withdraw_money(user_id: int, amount: float, description: str, session: SessionDep):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Update user balance
    user.balance -= amount
    user.updated_at = datetime.datetime.utcnow()
    session.add(user)
    
    # Create transaction record
    transaction = Transaction(
        user_id=user.id,
        transaction_type="DEBIT",
        amount=amount,
        description=description
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return {
        "transaction_id": transaction.id,
        "user_id": user.id,
        "amount": amount,
        "new_balance": user.balance,
        "transaction_type": transaction.transaction_type
    }



@app.get("/transactions/{user_id}")
def get_transactions(
    session: SessionDep,
    user_id: int,
    page: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    total = session.exec(select(Transaction).where(Transaction.user_id == user_id)).all()
    transactions = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .offset(page)
        .limit(limit)
        .order_by(Transaction.created_at.desc())
    ).all()
    
    return {
        "transactions": transactions,
        "total": total.__len__(),
        "offset": page,
        "limit": limit
    }


@app.get("/transactions/detail/{transaction_id}")
def get_transaction_detail(transaction_id: int, session: SessionDep):
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction



@app.post("/transactions/")
def create_transaction(transaction: Transaction, session: SessionDep):
    user = session.get(User, transaction.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if transaction.transaction_type == "CREDIT":
        user.balance += transaction.amount
    elif transaction.transaction_type == "DEBIT":
        if user.balance < transaction.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance -= transaction.amount
    else:
        raise HTTPException(status_code=400, detail="Invalid transaction type")
    
    user.updated_at = datetime.datetime.utcnow()
    session.add(user) 
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    return transaction


@app.post("/transfer")
def transfer_money(
    session: SessionDep,
    sender_user_id: int,
    recipient_user_id: int,
    amount: float,
    description: str | None = None,
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    sender = session.get(User, sender_user_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    recipient = session.get(User, recipient_user_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    if sender.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Deduct from sender
    sender.balance -= amount
    sender.updated_at = datetime.datetime.utcnow()
    session.add(sender)
    
    # Add to recipient
    recipient.balance += amount
    recipient.updated_at = datetime.datetime.utcnow()
    session.add(recipient)

    # Create sender transaction
    sender_transaction = Transaction(
        user_id=sender.id,
        transaction_type="TRANSFER_OUT",
        amount=amount,
        description=description,
        recipient_user_id=recipient.id
    )
    session.add(sender_transaction)
    session.commit()
    session.refresh(sender_transaction)
    
    # Create recipient transaction
    recipient_transaction = Transaction(
        user_id=recipient.id,
        transaction_type="TRANSFER_IN",
        amount=amount,
        description=description,
        reference_transaction_id=sender_transaction.id,
        recipient_user_id=sender.id
    )
    session.add(recipient_transaction)
    session.commit()
    session.refresh(recipient_transaction)

    transerDetails = TransferDetails(
        sender_user_id=sender.id,
        recipient_user_id=recipient.id,
        amount=amount,
        description=description,
        status="completed"
    )
    session.add(transerDetails)
    session.commit()
    session.refresh(transerDetails)
    
    
    return {
        "transfer_id": transerDetails.transfer_id,
        "sender_transaction_id": sender_transaction.id,
        "recipient_transaction_id": recipient_transaction.id,
        "amount": amount,
        "sender_new_balance": sender.balance,
        "recipient_new_balance": recipient.balance,
        "status": "completed"
    }



@app.get("/transfer/{transfer_id}")
def get_transfer_details(transfer_id: str, session: SessionDep):
    transfer = session.exec(
        select(TransferDetails).where(TransferDetails.transfer_id == transfer_id)
    ).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer

