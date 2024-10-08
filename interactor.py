import os
import asyncio
import itertools
import time
import re
from dotenv import load_dotenv 
from telethon.sync import TelegramClient, events
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
from telethon.tl.types import KeyboardButtonCallback
from telethon.tl.types import Message
from telethon.tl.types import UpdateEditMessage, UpdateNewMessage
import random
from sheets import Sheets
load_dotenv()

class MaestroInteractor:   
   
   def __init__(self, client: TelegramClient, sheets: Sheets):      
      self.client = client
      self.sheets = sheets
      self.maestro_username = os.environ.get("TRADEBOTNAME")
      self.maestro_id = int(os.environ.get("MAESTRO_ID"))
      self.sleep_period = int(os.environ.get("SLEEP_TIME"))
      self.trailing_stop = self.sheets.read_interactor_stop_loss()
      self.current_monitor: UpdateEditMessage = None
      self.buttons: list[{"name", "data"}] = [] 
      self.current_trades:list[{"name", "read_stop_loss", "percent", "age", "desired_stop_loss", "last_read"}] = []
      self.primary_trade = None
      self.handlers = []
      self.buy_signals_group_id = None


      @client.on(events.NewMessage(chats=[self.maestro_id], incoming=True))
      async def onMaestroMonitorShown(message: UpdateNewMessage):                  
         print(f"SHOWN: "+message.message.message.replace('\n', ""))
         if(message.message.message.startswith("You are setting the sell low limit.")):
            await client.send_message(entity=self.maestro_username, message=str(self.primary_trade["desired_stop_loss"]), reply_to=message.message.id)
         elif(message.message.message.startswith("Reply to this message with your desired sell percentage. Minimum is 1. Max is 100")):
            await client.send_message(entity=self.maestro_username, message="100", reply_to=message.message.id)
            percent = self.primary_trade["percent"]
            age = self.primary_trade["age"]
            await client.send_message(entity=self.maestro_username, message=f"⚠️ Initiating auto-sell. Time limit has been met ({percent}%). Trade is {age} seconds old")
            await self.send_command('monitor')
         elif(message.message.message.startswith("📌 Primary Trade")):
            ## force an update
            await message.message.click(text="➡")
         elif(message.message.message.startswith("❌ You do not have any active monitors!")):
            self.current_trades = []
         elif("Sell transaction of" in message.message.message):
            time.sleep(self.sleep_period)
            await self.send_command('wallets')         
         elif(message.message.message.startswith("Public Commands:")):
            self.current_trades = []            
         # if(message.message.message is not None):         
      self.handlers.append(onMaestroMonitorShown)
            
            


      @client.on(events.MessageEdited(chats=[self.maestro_id]))
      async def handler(event: UpdateEditMessage):
         print(f"EDITED: " + event.message.message.replace('\n', ""))
         self.current_monitor = event
         self.buttons = self.get_buttons_from_monitor(self.current_monitor)         
         message_text = event.message.message         
         

         if('%' not in [x['text'] for x in self.buttons] and message_text.startswith("📌 Primary Trade")):
            self.current_trades = self.get_trades_from_message(message_text)            
            self.primary_trade = self.current_trades[0]
            unfilled_trades = [x for x in self.current_trades if x["read_stop_loss"] == -100 or x["age"] == 0 or x["last_read"] == -999]
            trades_with_outdated_stop_loss = [x for x in self.current_trades if x["read_stop_loss"] < x["desired_stop_loss"]]
            # trades_older_than_an_hour = [x for x in self.current_trades if x["age"] >= 60*60]
            # trades read more than 150 seconds ago
            most_stale_trades = sorted([x for x in self.current_trades if x["last_read"] != -999 and time.time() - x["last_read"] >= 30], key=lambda x: x["last_read"])
            # tell scraper bot how many open trades there are
            await self.client.send_message('Pfscrapedevbot', f"/set {len(self.current_trades)}")
            
            # ensure all trades are filled out
            if(len(unfilled_trades) > 0):               
               await self.navigate_to_trade_at_index(unfilled_trades[0]["index"])
            #navigate to trades if they need to update stop loss            
            elif(len(trades_with_outdated_stop_loss) > 0):
               #check if primary trade stop loss needs to be updated
               if(self.primary_trade["read_stop_loss"] < self.primary_trade["desired_stop_loss"]):
                  await event.message.click(text=self.get_stop_loss_button(self.buttons)["text"])
               else:
                  await self.navigate_to_trade_at_index(trades_with_outdated_stop_loss[0]["index"])
            # purge older than an hour
            elif(self.primary_trade["age"] >= 60 * 60):                  
                  await event.message.click(text=self.get_sell_xpercent_button(self.buttons)["text"])                  
            # purge older than an hour
            # elif(len(trades_older_than_an_hour) > 0):
            #    if(self.primary_trade["age"] >= 60 * 60):
            #       percent = self.primary_trade["percent"]
            #       age = self.primary_trade["age"]
            #       await client.send_message(entity=self.maestro_username, message=f"⚠️ Initiating auto-sell. Time limit has been met ({percent}%). Trade is {age} seconds old")
            #       await event.message.click(text=self.get_sell_all_button(self.buttons)["text"])
                  
            #       time.sleep(self.sleep_period * 3)
            #    else:
            #       await self.navigate_to_trade_at_index(trades_older_than_an_hour[0]["index"])
            elif(len(most_stale_trades) > 0):
               await self.navigate_to_trade_at_index(most_stale_trades[0]["index"])
               time.sleep(self.sleep_period)

         elif('%' in [x['text'] for x in self.buttons] and message_text.startswith("📌 Primary Trade")):
            percent_button_text = [x['text'] for x in self.buttons if x['text']=='%']               
            if(len(percent_button_text)):                  
               await self.click_button_by_text(event.message, percent_button_text[0])


      self.handlers.append(handler)
      
      loop = asyncio.get_event_loop()
      asyncio.run_coroutine_threadsafe(self.send_command('monitor'), loop)      
      


   def get_oldest_trade(self):
      oldest = self.current_trades[0]
      for t in self.current_trades:
         if(t["age"]>oldest["age"]):
            oldest = t
      return oldest

   def read_trade_string(self, trade: str, original_message: str):

      index = int(trade.split("🪙")[0].replace("/", "").strip() or '0')
      name = trade.split("🪙")[1].split("🚀")[0].replace("$", "").strip()      
      percent = float(trade.split("🚀")[1].split("%")[0].strip())
      trade_item = [x for x in self.current_trades if x["name"] == name]
      now = time.time()
      # primary trade
      if(index == 0):
         current_stop_loss = round(float(self.get_stop_loss_button(self.buttons)["text"].replace("%", "")), 2)
         current_age = self.convert_time_to_seconds(original_message.split("Time elapsed:")[1].split("\n")[0])
         return {"index": index, "name": name, "percent": percent, "age": current_age, "read_stop_loss": current_stop_loss, "desired_stop_loss": round(max(percent + self.trailing_stop, current_stop_loss, self.trailing_stop), 2) , "last_read": now }
      # other trade
      else:
         if(len(trade_item)):            
            return {"index": index, "name": name, "percent": percent, "age": trade_item[0]["age"], "read_stop_loss": trade_item[0]["read_stop_loss"], "desired_stop_loss": round(max(percent + self.trailing_stop, trade_item[0]["read_stop_loss"], self.trailing_stop) , 2), "last_read": trade_item[0]["last_read"] }
         else:
            return {"index": index, "name": name, "percent": percent, "age": 0, "read_stop_loss": -100, "desired_stop_loss": round(max(percent + self.trailing_stop, self.trailing_stop), 2), "last_read": -999 }

   def get_trades_from_message(self, message: str):
      return [self.read_trade_string(x, message) for x in re.findall("🪙*.*", message) if "🚀" in x]

   # input is 9h 12m 6s  
   def convert_time_to_seconds(self, time_string: str):
      time_string = time_string.strip()
      parts = time_string.split(" ")
      total_seconds = 0
      for p in parts:
         if(p.endswith("h")):
               total_seconds += int(p.replace("h", "")) * 60 * 60
         elif(p.endswith("m")):
               total_seconds += int(p.replace("m", "")) * 60
         elif(p.endswith("s")):
               total_seconds += int(p.replace("s", ""))
      return total_seconds

   async def navigate_to_trade_at_index(self, index: int):
      await self.send_command(index)      

   async def send_command(self, command: str):
      await self.client.send_message(self.maestro_username, f'/{command}')

   async def click_button_by_text(self, message, button_text):
      await message.click(text=button_text)

   async def click_button_by_code(self, message, code):
      await message.click(data=code)

   def get_buttons_from_monitor(self, update: UpdateEditMessage):
      if(update.message.reply_markup is None):
         return []
      buttons = list(itertools.chain.from_iterable(map(lambda b: b.buttons, update.message.reply_markup.rows)))
      return list(map(lambda b: {'text':b.text, 'data': b.data}, buttons))


   def get_stop_loss_button(self, buttons):
         return buttons[self.try_get_button_index_by_text(buttons, '◀ Lo | Hi ▶') - 1]

   def get_refresh_button(self, buttons):
      return buttons[self.try_get_button_index_by_text(buttons, '➡') - 1]

   def get_left_nav_button(self, buttons):
      return buttons[self.try_get_button_index_by_text(buttons, '⬅')]
   
   def get_right_nav_button(self, buttons):
      return buttons[self.try_get_button_index_by_text(buttons, '➡')]

   def get_sell_xpercent_button(self, buttons):
      return buttons[self.try_get_button_index_by_text(buttons, 'Sell X %')]

   def try_get_button_index_by_text(self, buttons, text):
      try:
         return list(map(lambda x: x['text'] , buttons)).index(text)
      except:
         return None

   def __del__(self):      
      for h in self.handlers:         
         self.client.remove_event_handler(h)
      self.handlers = []
