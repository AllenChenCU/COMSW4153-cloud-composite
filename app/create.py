"""Create tables for the composite service"""
import os

import pymysql
import structlog


logger = structlog.getLogger(__name__)


CREATE_EMAIL_NOTIFICATION_TABLE_QUERY = """
    create table if not exists email_notification (
        notification_id text null,
        user_id text null,
        route_id text null
    );
"""


CREATE_SAVED_ROUTE_TABLE_QUERY = """
    create table if not exists saved_route (
        route_id text not null,
        source text not null,
        destination text not null,
        user_id text not null,
        query_id text not null,
        route json not null
    );
"""


if __name__ == "__main__":
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

        ## --- saved_route table ---
        # delete table
        cursor.execute("""DROP TABLE saved_route;""")
        conn.commit()

        # create table
        cursor.execute(CREATE_SAVED_ROUTE_TABLE_QUERY)
        conn.commit()
        logger.info("Created saved_route table.")
        ## ------------------------

        ## --- email_notification table ---
        # delete table
        cursor.execute("""DROP TABLE email_notification;""")
        conn.commit()

        # create table
        cursor.execute(CREATE_EMAIL_NOTIFICATION_TABLE_QUERY)
        conn.commit()
        logger.info("Created email_notification table.")
        ## ------------------------

    except pymysql.Error as e:
        conn.rollback()
        logger.info(f"An error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection is closed.")
