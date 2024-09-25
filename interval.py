from threading import Timer
from telethon.sync import TelegramClient
import asyncio;
from interactor import MaestroInteractor
from sheets import Sheets


class IntervalHandler:
    def __init__(self, client: TelegramClient, sheets: Sheets):
        print("init interval")
        self.sheets = sheets
        self.client = client
        self.task = None
        self.running = True
        scraper_data = self.sheets.read_scraper_data()
        self.command = scraper_data[0]
        self.interval = scraper_data[1]
        self.add_interval()
        
    def add_interval(self):
        print("add interval")
        scraper_data = self.sheets.read_scraper_data()
        self.command = scraper_data[0]
        self.interval = scraper_data[1]

        if(self.task is not None):
            self.task.cancel()
        self.task = asyncio.create_task(self.auto_send())


    async def auto_send(self):
        while self.running:
            await self.client.send_message('Pfscrapedevbot', f'/{self.command}')
            await self.client.send_message('MaestroSniperBot', f'/monitor')
            await asyncio.sleep(self.interval)
    
    def __del__(self):
        print("delete interval")
        if(self.task is not None):
            self.task.cancel()
        self.running = False
    