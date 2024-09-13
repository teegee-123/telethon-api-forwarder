import os
import asyncio 
from fastapi import FastAPI
from dotenv import load_dotenv
from telethon.sync import TelegramClient, events
from forwarder import TelegramManager
from sheets import Sheets
load_dotenv()
code_file = os.environ.get("CODE_FILE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")


app = FastAPI()
client = TelegramClient(session, api_id, api_hash)
manager = TelegramManager(client)

# from starlette.background import BackgroundTasks

# @app.on_event("startup")
# def startup_event():
#      asyncio.run(main(client))

@app.get("/code/{code}")
def set_code(code: int):
     print(code_file)
     f = open(code_file, "w")
     f.write(str(code))
     f.close()
     return manager.getCodeFromFile(clear=False)

@app.get("/code")
def set_code_with_slash(code: str):
     print(code_file)
     f = open(code_file, "w")
     f.write(str(code))
     f.close()
     return manager.getCodeFromFile(clear=False)


@app.get("/run")
def run():
     asyncio.run(manager.run())     
     return "Started"


@app.get("/ping")
def run():
     return "PING!"

@app.get("/auth")
def auth_sheets():
     manager.sheets = Sheets()

@app.get("/stop")
async def run():     
     await client.disconnect()
     return "Stopped"

