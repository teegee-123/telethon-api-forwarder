import os
import json
from telethon.sync import TelegramClient, events
from dotenv import load_dotenv, dotenv_values 
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest

load_dotenv()

phone = os.environ.get("PHONE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")

trade_bot = os.environ.get("TRADEBOTNAME")
buy_signals = int(os.environ.get("BUYSIGNALSGROUP"))


feeds = json.loads(os.environ.get("FEEDS"))
feed_users = json.loads(os.environ.get("FEED_USERS")) # add safe analyzer and the bot api user
print(feeds)


def getMessageId(message):
   if(hasattr(message.peer_id, 'channel_id')):            
      return message.peer_id.channel_id 
   if(hasattr(message.peer_id, 'user_id')):
      return message.peer_id.user_id 
   if(hasattr(message.peer_id, 'chat_id')):
      return message.peer_id.chat_id

async def getChats(client): 
   async for dialog in client.iter_dialogs():
      with open("chats3.txt", "a", encoding="utf-8") as myfile:
         id = getMessageId(dialog.message)
         print(f'{dialog.name}:{id}\n')
         myfile.write(f'{dialog.name}:{id}\n')


def create_feed(client , feed_name):      
   createdGroup = client(CreateChannelRequest(f'Feed {feed_name}', f'forwards from {feed_name}' ,megagroup=True))
   newChannelID = createdGroup.__dict__["chats"][0].__dict__["id"]     
   client(InviteToChannelRequest(channel=newChannelID, users=feed_users))

   users = client.get_participants(newChannelID)
   client.edit_admin(add_admins=True, entity=newChannelID, user = users[1], post_messages = True, edit_messages = True)
   client.edit_admin(add_admins=True, entity=newChannelID, user = users[2], post_messages = True, edit_messages = True)
   return newChannelID

# creates a group with scraper bot and safe bot as participants and for
# also listens for messages on buy signals and forwards to trade bot
def create_feeds():
   channels = []
   with TelegramClient(session, api_id, api_hash) as client:    
      for feed in feeds:
         feed_name = feed["name"]
         source_id = feed["id"]
         id = create_feed(client, feed_name)
         if(not feed["channel_id"]):
            feed["channel_id"] = id
      
      sources = list(map(lambda x: x['id'], feeds))
      @client.on(events.NewMessage(chats=sources))
      async def handler(event):
         source_id = getMessageId(event.message)
         destination_id = list(filter(lambda x: x['id'] == source_id, feeds))[0]['channel_id']
         await client.send_message(destination_id, event.message)
      
      @client.on(events.NewMessage(chats=[buy_signals]))
      async def handler(event):         
         await client.send_message(trade_bot, event.message)


      client.run_until_disconnected()

create_feeds()



