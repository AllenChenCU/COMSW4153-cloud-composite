# COMSW4153-cloud-composite-service

Author: Allen Chen (atc2160)

Team Name: cloudGPT

The Composite Service repo for the accessible routes application

API deployed on GCP Compute Engine

## Data

Database deployed on GCP Cloud SQL
- Host: 104.155.191.78
- user: root
- password: please request
- port: 3306
- dbname: composite_database

Tables:
1. saved_route table: saved routes by the users
2. email_notification table: email to be sent to the users to notify them for any equipment status changes.

## API Usage

API Endpoint: http://34.55.117.204:5001/

### 1. Query routes and stations

Description: Given source and destination as query parameter, this endpoint calls the internal Google Map service API and MTA service API to return the routes and all status information of equipments of the corresponding stations in returned routes. response["routes"] and response["stations"] have an one-to-one mapping relationship. 

Example: http://34.55.117.204:5001/query-routes-and-stations/?source=Columbia%20University&destination=John%20F.%20Kennedy%20International%20Airport

### 2. Save route

Description: Given a request body of SavedRoute model, this endpoint generates a route_id and attaches it with the saved route and creates a record in the saved_route table. A notification record is also asynchronously saved into the email_notification table (An email or notification should be sent to the user). 

Example: 
```
curl -X POST "http://34.55.117.204:5001/save-route/" -H "Content-Type: application/json" -d @app/example_route.json
```

See app/example_route.json for an example of the request body. 

### 3. Unsave route

Description: Given an existing route_id, this endpoint updates / deletes the saved route associated with the route_id in the saved_route table and the notification record in the email notification table. This is done synchronously.

Example: 
```
curl -X PUT "http://34.55.117.204:5001/unsave-route/?route_id=360810dd-312c-474d-9fba-e94cb1d53662"
```

### 4. Get all SAVED routes and stations for the user

Description: Given a user_id, the endpoint queries the saved_route table to return all saved routes and station equipments info from all saved routes. 

Example: http://34.55.117.204:5001/get-saved-routes-and-stations/?user_id=user123

OR 
```
curl -X GET "http://34.55.117.204:5001/get-saved-routes-and-stations/?user_id=user123"
```

### 5. Get all QUERIED routes and stations for the user

TODO
- Implement this endpoint
- Need to modify the google service API to take in a user_id param
- Endpoint query-routes-and-stations needs to take in a user_id param

Description: Given a user_id, this endpoint calls the google maps service API which in turns queries its database to return all queries made by the user. 

Example: http://34.55.117.204:5001/query-all-routes-and-stations-by-user/?user_id=user123
