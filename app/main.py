"""Flask App for the composite service"""
from typing import Union
import requests
import json
import uuid
import os

import uvicorn
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog
import pandas as pd
from jose import jwt, JWTError

from models import SavedRoute
from utils import (
    request_to_google_maps_service, 
    get_stations_from_routes, 
    request_to_mta_service, 
    insert_into_table, 
    INSERT_SAVED_ROUTE_QUERY, 
    INSERT_SAVED_ROUTE_COL_ORDER, 
    INSERT_EMAIL_NOTIFICATION_QUERY, 
    delete_in_table, 
    DELETE_SAVED_ROUTE_QUERY, 
    DELETE_EMAIL_NOTIFICATION_QUERY, 
    GET_SAVED_ROUTE_QUERY, 
    query_table, 
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_headers=["*"], 
    allow_methods=["*"],
)
logger = structlog.getLogger(__name__)


@app.middleware("http")
async def log(request: Request, call_next):
    # before
    logger.info(f"Request: {request.method} {request.url}")

    # call the main request handler
    response = await call_next(request)

    # after
    logger.info(f"Response status: {response.status_code}")

    return response


# JWT secret and algorithm
SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"


# Middleware for JWT Validation
@app.middleware("http")
async def jwt_validation_middleware(request: Request, call_next):
    # Allow public routes without JWT validation
    public_routes = [
        "/", 
        "/query-routes-and-stations/", 
        "/query-all-routes-by-user/", 
        "/save-route/", 
        "/unsave-route/", 
        "/get-saved-routes-and-stations/", 
    ]  # Add more public routes if needed
    if request.url.path in public_routes:
        return await call_next(request)

    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    # Extract and decode JWT token
    token = auth_header.split("Bearer ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Optional: Store user information for downstream use
        request.state.user = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid JWT token")

    # Call the next middleware or route
    return await call_next(request)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/query-routes-and-stations/")
async def query_routes_and_stations(source: str, destination: str, user_id: str):
    """Query Google Map Service and MTA Service 
    and return a list of routes and a list of stations associated with the route
    for each route. 
    """
    routes = await request_to_google_maps_service(source, destination, user_id, mode="transit")
    all_stations, all_transit_types = await get_stations_from_routes(routes["routes"])
    all_mta_info = await request_to_mta_service(all_stations, all_transit_types)
    results = {
        "routes": routes["routes"], 
        "stations": all_mta_info, 
        "links": routes["_links"], 
        # "query_id": routes["query_id"] ???
    }
    results_json = json.dumps(results)
    return Response(results_json, media_type="application/json")


@app.get("/query-all-routes-by-user/")
async def query_all_routes_by_user(user_id: str, limit: int=10, page: int=1):
    """Retrieve all queries made by the user from the Google Map Service. 
    (with Pagination)
    """
    api_endpoint = "http://18.118.121.175"
    api_endpoint_template = f"{api_endpoint}:5000/viewed_routes/page/{page}?limit={limit}&user_id={user_id}"
    response = requests.get(api_endpoint_template)
    results_json = json.dumps(response.json())
    return Response(results_json, media_type="application/json")


@app.post("/save-route/")
async def save_route(saved_route: SavedRoute):
    """Create SavedRoute record to 
    the saved_route table and the email notification table. (With HATEOAS and support links)

    Example request body: see app/example_route.json for full example
        '{
            "source": "Columbia University", 
            "destination": "John F. Kennedy International Airport", 
            "user_id": "user123", 
            "query_id": "query123", 
            "to_email": null,
            "route": {
                "bounds": {
                    "northeast": {
                    "lat": 40.808134,
                    "lng": -73.7893588
                    },
                },
                "legs": [{"start_address": "116th and Broadway, New York, NY 10027, USA"}]
            }, 
            ...
        }'
    """
    # generate route_id
    route_id = str(uuid.uuid4())

    # insert into saved_route table
    saved_route_dict = saved_route.dict()
    saved_route_dict["route_id"] = route_id
    saved_route_dict["route"] = json.dumps(saved_route_dict["route"])
    saved_route_data = [tuple([saved_route_dict[key] for key in INSERT_SAVED_ROUTE_COL_ORDER])]
    await insert_into_table(INSERT_SAVED_ROUTE_QUERY, saved_route_data)

    # insert into email_notification table
    notification_id = str(uuid.uuid4())
    email_notification_data = [(
        notification_id, 
        saved_route_dict["user_id"], 
        route_id, 
    )]
    await insert_into_table(INSERT_EMAIL_NOTIFICATION_QUERY, email_notification_data)

    # send email to user
    if saved_route_dict["to_email"] != "":
        try:
            FaaS_url = "https://us-central1-norse-bond-439820-h5.cloudfunctions.net/function-send-email"
            payload = {
                "to_email": saved_route_dict["to_email"], 
                "subject": "Route Saved", 
                "message": f"Route with route_id {route_id} from source {saved_route_dict["source"]} to destination {saved_route_dict["destination"]} is saved successfully!"
            }
            headers = {"Content-Type": "application/json"}
            email_response = requests.post(FaaS_url, json=payload, headers=headers).text
            logger.info(email_response)
        except Exception as e:
            logger.info(f"Error: {e}")
    else:
        email_response = "No user email is provided."

    results_json = json.dumps(
        {
            "message": "Route is successfully saved!", 
            "route_id": route_id, 
            "user_id": saved_route_dict["user_id"], 
            "query_id": saved_route_dict["query_id"], 
            "source": saved_route_dict["source"], 
            "destination": saved_route_dict["destination"], 
            "email_response": email_response,
            "links": {
                "self": {
                    "href": "/save-route/", 
                    "method": "POST"
                }, 
                "get": {
                    "href": f"/get-saved-routes-and-stations/?user_id={saved_route_dict["user_id"]}", 
                    "method": "GET"
                }, 
                "update": {
                    "href": f"/unsave-route/?route_id={route_id}", 
                    "method": "PUT"
                }
            }
        }
    )
    return Response(results_json, media_type="application/json")


@app.put("/unsave-route/")
def unsave_route(route_id: str):
    """Delete SavedRoute record 
    from the saved_route table and the email notification table.
    """

    # delete in saved_route table
    delete_in_table(DELETE_SAVED_ROUTE_QUERY, route_id)

    # delete in email notification table
    delete_in_table(DELETE_EMAIL_NOTIFICATION_QUERY, route_id)

    results_json = json.dumps(
        {
            "message": "Route is successfully deleted!", 
            "route_id": route_id, 
        }
    )
    return Response(results_json, media_type="application/json")


@app.get("/get-saved-routes-and-stations/")
async def get_saved_routes_and_stations(user_id: str):
    """Get all saved routes and stations saved by the users previously
    1. Query the database to get saved routes for the user
    2. Retrieve stations from the saved routes and get status of stations
    The returned list of saved_routes and the list of list of station_from_saved_routes
    have a one-to-one mapping relationship.
    """
    saved_routes_info = await query_table(GET_SAVED_ROUTE_QUERY, user_id)
    for saved_routes_info_i in saved_routes_info:
        saved_routes_info_i["route"] = json.loads(saved_routes_info_i["route"])
    saved_routes_only = [d["route"] for d in saved_routes_info]
    saved_routes_stations, saved_routes_transit_types = await get_stations_from_routes(saved_routes_only)
    saved_routes_mta_info = await request_to_mta_service(saved_routes_stations, saved_routes_transit_types)
    results = {
        "saved_routes": saved_routes_info, 
        "stations_from_saved_routes": saved_routes_mta_info, 
    }
    results_json = json.dumps(results)
    return Response(results_json, media_type="application/json")


## ------------ Protected route ------------
@app.get("/protected-query-routes-and-stations/")
async def protected_query_routes_and_stations(source: str, destination: str, user_id: str):
    """Query Google Map Service and MTA Service 
    and return a list of routes and a list of stations associated with the route
    for each route. 
    """
    routes = await request_to_google_maps_service(source, destination, user_id, mode="transit")
    all_stations, all_transit_types = await get_stations_from_routes(routes["routes"])
    all_mta_info = await request_to_mta_service(all_stations, all_transit_types)
    results = {
        "routes": routes["routes"], 
        "stations": all_mta_info, 
        "links": routes["_links"], 
        # "query_id": routes["query_id"] ???
    }
    results_json = json.dumps(results)
    return Response(results_json, media_type="application/json")


@app.get("/protected-query-all-routes-by-user/")
async def protected_query_all_routes_by_user(user_id: str, limit: int=10, page: int=1):
    """Retrieve all queries made by the user from the Google Map Service. 
    (with Pagination)
    """
    api_endpoint = "http://18.118.121.175"
    api_endpoint_template = f"{api_endpoint}:5000/viewed_routes/page/{page}?limit={limit}&user_id={user_id}"
    response = requests.get(api_endpoint_template)
    results_json = json.dumps(response.json())
    return Response(results_json, media_type="application/json")


@app.post("/protected-save-route/")
async def protected_save_route(saved_route: SavedRoute):
    """Create SavedRoute record to 
    the saved_route table and the email notification table. (With HATEOAS and support links)

    Example request body: see app/example_route.json for full example
        '{
            "source": "Columbia University", 
            "destination": "John F. Kennedy International Airport", 
            "user_id": "user123", 
            "query_id": "query123", 
            "to_email": null,
            "route": {
                "bounds": {
                    "northeast": {
                    "lat": 40.808134,
                    "lng": -73.7893588
                    },
                },
                "legs": [{"start_address": "116th and Broadway, New York, NY 10027, USA"}]
            }, 
            ...
        }'
    """
    # generate route_id
    route_id = str(uuid.uuid4())

    # insert into saved_route table
    saved_route_dict = saved_route.dict()
    saved_route_dict["route_id"] = route_id
    saved_route_dict["route"] = json.dumps(saved_route_dict["route"])
    saved_route_data = [tuple([saved_route_dict[key] for key in INSERT_SAVED_ROUTE_COL_ORDER])]
    await insert_into_table(INSERT_SAVED_ROUTE_QUERY, saved_route_data)

    # insert into email_notification table
    notification_id = str(uuid.uuid4())
    email_notification_data = [(
        notification_id, 
        saved_route_dict["user_id"], 
        route_id, 
    )]
    await insert_into_table(INSERT_EMAIL_NOTIFICATION_QUERY, email_notification_data)

    # send email to user
    if saved_route_dict["to_email"] != "":
        try:
            FaaS_url = "https://us-central1-norse-bond-439820-h5.cloudfunctions.net/function-send-email"
            payload = {
                "to_email": saved_route_dict["to_email"], 
                "subject": "Route Saved", 
                "message": f"Route with route_id {route_id} from source {saved_route_dict["source"]} to destination {saved_route_dict["destination"]} is saved successfully!"
            }
            headers = {"Content-Type": "application/json"}
            email_response = requests.post(FaaS_url, json=payload, headers=headers).text
            logger.info(email_response)
        except Exception as e:
            logger.info(f"Error: {e}")
    else:
        email_response = "No user email is provided."

    results_json = json.dumps(
        {
            "message": "Route is successfully saved!", 
            "route_id": route_id, 
            "user_id": saved_route_dict["user_id"], 
            "query_id": saved_route_dict["query_id"], 
            "source": saved_route_dict["source"], 
            "destination": saved_route_dict["destination"], 
            "email_response": email_response,
            "links": {
                "self": {
                    "href": "/save-route/", 
                    "method": "POST"
                }, 
                "get": {
                    "href": f"/get-saved-routes-and-stations/?user_id={saved_route_dict["user_id"]}", 
                    "method": "GET"
                }, 
                "update": {
                    "href": f"/unsave-route/?route_id={route_id}", 
                    "method": "PUT"
                }
            }
        }
    )
    return Response(results_json, media_type="application/json")


@app.put("/protected-unsave-route/")
def protected_unsave_route(route_id: str):
    """Delete SavedRoute record 
    from the saved_route table and the email notification table.
    """

    # delete in saved_route table
    delete_in_table(DELETE_SAVED_ROUTE_QUERY, route_id)

    # delete in email notification table
    delete_in_table(DELETE_EMAIL_NOTIFICATION_QUERY, route_id)

    results_json = json.dumps(
        {
            "message": "Route is successfully deleted!", 
            "route_id": route_id, 
        }
    )
    return Response(results_json, media_type="application/json")


@app.get("/protected-get-saved-routes-and-stations/")
async def protected_get_saved_routes_and_stations(user_id: str):
    """Get all saved routes and stations saved by the users previously
    1. Query the database to get saved routes for the user
    2. Retrieve stations from the saved routes and get status of stations
    The returned list of saved_routes and the list of list of station_from_saved_routes
    have a one-to-one mapping relationship.
    """
    saved_routes_info = await query_table(GET_SAVED_ROUTE_QUERY, user_id)
    for saved_routes_info_i in saved_routes_info:
        saved_routes_info_i["route"] = json.loads(saved_routes_info_i["route"])
    saved_routes_only = [d["route"] for d in saved_routes_info]
    saved_routes_stations, saved_routes_transit_types = await get_stations_from_routes(saved_routes_only)
    saved_routes_mta_info = await request_to_mta_service(saved_routes_stations, saved_routes_transit_types)
    results = {
        "saved_routes": saved_routes_info, 
        "stations_from_saved_routes": saved_routes_mta_info, 
    }
    results_json = json.dumps(results)
    return Response(results_json, media_type="application/json")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
