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
SQL_File = pathlib.Path(__file__).parent.resolve() / "db" / "items.sql"

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

##### for STEP 4-3
def hash_image(image_file: UploadFile):
    try:
        # read image from image_file
        image = image_file.file.read()
        # hash the image
        hash_value = hashlib.sha256(image).hexdigest()
        hashed_image_name = f"{hash_value}.jpg"
        hashed_image_path = images / hashed_image_name
        
        with open(hashed_image_path, 'wb') as f:
            f.write(image)
        return hashed_image_name

    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {e}")    
#############

# STEP 5-1: set up the database connection
def setup_database():
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    if SQL_File.exists():
        with open(SQL_File, 'r') as f:
            cursor.executescript(f.read())
    conn.commit()
    conn.close()        


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
    if not name or not category or not image:
        raise HTTPException(status_code=400, detail="name, category, and image are required")
    
    hashed_image = hash_image(image)

    ####### for STEP 5-1
    cursor = db.cursor()
    cursor.execute("INSERT INTO items (name, category, image_name) VALUES (?, ?, ?)", (name, category, image_name))
    db.commit()
    
    insert_item(Item(name=name, category=category, image=hashed_image))
    return AddItemResponse(**{"message": f"item received: {name}"})

 ###### for STEP 4-3   ##### modifying for STEP 5-1
@app.get("/items")
def get_items(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    return [{"name": item["name"], "category": item["category"], "image_name": item["image_name"]} for item in items]

########## 

####### for STEP 4-5
@app.get("/items/{item_id}")
def get_item_by_id(item_id):
    item_id_int = int(item_id)
    all_data = read_from_json()
    item = all_data["items"][item_id_int - 1]
    return item 
############## 

######### for STEP 5-2
@app.get("/search")
def search_items(keyword: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor
    cursor.execute("SELECT * FROM items WHERE name LIKE ?", ('%' + keyword + '%',))
    items = cursor.fetchall()
    return {"items": [{"name": item["name"], "category": item["category"], "image_name": item["image_name"]} for item in items]}
############

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
    id: str
    name: str
    category: str
    image : str



def insert_item(item: Item):
    # STEP 4-2: add an implementation to store an item
    handy = read_from_json()
    handy["items"].append({"name": item.name, "category": item.category, "image_name": item.image})
    write_from_json(handy)
    