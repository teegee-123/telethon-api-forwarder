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
      self.current_trades:list[{"name", "stop_loss", "percent", "age"}] = []
      self.handlers = []


      @client.on(events.NewMessage(chats=[self.maestro_id], incoming=True))
      async def onMaestroMonitorShown(message: UpdateNewMessage):                  
         print(f"SHOWN: "+message.message.message.replace('\n', ""))
         if(message.message.message.startswith("You are setting the sell low limit.")):
            primary_trade_name = self.current_monitor.message.message.split("🪙")[1].split("\n")[0].split(" ")[1].replace("$", "").strip()            
            new_stop_loss = [x["stop_loss"] for x in self.current_trades if x["name"] == primary_trade_name][0]            
            await client.send_message(entity=self.maestro_username, message=str(new_stop_loss), reply_to=message.message.id)
         elif(message.message.message.startswith("📌 Primary Trade")):            
            #self.update_current_trades(message.message.message or message.message)
            await message.message.click(text="➡")
         elif(message.message.message.startswith("❌ You do not have any active monitors!")):                        
            self.current_trades = []
         elif("Sell transaction of" in message.message.message):
            self.current_trades = []
            await self.send_command(client, 'wallets')
         elif(message.message.message.startswith("Public Commands:")):            
            self.current_trades = []            
         # if(message.message.message is not None):         
      self.handlers.append(onMaestroMonitorShown)
            
            


      @client.on(events.MessageEdited(chats=[self.maestro_id]))
      async def handler(event: UpdateEditMessage):
         print(f"EDITED: " + event.message.message.replace('\n', ""))
         self.current_monitor = event
         self.buttons = self.get_buttons_from_menu(event)
         
         message_text = event.message.message
         self.update_current_trades(message_text)
         primary_trade = [x for x in self.current_trades if x["index"]==0]         
         primary_is_oldest = False

         if(len([x for x in self.current_trades if x["index"]==0]) > 0):
            primary_trade = [x for x in self.current_trades if x["index"]==0][0]
            try:
               if('%' not in [x['text'] for x in self.buttons]):
                  primary_trade["stop_loss"] = int(str(self.get_stop_loss_button(self.buttons)['text']).replace("%", ''))
               primary_trade["age"] = self.convert_time_to_seconds(message_text.split("Time elapsed:")[1].split("\n")[0])
            except:
               print("ERROR setting SL")
            primary_is_oldest = self.is_oldest(primary_trade["age"])
         else:
            print(f"Could not find primary trade {self.current_trades}")            
            return 
         print(f"PRIMARY TRADE: {primary_trade}")
         print(f"% button: {'%' in [x['text'] for x in self.buttons]}")
         #if it has '%' button click it, we want to set SL
         if('%' in [x['text'] for x in self.buttons] and message_text.startswith("📌 Primary Trade")):               
            percent_button_text = [x['text'] for x in self.buttons if x['text']=='%']               
            if(len(percent_button_text)):                  
               await self.click_button_by_text(event.message, percent_button_text[0])
            ##else:                   
         
         #if its normal menu set current trades values
         elif('%' not in [x['text'] for x in self.buttons] and message_text.startswith("📌 Primary Trade")):            

            # setting new stop loss
            if(primary_trade["stop_loss"] < primary_trade["percent"] + self.trailing_stop ):                                    
               primary_trade["stop_loss"] = primary_trade["percent"] + self.trailing_stop                  
               await self.current_monitor.message.click(text=self.get_stop_loss_button(self.buttons)["text"])               
            
            # iterate trades
            else:
               if(primary_is_oldest and len(self.current_trades)>=6):
                  # close oldest trade                     
                  sell_all_button = self.get_sell_all_button(self.buttons)
                  await event.message.click(text=sell_all_button["text"])
                  time.sleep(self.sleep_period)
               # navigate to trade missing stop_loss or age
               else:
                  # trades with missing stop_loss or age
                  trade_with_missing_data = [x for x in  self.current_trades if (x["age"] == 0) and x["index"] != 0]                     
                  # trades with stop_loss that need updating
                  trade_with_wrong_stop_loss = [x for x in  self.current_trades if x["stop_loss"] != self.trailing_stop and x["stop_loss"] < x["percent"] + self.trailing_stop and x["index"]!=0]
                  print(f"SL TO UPDATE {trade_with_wrong_stop_loss}")                     
                  # check for incomplete trade data
                  if(len(trade_with_missing_data) > 1 and trade_with_missing_data[1]["index"] != 0):
                     await self.navigate_to_trade_at_index(random.choice(trade_with_missing_data)["index"])
                  # check for stop losses that need changing
                  elif(len(trade_with_wrong_stop_loss) > 0):
                     index = random.choice(trade_with_wrong_stop_loss)["index"]
                     if (index!=0):
                        await self.navigate_to_trade_at_index(random.choice(trade_with_wrong_stop_loss)["index"])
                     else:
                        await self.navigate_to_trade_at_index(1) 
                  #nav to random
                  else:                                            
                     await self.navigate_to_trade_at_index(random.choice([x for x in self.current_trades if x["index"]!=0])["index"])
                  time.sleep(self.sleep_period)
                  # TODO add this back with bigger sleep time
                  #await self.send_command(self.client, 'monitor')
      self.handlers.append(handler)
      
      loop = asyncio.get_event_loop()
      asyncio.run_coroutine_threadsafe(self.send_command(self.client, 'monitor'), loop)      
      


   def read_trade_string(self, trade: str, original_message: str):            
      index = int(trade.split("🪙")[0].replace("/", "").strip() or '0')
      name = trade.split("🪙")[1].split("🚀")[0].replace("$", "").strip()      
      percent = int(float(trade.split("🚀")[1].split("%")[0].strip()))
      trade_item = [x for x in self.current_trades if x["name"] == name]      
      primary_trade_age = self.convert_time_to_seconds(original_message.split("Time elapsed:")[1].split("\n")[0])
      #primary_trade_stop_loss = int(str(self.get_stop_loss_button(self.buttons)['text']).replace("%", ''))
      # primary trade
      if(len(trade_item) > 0 and index == 0):          
         return {"index": 0, "name": name, "percent": percent, "age": primary_trade_age, "stop_loss": percent - abs(self.trailing_stop)}
      # other trade
      elif(len(trade_item) > 0):         
         return {"index": index, "name": name, "percent": percent, "age": trade_item[0]["age"], "stop_loss": percent - abs(self.trailing_stop)}
      else:         
         return {"index": index, "name": name, "percent": percent, "age": primary_trade_age if index == 0 else 0, "stop_loss": percent - abs(self.trailing_stop)}

      # # new trade
      # else:      
      #    return {"index": index, "name": name, "percent": percent, "age": None, "stop_loss": None}      

   def update_current_trades(self, message: str):
      if(message.startswith("📌 Primary Trade")):
         self.current_trades = [self.read_trade_string(x, message) for x in re.findall("🪙*.*", message) if "🚀" in x]         


   def is_oldest(self, age):
      oldest = max([x["age"] for x in self.current_trades if x["age"] is not None])
      return age >= oldest      

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
      await self.send_command(self.client, index)      

   async def send_command(self, client: TelegramClient, command: str):
      await client.send_message(self.maestro_username, f'/{command}')

   async def click_button_by_text(self, message, button_text):
      await message.click(text=button_text)

   async def click_button_by_code(self, message, code):
      await message.click(data=code)

   def get_buttons_from_menu(self, update: UpdateEditMessage):
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

   def get_sell_all_button(self, buttons):
      return buttons[self.try_get_button_index_by_text(buttons, '100%')]

   def try_get_button_index_by_text(self, buttons, text):
      try:
         return list(map(lambda x: x['text'] , buttons)).index(text)
      except:
         return None

   def __del__(self):      
      for h in self.handlers:         
         self.client.remove_event_handler(h)
      self.handlers = []
