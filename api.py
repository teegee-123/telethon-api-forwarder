import os
import asyncio
import time 
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from telethon.sync import TelegramClient, events
from forwarder import TelegramManager
from sheets import Sheets
import re
load_dotenv()
code_file = os.environ.get("CODE_FILE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")


app = FastAPI()

for filename in os.listdir():
     if re.findall('session', filename):
          os.remove(filename)
          print(f"REMOVED {filename}")
time.sleep(5)

client = TelegramClient(session, api_id, api_hash)
manager = TelegramManager(client)
#from starlette.background import BackgroundTasks

# @app.on_event("startup")
# async def on_startup():
#     asyncio.run(manager.run())

@app.get("/code")
def set_code_with_slash(code: str):
     print(code_file)
     with open(code_file, 'w') as file:
          print(code)
          file.write(code)          
     code = manager.getCodeFromFile()
     open(code_file, 'w').close()
     return code


@app.get('/')
def auth_sheets():
     asyncio.run(manager.sheets.auth())
     return "Sheets authed"

@app.get('/status')
def status():
     if(manager.client.is_connected()):
          return "Connected"
     return "Not Connected"

@app.get("/start")
def run(request: Request):
     manager.base_url = request.base_url
     print(f"BASEURL {manager.base_url}")
     if(manager.client.is_connected()):
          return "already connected"
     
     asyncio.run(manager.run())
     return "Started"




@app.get("/ping")
def run():
     return "PING!"

@app.get("/stop")
async def stop():     
     await client.disconnect()
     asyncio.get_running_loop().stop()
     return asyncio.all_tasks(asyncio.get_running_loop()).__str__()
     #return "Stopped"

@app.get("/send")
async def send(): {
     await manager.interactor.send_command('hi')
}