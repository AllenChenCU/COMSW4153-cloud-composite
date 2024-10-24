"""Flask App for the composite service"""
from typing import Union

import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from models import SavedRoute

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"])


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/query-routes-and-stations/")
async def query_routes_and_stations(source: str, destination: str):
    """Query google maps API and MTA API and return both info
    remember to add await when querying APIs
    """
    pass


@app.post("/save-route/")
def save_route(saved_route: SavedRoute):
    """Create SavedRoute record to 
    the saved_route table and the email notification table
    """
    pass


@app.put("/unsave-route/")
def unsave_route(saved_route: SavedRoute):
    """Delete SavedRoute record 
    from the saved_route table and the email notification table
    """
    pass


@app.get("/get-saved-routes-and-stations/")
async def get_saved_routes_and_stations(user_id: str):
    """Get all saved routes saved by the users previously
    1. Query the database to get saved routes for the user
    2. Retrieve stations from the saved routes and get status of stations
    remember to add await when querying database
    """
    pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
