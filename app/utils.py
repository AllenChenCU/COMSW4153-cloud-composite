import os
import requests
import json
from typing import Any, List

import pymysql
import structlog
import pandas as pd

logger = structlog.getLogger(__name__)


INSERT_SAVED_ROUTE_QUERY = """
    INSERT INTO saved_route (
        route_id, 
        source, 
        destination, 
        user_id, 
        query_id, 
        route
    ) VALUES (
        %s, %s, %s, %s, %s, %s
    );
"""


INSERT_SAVED_ROUTE_COL_ORDER = [
    "route_id", 
    "source", 
    "destination", 
    "user_id", 
    "query_id", 
    "route", 
]


INSERT_EMAIL_NOTIFICATION_QUERY = """
    INSERT INTO email_notification (
        notification_id, 
        user_id, 
        route_id
    ) VALUES (
        %s, %s, %s
    );
"""


DELETE_SAVED_ROUTE_QUERY = """
    DELETE FROM saved_route
    WHERE route_id = %s;
"""


DELETE_EMAIL_NOTIFICATION_QUERY = """
    DELETE FROM email_notification
    WHERE route_id = %s;
"""


GET_SAVED_ROUTE_QUERY = """
    SELECT * FROM saved_route
    WHERE user_id = %s;
"""


async def query_table(query, id):
    """Run read query corresponding to the id"""
    try:
        config = {
            "host": os.environ["DBHOST"],
            "user": os.environ["DBUSER"],
            "password": os.environ["DBPASSWORD"],
            "port": int(os.environ["DBPORT"]),
            "db": os.environ["DBNAME"],
            "cursorclass": pymysql.cursors.DictCursor,
        }
        conn = pymysql.connect(**config)
        logger.info("Connected to database.")

        cursor = conn.cursor()
        cursor.execute(query, (id, ))
        results = cursor.fetchall()

        return results

    except pymysql.Error as e:
        conn.rollback()
        logger.info(f"An error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection is closed.")


def delete_in_table(query: str, id: str):
    """delete record(s) corresponding to the id using the query"""
    try:
        config = {
            "host": os.environ["DBHOST"],
            "user": os.environ["DBUSER"],
            "password": os.environ["DBPASSWORD"],
            "port": int(os.environ["DBPORT"]),
            "db": os.environ["DBNAME"],
        }
        conn = pymysql.connect(**config)
        logger.info("Connected to database.")

        cursor = conn.cursor()
        cursor.execute(query, (id, ))
        conn.commit()
        logger.info("Inserted data into database.")

    except pymysql.Error as e:
        conn.rollback()
        logger.info(f"An error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection is closed.")


async def insert_into_table(query: str, data: List[Any]) -> None:
    """Insert data into the database using the query"""
    try:
        config = {
            "host": os.environ["DBHOST"],
            "user": os.environ["DBUSER"],
            "password": os.environ["DBPASSWORD"],
            "port": int(os.environ["DBPORT"]),
            "db": os.environ["DBNAME"],
        }
        conn = pymysql.connect(**config)
        logger.info("Connected to database.")

        cursor = conn.cursor()
        cursor.executemany(query, data)
        conn.commit()
        logger.info("Inserted data into database.")

    except pymysql.Error as e:
        conn.rollback()
        logger.info(f"An error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection is closed.")


async def request_to_google_maps_service(origin, dest, mode="transit"):
    """Request from Google Map API service given origin and dest"""
    query_origin = origin.replace(" ", "+")
    query_dest = dest.replace(" ", "+")
    api_endpoint_template = f"http://3.133.129.121:5000/routes?origin={query_origin}&destination={query_dest}&mode={mode}"
    response = requests.get(api_endpoint_template)
    return response.json()


async def get_stations_from_routes(routes):
    """Return a list of stations for every step of routes"""
    all_stations = []
    all_transit_types = []

    for route in routes:
        stations = []
        transit_types = []
        for step in route["legs"][0]["steps"]:
            if step["travel_mode"] == "TRANSIT":
                stations.append(step["transit_details"]["departure_stop"]["name"])
                stations.append(step["transit_details"]["arrival_stop"]["name"])
                transit_types.extend([step["transit_details"]["line"]["vehicle"]["type"]]*2)
        all_stations.append(stations)
        all_transit_types.append(transit_types)
    return all_stations, all_transit_types


async def request_to_mta_service(all_stations, all_transit_types):
    """Request from MTA service API to get station equipments status
    Return equipments info for all routes
    """
    all_info = []
    # loop through stations in a particular route
    for stations, transit_types in zip(all_stations, all_transit_types):
        info = {}
        for station, transit_type in zip(stations, transit_types):
            if station not in info and transit_type == "SUBWAY":
                query_station = station.replace(" ", "%20")
                mta_endpoint = f"http://3.84.62.68:5001/equipments/{query_station}"
                equipments_info = requests.get(mta_endpoint)
                info[station] = equipments_info.json()
        all_info.append(info)
    return all_info


if __name__ == "__main__":
    # sanity test
    #input_origin = "116th and Broadway, New York, NY"
    #input_destination = "200 Central Park W, New York, NY"
    # input_origin = "Columbia University"
    # input_destination = "John F. Kennedy International Airport"
    # routes = request_to_google_maps_service(input_origin, input_destination, mode="transit")
    # all_stations, all_transit_types = get_stations_from_routes(routes["routes"])
    # all_info = request_to_mta_service(all_stations, all_transit_types)
    # print(all_stations)
    # print(all_transit_types)
    # print(all_info)
    
    route_json = json.dumps(
        {
            "bounds": {
                "northeast": {
                "lat": 40.808134,
                "lng": -73.7893588
                },
            },
            "legs": [{"start_address": "116th and Broadway, New York, NY 10027, USA"}]
        }, 
    )
    example_data = [(
        "route123", 
        "Columbia University", 
        "John F. Kennedy International Airport", 
        "user123", 
        "query123", 
        route_json
    )]
    delete_in_table(INSERT_SAVED_ROUTE_QUERY, example_data)
