import os
import json
import datetime
import itertools
from telethon.sync import TelegramClient, events
from dotenv import load_dotenv, dotenv_values 
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
import time
import re
from telethon.tl.types import Message
from interactor import MaestroInteractor
from sheets import Sheets
import threading


load_dotenv()

phone = os.environ.get("PHONE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")
code_file = os.environ.get("CODE_FILE")
trade_bot = os.environ.get("TRADEBOTNAME")
buy_signals_group = json.loads(os.environ.get("BUYSIGNALSGROUP"))
report_group_name = os.environ.get("REPORT_GROUP_NAME")

token_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")#.replace('./', '')




class TelegramManager:
   client: TelegramClient
   sheets: Sheets
   feeds = []
   report_groups = []
   def __init__(self, client: TelegramClient):
      self.client = client
      self.sheets = None
   def get_group_users_to_add(self, group_name: str, groups):
      return list(filter(lambda x: x["name"]==group_name ,groups))[0]["users"]

   def getSenderIdFromMessage(self, message: Message):
      if(hasattr(message.peer_id, 'channel_id')):            
         return message.peer_id.channel_id 
      if(hasattr(message.peer_id, 'user_id')):
         return message.peer_id.user_id 
      if(hasattr(message.peer_id, 'chat_id')):
         return message.peer_id.chat_id

   def format_id(self, id: int):
      id = abs(id)
      if(str(id).startswith("100")):
         id = str(id)[3:]
      return int(id)

   async def find_group_by_name(self, group_name: str):   
      print(f'looking for {group_name}')   
      async for dialog in self.client.iter_dialogs():
         if(dialog.title is not None and dialog.title == group_name):
            print(f'Found Group {group_name}')
            return self.format_id(dialog.id)
      return None


   async def create_group(self, group_name: str, group_users: str = None, prefix: str = None, description: str = "no description"):
      group_full_name = group_name if prefix is None else f'{prefix} {group_name}'
      group_id = await self.find_group_by_name(group_full_name)
      if(group_id is None):      
         createdGroup = await self.client(CreateChannelRequest(f'{prefix} {group_name}', description, megagroup=True))
         group_id = createdGroup.__dict__["chats"][0].__dict__["id"]
         print(f'created group {group_full_name} with id {group_id}')
         if(group_users is not None):
            await self.client(InviteToChannelRequest(channel=group_id, users=group_users))
            await self.give_users_admin_rights(group_id)
      else:
         print(f'used exiting group {group_full_name} with id {group_id}')
      
      return group_id


   async def give_users_admin_rights(self, channel_id):
      users = await self.client.get_participants(channel_id)
      for u in users:
         if(u.bot):
            print(f'adding rights for {u.username}' )
            await self.apply_admin_to_user(u, channel_id)


   async def apply_admin_to_user(self, user, channelId):
      await self.client.edit_admin(add_admins=True, entity=channelId, user = user, post_messages = True, edit_messages = True)

   async def create_feed(self, feed_name: str, source_id): 
      group_users = self.get_group_users_to_add(feed_name, self.feeds)
      group_id = await self.create_group(feed_name, group_users, 'Feed', f'forwards from {source_id}')   
      return group_id

   async def create_report_group(self, report_group_name: str, group_description: str):
      group_users = self.get_group_users_to_add(report_group_name, self.report_groups)
      group_id = await self.create_group(report_group_name, group_users, "Report", group_description)
      return group_id

   async def find_report_destination(self, message_from_id: int):
      # flat map all report feeds
      report_feeds = list(itertools.chain.from_iterable(map(lambda x: x["feeds"], self.report_groups)))
      destination_report_id = list(filter(lambda x: x["channel_id"]==message_from_id, report_feeds))
      if(len(destination_report_id) > 0):
         return destination_report_id[0]["report_channel_id"]
      return None

   async def create_feed_groups(self):
      for feed in self.feeds:
         feed_name = feed["name"]
         source_id = feed["id"]
         feed["channel_id"] = await self.create_feed(feed_name, source_id)
   
   async def create_report_groups(self):
      for report_group in self.report_groups:
         group_name = report_group["name"]      
         report_group["report_channel_id"] = await self.create_report_group(group_name, 'reports for addChannelNames')
         for feed in report_group["feeds"]:
            feed["report_channel_id"] = report_group["report_channel_id"]
            feed["channel_id"] = await self.find_group_by_name(feed["name"])
            if(feed["channel_id"] is None):
               print(f'Check your configs Could not find a report group for {feed["name"]}')

   async def create_buy_signals_group(self):
      group_name = buy_signals_group["name"]
      all_report_bots = list(itertools.chain.from_iterable(map(lambda x: x["users"], self.report_groups)))
      buy_signals_group["channel_id"] = await self.create_group(group_name, all_report_bots, 'Signals', f'Buy signals will be forwarded to {trade_bot}')

   # creates a group with scraper bot and safe bot as participants and for
   # also listens for messages on buy signals and forwards to trade bot
   async def create_groups(self):   
      print("CONNECTED")
      await self.create_feed_groups()
      await self.create_report_groups()
      # await self.create_buy_signals_group()




   async def start_listeners(self):
      print("Listening...")
      await self.client.send_message(buy_signals_group["channel_id"], f'Started api service {datetime.datetime.now()}')
      feed_sources = list(map(lambda x: x['id'], self.feeds))
      #forward from sources to feed groups
      @self.client.on(events.NewMessage(chats=feed_sources))
      async def handler(event):         
         print("Forward to feed group")
         source_id = self.getSenderIdFromMessage(event.message)
         destination = list(filter(lambda x: x['id'] == source_id, self.feeds))[0]
         try:
            if ('lookup' in destination and destination['lookup'] is not None):
               print(destination)
               print(destination['lookup'])
               lookup = destination['lookup']+'*.*'
               print("lookup "+ lookup)
               event.message.message =  re.search(lookup, event.message.message).group() 
         except:
            print('lookup not defined')

         await self.client.send_message(destination['channel_id'], event.message)
      
      feed_groups = list(map(lambda x: x['channel_id'], self.feeds))
      #forward from feed groups to report group
      @self.client.on(events.NewMessage(chats=feed_groups))
      async def handler(event):
         if("SafeAnalyzer" in str(event.message)):
            try:
               chat_from = event.chat if event.chat else (await event.get_chat()) # telegram MAY not send the chat enity
               chat_title = chat_from.title
               #print(f'message {event.message}')
               print(f'from chat {chat_title}')
               event.message.message = event.message.message + "\n" + "Source feed: " + chat_title + "\n"
               #print(f'message replaced {str(event.message).replace("SafeAnalyzer | ", chat_title)}')
            except:
               print("COULD NOT GET CHAT TITLE")
            print("feed analyzer response")         
            channelId = self.getSenderIdFromMessage(event.message)
            destination_report_id = await self.find_report_destination(channelId)
            if(destination_report_id is not None):
               print("Send analyzed report to report group")
               await self.client.send_message(destination_report_id, event.message)
            else: 
               print(f'could not find a destination for {channelId}')
               return 
         

      # forward from buy signals group to trade bot
      @self.client.on(events.NewMessage(chats=[buy_signals_group['channel_id']]))
      async def handler(event):
         print(event.message.message)
         if(event.message.message.startswith("update")):
            print("updating feeds")
            await self.check_for_new_feeds()
         else:
            print("Forward to trade bot")
            await self.client.send_message(trade_bot, event.message)
      

   def getCodeFromFile(self, clear = True): 
      code = ''
      while(code == ''):
         with open(code_file, "r", encoding="utf-8") as myfile:
            code = myfile.read()           
      print(code)
      if(clear):
         open(code_file, "w").close()
      return code

   async def run(self):
      if(self.sheets is None):
         self.sheets = Sheets()
      print("sheets initialized")
      with open(token_file, 'r') as token:
         print(token.read())

      # # TODO rather run update      
      self.feeds = self.sheets.read_feeds()
      self.report_groups = self.sheets.read_reports()
      print(f'feeds {self.feeds}')
      print(f'report_groups {self.report_groups}')

      try:
         await self.client.start(phone=phone, code_callback=lambda : self.getCodeFromFile())
         print("client started")
      except Exception as error:
         print(f'error starting client {error}')
      async with self.client:
         self.interactor =  MaestroInteractor(self.client)
         await self.create_buy_signals_group()
         await self.client.send_message(buy_signals_group["channel_id"], f'update from api service')
         await self.create_groups()
         await self.start_listeners()
         await self.client.run_until_disconnected()



   ######### TODO REPLACE WITH AN EVENT FROM THE SHEET
   async def check_for_new_feeds(self):
      try:
         r = self.sheets.read_reports()
         f = self.sheets.read_feeds()         
         print(f'report_groups {report_groups}')
         print(f'feeds {feeds}')
         if(report_groups != r and feeds != f):
               feeds = f
               report_groups = r
               print("############################new feeds found############################")
               await self.create_groups()
      except Exception as error:
         print(f'Failed to read sheets {error}')
         self.sheets.auth()


