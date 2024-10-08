import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
from dotenv import load_dotenv, dotenv_values 
import asyncio 

load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.


class Sheets:
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    feeds_range = "feeds!A:C"
    reports_range = "reports!A:C"
    interactor_range = "interactor!A:A"
    scraper_range = "scraper!A:B"
    simple_range = "simple!A:C"
    creds = None
    # def __init__(self): 
    #     asyncio.run( self.auth())

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.auth())

    def read_feeds(self):
        feed_data = self.get_sheet_data(self.feeds_range, self.creds)
        feeds = feed_data[1:]
        print("read feeds sheet")
        mapped_feeds = []
        for feed in feeds:
            if(not feed[0] or not feed[1] or not feed[2]):
                print(f'cannot parse feed {feed}')                
            mapped_feed = { "id": int(feed[0]), "name": feed[1], "users": json.loads(feed[2]) }
            mapped_feeds.append(mapped_feed)
        print(str(mapped_feeds))
        return mapped_feeds

    def read_reports(self):
        report_data = self.get_sheet_data(self.reports_range, self.creds)
        
        reports = report_data[1:]
        print("read reports sheet")            
        mapped_reports = []
        for report in reports:
            if(not report[0] or not report[1] or not report[2]):
                print(f'cannot parse report {report}')

            report_feeds = json.loads(report[2])
            mapped_report_feeds = list(map(lambda r: {"name": r},report_feeds))
            mapped_report = { "name": report[0], "users": json.loads(report[1]), "feeds": mapped_report_feeds }
            mapped_reports.append(mapped_report)
        print(str(mapped_reports))
        return mapped_reports

    def read_simple_feeds(self):
        print("read simple feeds")
        source_to_destination_map = []
        simple_data = self.get_sheet_data(self.simple_range, self.creds)

        data = simple_data[1:]
        for item in data:
            source = item[0]
            destination = item[1]
            filter = str(item[2]) or ''
            print(f"filter {filter}")
            source_to_destination_map.append({"source": int(source), "destination": int(destination), "filter": filter})
        return source_to_destination_map

    def read_interactor_stop_loss(self):
        print("read interactor sheet")            
        report_data = self.get_sheet_data(self.interactor_range, self.creds)        
        stoplossData = report_data[1:][0][0]
        print(f"new stop loss {stoplossData}")
        return int(stoplossData)

    def read_scraper_data(self):
        print("read scraper sheet")
        sheet_data = self.get_sheet_data(self.scraper_range, self.creds)        
        scraper_command = sheet_data[1:][0][0]
        scraper_interval = int(sheet_data[1:][0][1])
        print(f'scraper_command {scraper_command}')        
        print(f"scraper_interval {scraper_interval}")
        return [scraper_command, scraper_interval]


    def get_sheet_data(self, range, creds):
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        return (sheet.values()
                .get(spreadsheetId=self.spreadsheet_id, range=range)
                .execute()).get("values", [])

            
    async def getCodeFromFile(self): 
        code = ''
        while(code == ''):
            with open(os.environ.get("CODE_FILE"), "r", encoding="utf-8") as myfile:
                code = myfile.read()
                
        print(code)
        return code

    async def auth(self): 
        try:
            token_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")#.replace('./', '')

            print(f"AUTHING SHEETS {token_file}")
            if os.path.exists(token_file):
                with open(token_file, "r", encoding="utf-8") as myfile:
                    token = myfile.read()
                if(token != "" and token != '{}'):
                    print("token not empty")
                    self.creds = Credentials.from_authorized_user_file(token_file, SCOPES)            
                    print(self.creds.to_json())
                    print(self.creds.valid)
            else:
                print("token empty")
            # If there are no (valid) credentials available, let the user log in.
            if not self.creds:
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
                    #self.creds = flow.run_console()
                    flow.redirect_uri = flow._OOB_REDIRECT_URI
                    auth_url, _ = flow.authorization_url()
                    print(auth_url)
                    code = await self.getCodeFromFile()
                    print(f"sheets code: {code}")
                    flow.fetch_token(code=code)
                    with open(token_file, "w") as token:
                        print(f'token written {flow.credentials.to_json()}')
                        self.creds = flow.credentials
                        token.write(flow.credentials.to_json())
        except:
            print("Could not auth sheets")
                

# s = Sheets()
# s.read()