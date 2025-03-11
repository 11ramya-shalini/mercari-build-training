import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import json
import hashlib
#from typing import Optional


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
items_file = pathlib.Path(__file__).parent.resolve() / "items.json"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"
#SQL_DB = pathlib.Path(__file__).parent.resolve()

def get_db():
    if not db.exists():
         yield

    conn = sqlite3.connect(db, check_same_thread=False )
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()

##### for STEP 4-1
# Function to read the items from the JSON file
def read_from_json():
    if not os.path.exists(items_file):
        with open(items_file, 'r') as f:
            json.dump({"items": []},f)
    with open(items_file, 'r') as f:
        return json.load(f)

# Function to save items to the JSON file
def write_from_json(data):
    with open(items_file, 'w') as f:
        json.dump(data, f, indent=4)
#############   

# STEP 5-1: set up the database connection
def setup_database():
    pass 


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("uvicorn")
logger.level = logging.DEBUG # for STEP 4-6
images = pathlib.Path(__file__).parent.resolve() / "images"
origins = [os.environ.get("FRONT_URL", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class HelloResponse(BaseModel):
    message: str


@app.get("/", response_model=HelloResponse)
def hello():
    return HelloResponse(**{"message": "Hello, world!"})


class AddItemResponse(BaseModel):
    message: str


# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
async def add_item(
    name: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    if not name or not category:
        raise HTTPException(status_code=400, detail="name, category, and image iare required")
    
    insert_item(Item(name=name, category=category)
    return AddItemResponse(**{"message": f"item received: {name}"})

 ###### for STEP 4-3   
 @app.get("/items")
 def get_items():
    all_data = read_from_json() 
    return all_data 
##########    


# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(image)


class Item(BaseModel):
    name: str
    category: str
    image_name: str



def insert_item(item: Item):
    # STEP 4-2: add an implementation to store an item
    handy = read_from_json()
    write_from_json(handy)
    