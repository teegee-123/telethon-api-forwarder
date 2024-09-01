import os
from fastapi import FastAPI
from dotenv import load_dotenv
from forwarder import main, getCodeFromFile
import asyncio 
load_dotenv()
code_file = os.environ.get("CODE_FILE")

app = FastAPI()


@app.get("/code/{code}")
def set_code(code: int):
     print(code_file)
     f = open(code_file, "w")
     f.write(str(code))
     f.close()
     return getCodeFromFile(0)

@app.get("/run")
def run():
     asyncio.run(main())


@app.get("/ping")
def run():
     return "PING!"

