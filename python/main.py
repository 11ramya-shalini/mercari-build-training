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
from typing import Dict, List, Optional


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
items_file = pathlib.Path(__file__).parent.resolve() / "items.json"
db = pathlib.Path(__file__).parent.resolve() / "mercari.sqlite3"
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
        hashed_image = f"{hash_value}.jpg"
        hashed_image_path = images / hashed_image
        
        with open(hashed_image_path, 'wb') as f:
            f.write(image)
        image_file.file.close()
        return hashed_image

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
        logger.debug(f"Fetched rows: {rows}")
        items_list = [{"name": name, "category":category, "image_name": image_name} for name, category, image_name in rows]
        result = {"items": items_list}

        return result

    except Exception as e:
        logger.error(f"Error fetching items: {e}")
        return {f"An unexpected error occurred: {e}"}
    finally:
        cursor.close()
###############

######## for STEP 5
def get_items_from_db_by_id(id: int, db: sqlite3.Connection)-> Dict[str, List[Dict[str, str]]]:
    try:
        cursor = db.cursor()
        logger.debug(f"Executing query to fetch item with ID: {id}")

        query = """
        SELECT items.id, items.name, categories.name AS category, items.image_name
        FROM items
        JOIN categories ON items.category_id = categories.id
        WHERE items.id = ?
        """

        cursor.execute(query, (id,))
        row = cursor.fetchone()

        if row:
            logger.debug(f"Found item: {row}")
            item = [{"id": row[0], "name": row[1], "category": row[2], "image_name": row[3]}]
            return {"items": item}
        else:
            logger.debug(f"No item found for ID: {id}")
            return {"items": []}
    except Exception as e:
        logger.error(f"Error during DB query: {e}")
        return {"error": f"An unexpected error occurred: {e}"}
    finally:
        cursor.close()
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
    allow_credentials=True,
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
    try:
        if not name or not category or not image:
            raise HTTPException(status_code=400, detail="name, category, and image are required")
    
        hashed_image = hash_image(image)

        insert_item_by_db(Item(name=name, category=category, image_name=hashed_image), db)
        return AddItemResponse(**{"message": f"item received: {name}, {category}, {hashed_image}"})
    except Exception as e:
        logger.error(f"An error occurred while processing the item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")   

 ###### modifying for STEP 5-1
@app.get("/items")
def get_items(db: sqlite3.Connection = Depends(get_db)):
    all_data = get_items_from_db(db)
    return all_data
########## 

####### modified for STEP 5   
@app.get("/items/{item_id}")
def get_item_by_id(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        logger.debug(f"Fetching item with ID: {item_id}")
        all_data = get_items_from_db_by_id(item_id, db)
        if isinstance(all_data, dict) and "items" in all_data:
            items = all_data["items"]
            if items:
                logger.debug(f"Item found: {items[0]}")
                return items[0]
            else:
                logger.debug("No items found for the given ID")
                raise HTTPException(status_code=404, detail="Item not found")
        else:
            logger.error(f"Unexpected response format: {all_data}")
            raise HTTPException(status_code=500, detail="Unexpected response format")
    except Exception as e:
        logger.error(f"Error fetching item: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
                    
############## 

######### for STEP 5-2
@app.get("/search")
def search_items_by_keyword(keyword: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        query = """
        SELECT items.name, categories.name AS category_name, items.image_name
        FROM items
        JOIN categories ON items.category_id = categories.id
        WHERE items.name LIKE ?
        """

        pattern = f"%{keyword}%"
        cursor.execute(query, (pattern,))
        rows = cursor.fetchall()
        items_list =  [{"name": name, "category":category, "image_name": image_name} for name, category, image_name in rows]
        return  {"items": items_list}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

    finally:
        cursor.close()
############


# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name: str):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(image)


class Item(BaseModel):
    id: Optional[str] = None
    name: str
    category: str
    image_name: str



def insert_item_by_db(item: Item, db: sqlite3.Connection) -> int:
    try:
        cursor = db.cursor()
        query_category = "SELECT id FROM categories WHERE name = ?"
        cursor.execute(query_category, (item.category,))
        rows = cursor.fetchone()
        if rows is None:
            insert_query_category = "INSERT INTO categories (name) VALUES (?)"
            cursor.execute(insert_query_category, (item.category,))
            category_id = cursor.lastrowid
            print(f"Inserted new category with id {category_id}")
        else:
            category_id = rows[0]
            print(f"Category {item.category} found with id {category_id}")
        query = """
        INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)
        """
        cursor.execute(query, (item.name, category_id, item.image_name))

        db.commit()
        print(f"Inserted item into DB: {item.name}, {category_id}, {item.image_name}")
    except Exception as e:
        logger.error(f"Error inserting item into DB: {str(e)}")
        raise RuntimeError(f"An unexpected error occurred while inserting the item: {e}")
    finally:
        cursor.close()