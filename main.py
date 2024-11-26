# main.py

import datetime as dt
from fastapi import FastAPI, Request, BackgroundTasks, Response
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import requests
import uuid
from requests.auth import HTTPBasicAuth
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from fastapi_utils.tasks import repeat_every
import os

app = FastAPI()
engine = create_engine("sqlite:///sessions.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

ACCOUNT_ID = os.getenv("ACCOUNT_ID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
client = Client(ACCOUNT_ID, AUTH_TOKEN)
SERVICE_NUMBER = os.getenv("SERVICE_NUMBER")
IMAGE_OUTPUT_PATH = os.getenv("IMAGE_OUTPUT_PATH")


class UploadSession(Base):
    __tablename__ = "upload_sessions"
    session_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    session_end_time = Column(DateTime)
    closed = Column(Boolean, default=False)

    images = relationship("Image", back_populates="upload_session")


class Image(Base):
    __tablename__ = "images"
    image_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String)
    from_mobile = Column(String)
    twilio_account_id = Column(String)
    image_url = Column(String)
    attached_message = Column(String)
    upload_session_id = Column(Integer, ForeignKey("upload_sessions.session_id"))

    upload_session = relationship("UploadSession", back_populates="images")


Base.metadata.create_all(bind=engine)


def download_with_basic_auth(url, username=ACCOUNT_ID, password=AUTH_TOKEN):
    response = requests.get(url, auth=HTTPBasicAuth(username, password))
    if response.status_code == 200:
        return response.content
    else:
        response.raise_for_status()


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()

    for k, v in form_data.items():
        print(f"{k}: {v}")

    from_mobile = form_data.get("From").split(":")[-1]
    message_body = "_".join(form_data.get("Body").split(" "))
    account_sid = form_data.get("AccountSid")
    message_sid = form_data.get("MessageSid")
    num_images = int(form_data.get("NumMedia")) or 0

    resp = MessagingResponse()

    if num_images == 0:
        print("No images attached.")
        resp.message("Incorrect input.")
        return Response(content=str(resp), media_type="application/xml")

    db = SessionLocal()

    session = (
        db.query(UploadSession).filter_by(customer_id=from_mobile, closed=False).first()
    )
    current_time = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    if not session:
        # Create new session
        print("Creating new session.")
        session = UploadSession(
            customer_id=from_mobile,
            session_end_time=current_time + dt.timedelta(seconds=30),
        )
        db.add(session)
        db.commit()
        # Send reply
        resp.message("Beginning Upload Session.")
    else:
        # Update session
        print("Updating existing session.")
        session.session_end_time = max(
            session.session_end_time, current_time + dt.timedelta(seconds=30)
        )

    print(f"Parsing {num_images} images of session {session.session_id}.")
    for i in range(num_images):
        image = Image(
            message_id=message_sid,
            from_mobile=from_mobile,
            twilio_account_id=account_sid,
            image_url=form_data.get(f"MediaUrl{i}"),
            attached_message=message_body,
            upload_session_id=session.session_id,
        )
        db.add(image)
        db.commit()
        img_data = download_with_basic_auth(form_data.get(f"MediaUrl{i}"))
        with open(os.path.join(IMAGE_OUTPUT_PATH, f"{image.image_id}.jpg"), "wb") as f:
            f.write(img_data)
    db.commit()
    db.close()
    print()
    return Response(content=str(resp), media_type="application/xml")


@app.on_event("startup")
@repeat_every(seconds=20)
def check_sessions():
    print("Checking for closed sessions.")
    db = SessionLocal()
    sessions = (
        db.query(UploadSession)
        .filter(
            UploadSession.session_end_time <= dt.datetime.now(dt.timezone.utc),
            UploadSession.closed == False,  # noqa:E712
        )
        .all()
    )
    for session in sessions:
        print(f"Closing session {session.session_id}.")
        # Get number of images
        img_count = len(session.images)
        # Mark session as closed
        session.closed = True
        db.commit()
        # Send message with the number of images received
        client.messages.create(
            to="whatsapp:" + session.customer_id,
            from_="whatsapp:" + SERVICE_NUMBER,
            body=f"Received and uploaded {img_count} images."
        )
    db.close()
