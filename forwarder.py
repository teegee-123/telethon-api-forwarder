import os
import json
import time
import itertools
from telethon.sync import TelegramClient, events
from dotenv import load_dotenv, dotenv_values 
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
load_dotenv()

phone = os.environ.get("PHONE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")
code_file = os.environ.get("CODE_FILE")
trade_bot = os.environ.get("TRADEBOTNAME")
buy_signals = int(os.environ.get("BUYSIGNALSGROUP"))
report_group_name = os.environ.get("REPORT_GROUP_NAME")


feeds = json.loads(os.environ.get("FEEDS"))
report_groups = json.loads(os.environ.get("REPORT_GROUPS"))
print(feeds)
print(report_groups)


def get_group_users(group_name, groups):
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

async def get_group_id(client, feed_name):
   async for dialog in client.iter_dialogs():
      if(dialog.title is not None and dialog.title == f'Feed {feed_name}'):
         return format_id(dialog.id)
   return 0

async def applyAdminToUser(client, user, channelId):
   await client.edit_admin(add_admins=True, entity=channelId, user = user, post_messages = True, edit_messages = True)

async def create_feed(client , feed_name, source_id): 
   newChannelID = await get_group_id(client, feed_name)
   if(newChannelID == 0):
      createdGroup = await client(CreateChannelRequest(f'Feed {feed_name}', f'forwards from {feed_name} {source_id}' ,megagroup=True))
      newChannelID = createdGroup.__dict__["chats"][0].__dict__["id"]
      print(f'created new group {newChannelID}')
      await client(InviteToChannelRequest(channel=newChannelID, users=get_group_users(feed_name, feeds)))
   else:
      print(f'using existing group {newChannelID}')
   users = await client.get_participants(newChannelID)
   for u in users:
      if(u.bot):
         print(f'adding rights for {u.username}' )
         await client.edit_admin(add_admins=True, entity=newChannelID, user = u, post_messages = True, edit_messages = True)
   return newChannelID

async def create_report_group(client, report_group_name):
   print('create_report_group')
   print(report_group_name)
   newChannelID = await get_group_id(client, report_group_name)
   print("newChannelID REPORT ")
   print(newChannelID)
   if(newChannelID == 0):
      createdGroup = await client(CreateChannelRequest(f'{report_group_name}', f'reports for {report_group_name}' ,megagroup=True))
      newChannelID = createdGroup.__dict__["chats"][0].__dict__["id"]
      print(f'created new report group {newChannelID}')
      await client(InviteToChannelRequest(channel=newChannelID, users=get_group_users(report_group_name, report_groups)))
   else:
      print(f"using existing report group {newChannelID}")
   
   users = await client.get_participants(newChannelID)
   for u in users:
      if(u.bot):
         print(f'adding rights for {u.username}' )
         await client.edit_admin(add_admins=True, entity=newChannelID, user = u, post_messages = True, edit_messages = True)


async def find_report_destination(message_from_id):
   # flat map all report feeds
   report_feeds = list(itertools.chain.from_iterable(map(lambda x: x["feeds"], report_groups)))
   destination_report_id = list(filter(lambda x: x["channel_id"]==message_from_id, report_feeds))
   if(len(destination_report_id) > 0):
      return destination_report_id["report_channel_id"]
   return None
# creates a group with scraper bot and safe bot as participants and for
# also listens for messages on buy signals and forwards to trade bot
async def create_groups(client):   
   print("CONNECTED")
   for feed in feeds:
      feed_name = feed["name"]
      source_id = feed["id"]
      feed["channel_id"] = await create_feed(client, feed_name, source_id)

   for report_group in report_groups:
      group_name = report_group["name"]      
      report_group["report_channel_id"] = await create_report_group(client, group_name)
      for feed in report_group["feeds"]:
         feed["report_channel_id"] = report_group["report_channel_id"]
         feed["channel_id"] = get_group_id(client, feed["name"])
         if(feed["channel_id"] == 0):
            raise f'Check your configs Could not find a report group for {feed["name"]}'


   feed_sources = list(map(lambda x: x['id'], feeds))
   destinations = list(map(lambda x: x['channel_id'], feeds))

   #forward from sources to feed groups
   @client.on(events.NewMessage(chats=feed_sources))
   async def handler(event):      
      print("Forward to feed group")
      source_id = getSenderIdFromMessage(event.message)
      destination_id = list(filter(lambda x: x['id'] == source_id, feeds))[0]['channel_id']
      await client.send_message(destination_id, event.message)
   
   feed_groups = list(map(lambda x: x['channel_id'], feeds))
   #forward from feed groups to report group
   @client.on(events.NewMessage(chats=feed_groups))
   async def handler(event):
      if("SafeAnalyzer" in str(event.message)):
         channelId = getSenderIdFromMessage(event.message)
         destination_report_id = await find_report_destination(channelId)
         if(destination_report_id):
            print("Send analyzed report to report group")
            await client.send_message(destination_report_id, event.message)
         else: 
            print(f'could not find a destination for {channelId}')
      


   @client.on(events.NewMessage(chats=[buy_signals]))
   async def handler(event):         
      print("Forward to trade bot")
      await client.send_message(trade_bot, event.message)


def getCodeFromFile(delay = 15): 
   if(delay != 0): 
      time.sleep(delay)
   with open(code_file, "r", encoding="utf-8") as myfile:
      code = myfile.read()
      print(code)
      return code



async def main(client):
   await client.start(phone=phone, code_callback= lambda : getCodeFromFile(15))
   async with client:
      await create_groups(client)
      await client.run_until_disconnected()

# if __name__ == "__main__":
#     asyncio.run(main(TelegramClient(session, api_id, api_hash)))
