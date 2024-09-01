import os
import json
from telethon.sync import TelegramClient, events
from dotenv import load_dotenv, dotenv_values 
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
import asyncio
import time
load_dotenv()

phone = os.environ.get("PHONE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")
code_file = os.environ.get("CODE_FILE")
trade_bot = os.environ.get("TRADEBOTNAME")
buy_signals = int(os.environ.get("BUYSIGNALSGROUP"))


feeds = json.loads(os.environ.get("FEEDS"))
feed_users = list(map(lambda x: x['users'], feeds)); # add safe analyzer and the bot api user
print(feeds)


def get_feed_users(feed_name):
   return list(filter(lambda x: x["name"]==feed_name ,feeds))[0]["users"]

for f in feeds:
   print(get_feed_users(f["name"]))

def getIdFromMessage(message):
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

async def feed_exists(client, feed_name):
   async for dialog in client.iter_dialogs():
      print(dialog.title)
      if(dialog.title is not None and dialog.title == f'Feed {feed_name}'):
         return format_id(dialog.id)
   return 0

async def applyAdminToUser(client, user, channelId):
   await client.edit_admin(add_admins=True, entity=channelId, user = user, post_messages = True, edit_messages = True)

async def create_feed(client , feed_name, source_id): 
   newChannelID = await feed_exists(client, feed_name)
   if(newChannelID == 0):
      createdGroup = await client(CreateChannelRequest(f'Feed {feed_name}', f'forwards from {feed_name} {source_id}' ,megagroup=True))
      newChannelID = createdGroup.__dict__["chats"][0].__dict__["id"]
      print(f'created new group {newChannelID}')
      await client(InviteToChannelRequest(channel=newChannelID, users=get_feed_users(feed_name)))
   else:
      print(f'using existing group {newChannelID}')
   users = await client.get_participants(newChannelID)
   print(users)
   for u in users:
      if(u.bot):
         await client.edit_admin(add_admins=True, entity=newChannelID, user = u, post_messages = True, edit_messages = True)
   return newChannelID

# creates a group with scraper bot and safe bot as participants and for
# also listens for messages on buy signals and forwards to trade bot
async def create_feeds(client):   
   print("CONNECTED")
   for feed in feeds:
      feed_name = feed["name"]
      source_id = feed["id"]
      id = await create_feed(client, feed_name, source_id)
      feed["channel_id"] = id

   sources = list(map(lambda x: x['id'], feeds))
   @client.on(events.NewMessage(chats=sources))
   async def handler(event):
      source_id = getIdFromMessage(event.message)
      destination_id = list(filter(lambda x: x['id'] == source_id, feeds))[0]['channel_id']
      await client.send_message(destination_id, event.message)
      
   @client.on(events.NewMessage(chats=[buy_signals]))
   async def handler(event):         
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
      await create_feeds(client)
      await client.run_until_disconnected()

# if __name__ == "__main__":
#     asyncio.run(main(TelegramClient(session, api_id, api_hash)))
