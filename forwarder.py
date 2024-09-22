import os
import json
import datetime
import itertools
from telethon.sync import TelegramClient, events
from dotenv import load_dotenv, dotenv_values 
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
import time
import re

from interactor import MaestroInteractor



load_dotenv()

phone = os.environ.get("PHONE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")
code_file = os.environ.get("CODE_FILE")
trade_bot = os.environ.get("TRADEBOTNAME")
buy_signals_group = json.loads(os.environ.get("BUYSIGNALSGROUP"))
report_group_name = os.environ.get("REPORT_GROUP_NAME")


feeds = json.loads(os.environ.get("FEEDS"))
report_groups = json.loads(os.environ.get("REPORT_GROUPS"))
print(f'feeds {feeds}')
print(f'report_groups {report_groups}')


def get_group_users_to_add(group_name, groups):
   return list(filter(lambda x: x["name"]==group_name ,groups))[0]["users"]

def getSenderIdFromMessage(message):
   if(hasattr(message.peer_id, 'channel_id')):            
      return message.peer_id.channel_id 
   if(hasattr(message.peer_id, 'user_id')):
      return message.peer_id.user_id 
   if(hasattr(message.peer_id, 'chat_id')):
      return message.peer_id.chat_id

def format_id(id):
   id = abs(id)
   if(str(id).startswith("100")):
      id = str(id)[3:]
   return int(id)

async def find_group_by_name(client, group_name):   
   print(f'looking for {group_name}')   
   async for dialog in client.iter_dialogs():
      if(dialog.title is not None and dialog.title == group_name):
         print(f'Found Group {group_name}')
         return format_id(dialog.id)
   return None


async def create_group(client, group_name, group_users = None, prefix = None, description = "no description"):
   group_full_name = group_name if prefix is None else f'{prefix} {group_name}'
   group_id = await find_group_by_name(client, group_full_name)
   if(group_id is None):      
      createdGroup = await client(CreateChannelRequest(f'{prefix} {group_name}', description, megagroup=True))
      group_id = createdGroup.__dict__["chats"][0].__dict__["id"]
      print(f'created group {group_full_name} with id {group_id}')
      if(group_users is not None):
         await client(InviteToChannelRequest(channel=group_id, users=group_users))
         await give_users_admin_rights(client, group_id)
   else:
      print(f'used exiting group {group_full_name} with id {group_id}')
   
   return group_id


async def give_users_admin_rights(client, channel_id):
   users = await client.get_participants(channel_id)
   for u in users:
      if(u.bot):
         print(f'adding rights for {u.username}' )
         await apply_admin_to_user(client, u, channel_id)


async def apply_admin_to_user(client, user, channelId):
   await client.edit_admin(add_admins=True, entity=channelId, user = user, post_messages = True, edit_messages = True)

async def create_feed(client , feed_name, source_id): 
   group_users = get_group_users_to_add(feed_name, feeds)
   group_id = await create_group(client, feed_name, group_users, 'Feed', f'forwards from {source_id}')   
   return group_id

async def create_report_group(client, report_group_name, group_description):
   group_users = get_group_users_to_add(report_group_name, report_groups)
   group_id = await create_group(client, report_group_name, group_users, "Report", group_description)
   return group_id

async def find_report_destination(message_from_id):
   # flat map all report feeds
   report_feeds = list(itertools.chain.from_iterable(map(lambda x: x["feeds"], report_groups)))
   destination_report_id = list(filter(lambda x: x["channel_id"]==message_from_id, report_feeds))
   if(len(destination_report_id) > 0):
      return destination_report_id[0]["report_channel_id"]
   return None

async def create_feed_groups(client):
   for feed in feeds:
      feed_name = feed["name"]
      source_id = feed["id"]
      feed["channel_id"] = await create_feed(client, feed_name, source_id)
   
async def create_report_groups(client):
   for report_group in report_groups:
      group_name = report_group["name"]      
      report_group["report_channel_id"] = await create_report_group(client, group_name, 'reports for addChannelNames')
      for feed in report_group["feeds"]:
         feed["report_channel_id"] = report_group["report_channel_id"]
         feed["channel_id"] = await find_group_by_name(client, feed["name"])
         if(feed["channel_id"] is None):
            print(f'Check your configs Could not find a report group for {feed["name"]}')

async def create_buy_signals_group(client):
   group_name = buy_signals_group["name"]
   all_report_bots = list(itertools.chain.from_iterable(map(lambda x: x["users"], report_groups)))
   buy_signals_group["channel_id"] = await create_group(client, group_name, all_report_bots, 'Signals', f'Buy signals will be forwarded to {trade_bot}')

# creates a group with scraper bot and safe bot as participants and for
# also listens for messages on buy signals and forwards to trade bot
async def create_groups(client):   
   print("CONNECTED")
   await create_feed_groups(client)
   await create_report_groups(client)
   await create_buy_signals_group(client)

   feed_sources = list(map(lambda x: x['id'], feeds))

   print("Listening...")
   await client.send_message(buy_signals_group["channel_id"], f'Started api service {datetime.datetime.now()}')
   #forward from sources to feed groups
   @client.on(events.NewMessage(chats=feed_sources))
   async def handler(event):      
      print("Forward to feed group")
      source_id = getSenderIdFromMessage(event.message)
      destination = list(filter(lambda x: x['id'] == source_id, feeds))[0]
      try:
         if ('lookup' in destination and destination['lookup'] is not None):
            print(destination)
            print(destination['lookup'])
            lookup = destination['lookup']+'*.*'
            print("lookup "+ lookup)
            event.message.message =  re.search(lookup, event.message.message).group() 
      except:
         print('lookup not defined')

      await client.send_message(destination['channel_id'], event.message)
   
   feed_groups = list(map(lambda x: x['channel_id'], feeds))
   #forward from feed groups to report group
   @client.on(events.NewMessage(chats=feed_groups))
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
         channelId = getSenderIdFromMessage(event.message)
         destination_report_id = await find_report_destination(channelId)
         if(destination_report_id is not None):
            print("Send analyzed report to report group")
            await client.send_message(destination_report_id, event.message)
         else: 
            print(f'could not find a destination for {channelId}')
            return 
      

   # forward from buy signals group to trade bot
   @client.on(events.NewMessage(chats=[buy_signals_group['channel_id']]))
   async def handler(event):         
      print("Forward to trade bot")
      # time.sleep(2) #TODO add this if neccessary
      await client.send_message(trade_bot, event.message)


def getCodeFromFile(delay = 15): 
   code = ''
   while(code == ''):
      with open(code_file, "r", encoding="utf-8") as myfile:
         code = myfile.read()
   print(code)
   return code
   # if(delay != 0): 
   #    time.sleep(delay)



import threading

def set_interval(func, sec):
    async def func_wrapper():
        set_interval(func, sec)
        await func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

async def main(client):
   print(client)
   try:
      await client.start(phone=phone, code_callback= lambda : getCodeFromFile(15))
      print("client started")
   except Exception as error:
      print(f'error starting client {error}')
   async with client:
      interactor =  MaestroInteractor(client)
      set_interval(lambda: client.send_message('Pfscrapedevbot', f'/pump'), 120)
      await create_groups(client)      
      await client.run_until_disconnected()

# if __name__ == "__main__":
#     asyncio.run(main(TelegramClient(session, api_id, api_hash)))
