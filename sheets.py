import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
from dotenv import load_dotenv, dotenv_values 

load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.


class Sheets:
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    feeds_range = "feeds!A:C"
    reports_range = "reports!A:C"
    creds = None
    def __init__(self): 
        self.auth()

    def read_feeds(self):
        feed_data = self.get_sheet_data(self.feeds_range, self.creds)
        feeds = feed_data[1:]
        print("feeds")
        mapped_feeds = []
        for feed in feeds:
            mapped_feed = { "id": feed[0], "name": feed[1], "users": json.loads(feed[2]) }
            mapped_feeds.append(mapped_feed)
        
        return mapped_feeds

    def read_reports(self):
        report_data = self.get_sheet_data(self.reports_range, self.creds)
        
        reports = report_data[1:]
        print("reports")            
        mapped_reports = []
        for report in reports:
            report_feeds = json.loads(report[2])
            mapped_report_feeds = list(map(lambda r: {"name": r},report_feeds))
            mapped_report = { "name": report[0], "users": json.loads(report[1]), "feeds": mapped_report_feeds }
            mapped_reports.append(mapped_report)
        
        return mapped_reports
        
    def get_sheet_data(self, range, creds):
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        return (sheet.values()
                .get(spreadsheetId=self.spreadsheet_id, range=range)
                .execute()).get("values", [])

    def auth(self):        
        if os.path.exists("token.json"):
            self.creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:                
                config = {
                        "installed": {
                            "client_id": os.environ.get("CLIENT_ID"),
                            "project_id": os.environ.get("PROJECT_NAME"),
                            "client_secret": os.environ.get("CLIENT_SECRET"),
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            #TODO REMOVE
                            # "redirect_uris": [
                            #     "http://localhost"
                            # ]
                        }
                    }
                flow = InstalledAppFlow.from_client_config(client_config=config , scopes=SCOPES)

            self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(self.creds.to_json())

s = Sheets()
s.read()