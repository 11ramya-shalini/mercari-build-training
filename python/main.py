import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel, Field
from typing import Optional
from contextlib import asynccontextmanager
import json
import hashlib


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"
SQL_DB = pathlib.Path(__file__).parent.resolve() / "db" / "items.sql"


def get_db():
    if not db.exists():
        setup_database()

    conn = sqlite3.connect(db, check_same_thread=False )
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
  conn = sqlite3.connect(db)
    with open(SQL_DB, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")  


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("uvicorn")
logger.level = logging.DEBUG
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
    if not name:
        raise HTTPException(status_code=400, detail="name, category, and image iare required")

    image_bytes = await image.read()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    image_filename = f"{image_hash}.jpg"
    image_path = pathlib.Path(__file__).parent.resolve() / "images" / image_filename

    with open(image_path, "wb") as f:
        f.write(image_bytes)

    item = Item(name=name, category=category, image_name=image_filename)
    insert_item(item, db)
    
    return {"message": f"item received: {name}"}


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
    id: Optional[int] = Field(None, description="Auto-generated ID")
    name: str
    category: str
    image_name: str


def insert_item(item: Item):
    # STEP 4-2: add an implementation to store an item
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id FROM categories WHERE name = ?", (item.category,))
        category_row = cursor.fetchone()
        
        if category_row is None:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (item.category,))
            db.commit()  
            category_id = cursor.lastrowid
        else:
            category_id = category_row["id"]

        cursor.execute("SELECT id FROM items WHERE name = ?", (item.name,))
        existing_item = cursor.fetchone()

        if existing_item:
            logger.info(f"Item already exists: {existing_item}")
            raise HTTPException(status_code=400, detail="Item already exists")

        cursor.execute(
            "INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)",
            (item.name, category_id, item.image_name),
        )
        db.commit()
        logger.info(f"New item inserted: {item.dict()}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save item: {e}")
        raise HTTPException(status_code=500, detail="Failed to save item")



@app.get("/items")
def get_items(db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT items.id, items.name, categories.name AS category_name, items.image_name
            FROM items
            JOIN categories ON items.category_id = categories.id
        """)
        items = cursor.fetchall()

        return {"items": [dict(row) for row in items]}
    except Exception as e:
        logger.error(f"Failed to get items: {e}")
        raise HTTPException(status_code=500, detail="Failed to get items")


@app.get("/items/{item_id}")
def get_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT items.id, items.name, categories.name AS category_name, items.image_name
            FROM items
            JOIN categories ON items.category_id = categories.id
            WHERE items.id = ?
        """, (item_id,))
        item = cursor.fetchone()

        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        return dict(item)
    except Exception as e:
        logger.error(f"Failed to get item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get item")


@app.get("/search")
def search_items(keyword: str = Query(..., min_length=1), db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT items.name, categories.name AS category_name, items.image_name
            FROM items
            JOIN categories ON items.category_id = categories.id
            WHERE items.name LIKE ? OR categories.name LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%"))
        items = cursor.fetchall()

        return {
            "items": [
                {"name": row["name"], "category": row["category_name"], "image_name": row["image_name"]}
                for row in items
            ]
        }
    except Exception as e:
        logger.error(f"Failed to search items: {e}")
        raise HTTPException(status_code=500, detail="Failed to search items")
