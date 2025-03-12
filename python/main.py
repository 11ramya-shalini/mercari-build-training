import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager, contextmanager
import json
import hashlib
from typing import Dict, List, Optional
import threading


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
items_file = pathlib.Path(__file__).parent.resolve() / "items.json"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"
SQL_File = pathlib.Path(__file__).parent.resolve() / "db" / "items.sql"

local_db = threading.local()
@contextmanager
def get_db():
    if not os.path.exists(db):
        raise FileNotFoundError(f"Database file {db} does not exist.")
    if not hasattr(local_db, "conn"):
        local_db.conn = sqlite3.connect(db, check_same_thread=False )
        local_db.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
         
    try:
        yield local_db.conn    
    finally:
        pass

##### for STEP 4-1
# Function to read the items from the JSON file
'''def read_from_json():
    if not os.path.exists(items_file):
        with open(items_file, 'r') as f:
            json.dump({"items": []},f)
    with open(items_file, 'r') as f:
        return json.load(f)

# Function to save items to the JSON file
def write_from_json(data):
    with open(items_file, 'w') as f:
        json.dump(data, f, indent=4)'''
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

######### FOR STEP 5
def get_items_from_db(db: sqlite3.Connection):
    try:
        cursor = db.cursor()
        query = """
        SELECT items.name, categories.name AS category, image_name
        FROM items
        JOIN categories
        ON category_id = categories.id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        items_list = [{"name": name, "category":category, "image_name": image_name} for name, category, image_name in rows]
        result = {"items": items_list}

        return result

    except Exception as e:
        return {f"An unexpected error occurred: {e}"}
    finally:
        pass
       # cursor.close()
###############

######## for STEP 5
def get_items_from_db_by_id(id: int, db: sqlite3.Connection)-> Dict[str, List[Dict[str, str]]]:
    try:
        cursor = db.cursor()
        query = """
        SELECT items.id, items.name, categories.name AS category, items.image_name
        FROM items
        JOIN categories
        ON items.category_id = categories.id
        """
        cursor.execute(query, (id,))
        rows = cursor.fetchone()
        
        item = [{"id": row[0], "name": row[1], "category": row[2], "image_name": row[3]}]
        return {"items": item}

    except Exception as e:
        return {f"An unexpected error occurred: {e}"}
    
    finally:
        pass
        #cursor.close()
###########  


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

    insert_item_by_db(Item(name=name, category=category, image=hashed_image), db)
    return AddItemResponse(**{"message": f"item received: {name}, {category}, {hashed_filename}"})

 ###### modifying for STEP 5-1
@app.get("/items")
def get_items(db: sqlite3.Connection = Depends(get_db)):
    all_data = get_items_from_db(db)
    return all_data
########## 

####### modified for STEP 5   
@app.get("/items/{item_id}")
def get_item_by_id(item_id):
    item_id_int = int(item_id)
    all_data = get_items_from_db_by_id()
    item = all_data["items"] [item_id_int -1]
    return item
############## 

######### for STEP 5-2
@app.get("/search")
def search_items_by_keyword(keyword: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        query = """
        SELECT name, category, image_name
        FROM items
        WHERE name LIKE ?
        """
        pattern = f"%{keyword}%"
        cursor.execute(query, (pattern,))
        rows = cursor.fetchall()
        items_list =  [{"name": name, "category":category, "image_name": image_name} for name, category, image_name in rows]
        return  {"items": items_list}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

    finally:
        pass
        #cursor.close()
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
    id: Optional[int] = None
    name: str
    category: str
    image : str



def insert_item_by_db(item: Item, db: sqlite3.Connection) -> int:
    cursor = None
    try:
        cursor = db.cursor()
        query_category = "SELECT id FROM categories WHERE name = ?"
        cursor.execute(query_category, (item.category,))
        rows = cursor.fetchone()
        if rows is None:
            insert_query_category = "INSERT INTO categories (name) VALUES (?)"
            cursor.execute(insert_query_category, (item.category,))
            category_id = cursor.lastrowid
        else:
            category_id = rows[0]
            
        query = """
        INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)
        """
        cursor.execute(query, (item.name, category_id, item.image))

        db.commit()
    except sqlite3.DatabaseError as e:
        db.rollback() 
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if cursor:
            cursor.close()
 
    