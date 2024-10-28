from typing import Any, List, Dict

from pydantic import BaseModel, Json


# model for SavedRoute record
class SavedRoute(BaseModel):
    # route_id: str # created at composite unless it's created at google map service
    source: str
    destination: str
    user_id: str
    query_id: str
    route: Dict[str, Any] # take JSON data as well
    

# model for EmailNotification.
# the purpose is to log a record once an email/notification is sent. 
# An initial email will be sent once a user saves a route 
# Later if any stations related to the saved route have changes, another notification may also be sent
class EmailNotification(BaseModel):
    notification_id: str
    user_id: str
    route_id: str
