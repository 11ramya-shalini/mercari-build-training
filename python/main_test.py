from fastapi.testclient import TestClient
from main import app, get_db, add_item
import pytest
import sqlite3
import os
import pathlib
from fastapi import Form, HTTPException, UploadFile, File, Depends
import io

# STEP 6-4: uncomment this test setup
test_db = pathlib.Path(__file__).parent.resolve() / "db" / "test_mercari.sqlite3"

def override_get_db():
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

 
app.dependency_overrides[get_db] = override_get_db

# A mock version of the add_item function that does not require an actual file upload
async def mock_add_item(
    name: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(None),  # Make image optional during testing
    db: sqlite3.Connection = Depends(get_db),
):
    if not name or not category:
        raise HTTPException(status_code=400, detail="name and category are required")

    # Use a dummy image if no image is provided (for testing)
    hashed_image = "dummy_image.jpg" if not image else hash_image(image)

    insert_item_by_db(Item(name=name, category=category, image=hashed_image), db)
    return AddItemResponse(message=f"Item received: {name}, {category}, {hashed_image}")

app.dependency_overrides[add_item] = mock_add_item  

@pytest.fixture(autouse=True)
def db_connection():
     # Before the test is done, create a test database
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS items (
 		id INTEGER PRIMARY KEY AUTOINCREMENT,
 		name VARCHAR(255),
 		category VARCHAR(255)
 	)"""
    )
    conn.commit()
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    yield conn

    conn.close()
    # After the test is done, remove the test database
    if test_db.exists():
        test_db.unlink() # Remove the file

client = TestClient(app)


@pytest.mark.parametrize(
    "want_status_code, want_body",
    [
        (200, {"message": "Hello, world!"}),
    ],
)
def test_hello(want_status_code, want_body):
    response_body = client.get("/").json()
    response_status_code = client.get("/").status_code
    # STEP 6-2: confirm the status code
    assert response_status_code == want_status_code,f"unexpected result of test_hello: want={want_status_code},got={response_status_code}"
    # STEP 6-2: confirm response body
    assert response_body == want_body, f"unexpected result of test_hello: want={want_body}, got={response_body}"


#STEP 6-4: uncomment this test
@pytest.mark.parametrize(
    "args, want_status_code",
    [
        ({"name":"used iPhone 16e", "category":"phone"}, 200),
        ({"name":"", "category":"phone"}, 400),
    ],
)
def test_add_item_e2e(args,want_status_code,db_connection):
    image_file = io.BytesIO(b"fake image content")
    image_file.name = "fake_image.jpg"

    response = client.post(
        "/items/",
        data={
            "name": args["name"],
            "category": args["category"],
        },
        files={"image": ("fake_image.jpg", image_file, "image/jpeg")},
    )
    #response = client.post("/items/", data=args)
    assert response.status_code == want_status_code
    
    if want_status_code >= 400:
        return
    
    
    # Check if the response body is correct
    response_data = response.json()
    assert "message" in response_data,f"unexpected result of est_add_item_e2e:want=the string of [message],got={response_data}"

    # Check if the data was saved to the database correctly
    cursor = db_connection.cursor()
    cursor.execute("SELECT * FROM items WHERE name = ?", (args["name"],))
    db_item = cursor.fetchone()
    assert db_item is not None,"unexpected result of est_add_item_e2e:nothing saved to the database"
    assert dict(db_item)["name"] == args["name"],f"unexpected result of est_add_item_e2e:do not saved to the database {name}"
