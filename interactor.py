import os
import asyncio
import itertools
import time
from dotenv import load_dotenv 
from telethon.sync import TelegramClient, events
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
from telethon.tl.types import KeyboardButtonCallback
from telethon.tl.types import Message
from telethon.tl.types import UpdateEditMessage, UpdateNewMessage
load_dotenv()

class MaestroInteractor:   
   def __init__(self, client: TelegramClient):
      self.client = client
      self.maestro_username = os.environ.get("TRADEBOTNAME")
      self.maestro_id = int(os.environ.get("MAESTRO_ID"))
      self.trailing_stop = int(os.environ.get("TRAILING_STOP"))      
      self.sleep_period = int(os.environ.get("SLEEP_TIME"))
      
      self.current_monitor: UpdateEditMessage = None
      self.buttons: list[{"name", "data"}] = [] 
      self.current_trades:list[{"name", "stop_loss", "percent"}] = []

      #monitor_updated_filter=lambda x: type(x) is UpdateEditMessage and x.message.message.startswith("📌 Primary Trade") #and x.message.peer_id.user_id == self.maestro_id
      # monitor_messaged_filter=lambda x: type(x.original_update) is UpdateNewMessage and x.original_update.message.message.startswith("📌 Primary Trade") and x.original_update.message.peer_id.user_id == self.maestro_id


      @client.on(events.NewMessage(chats=[self.maestro_id], incoming=True))
      async def onMaestroMonitorShown(message: Message):         
         if(message.message.message.startswith("You are setting the sell low limit.")):
            primary_trade_name = self.current_monitor.message.message.split("🪙")[1].split("\n")[0].split(" ")[1]
            new_stop_loss = [x["stop_loss"] for x in self.current_trades if x["name"] == primary_trade_name][0]            
            print(f'new stop {new_stop_loss}')
            await client.send_message(entity=self.maestro_username, message=str(new_stop_loss), reply_to=message.message.id)
         elif(message.message.message.startswith("📌 Primary Trade")):
            print("new monitor shown start iterating")
            await message.message.click(text="➡")
         elif(message.message.message.startswith("❌ You do not have any active monitors!")):
            print("clearing trades")
            self.current_trades = []

      @client.on(events.MessageEdited(chats=[self.maestro_id]))
      async def handler(event: UpdateEditMessage):
         self.current_monitor = event
         self.buttons = self.get_buttons_from_menu(event)
         print(f'Pinned: {event.message.pinned}')
         print(f'Current Trades: {self.current_trades}')
         #if it has '%' button click it, we want to set SL
         if('%' in [x['text'] for x in self.buttons]):
            print(f'clicking "%" button')
            percent_button_text = [x['text'] for x in self.buttons if x['text']=='%']
            print(percent_button_text)
            if(len(percent_button_text)):
               await self.click_button_by_text(event.message, percent_button_text[0])
            else: 
               print("ERROR: couldnt find '%' button")
         
         #if its normal menu set current trades values
         if('%' not in [x['text'] for x in self.buttons]):
            message_text = event.message.message
            primary_trade_percent = int(float(message_text.split("🚀")[1].split("\n")[0].split("%")[0]))
            primary_trade_name = message_text.split("🪙")[1].split("\n")[0].split(" ")[1]
            primary_trade_stop_loss = int(str(self.get_stop_loss_button(self.buttons)['text']).replace("%", ''))
            if(primary_trade_name in [x["name"] for x in self.current_trades]):
               print(f'Updating {primary_trade_name} values')
               primary_trade = [x for x in self.current_trades if x["name"] == primary_trade_name][0]
               primary_trade["percent"] = primary_trade_percent
               primary_trade["stop_loss"] = primary_trade_stop_loss # TODO update stop loss 
            else:
               print(f'Adding {primary_trade_name}')
               primary_trade = {"name": primary_trade_name, "percent": primary_trade_percent, "stop_loss": primary_trade_stop_loss} # TODO update stop loss
               self.current_trades.append(primary_trade)
            
            #tier 1
            if(primary_trade["percent"] > 14 and  primary_trade["percent"] <= 24 and primary_trade["stop_loss"] < 14):
               print(f'setting new Tiered stop loss, old: {primary_trade["stop_loss"]} new: {14}')
               print(f'setting new Tiered SL prev: {primary_trade["stop_loss"]}, new: {14}')
               primary_trade["stop_loss"] = 14
               print("clicking stop loss button")
               await self.current_monitor.message.click(text=self.get_stop_loss_button(self.buttons)["text"])               
            #tier 2
            elif(primary_trade["percent"] > 24 and  primary_trade["percent"] <= 30 and primary_trade["stop_loss"] < 24):
               print(f'setting new Tiered stop loss, old: {primary_trade["stop_loss"]} new: {24}')
               print(f'setting new Tiered SL prev: {primary_trade["stop_loss"]}, new: {24}')
               primary_trade["stop_loss"] = 24
               print("clicking stop loss button")
               await self.current_monitor.message.click(text=self.get_stop_loss_button(self.buttons)["text"])               

            # setting new stop loss
            elif(primary_trade["stop_loss"] < primary_trade["percent"] + self.trailing_stop):
               print(f'setting new stop loss, old: {primary_trade["stop_loss"]} new: {primary_trade["percent"] + self.trailing_stop}')
               print(f'setting new SL prev: {primary_trade["stop_loss"]}, new: {primary_trade["percent"] + self.trailing_stop}')
               primary_trade["stop_loss"] = primary_trade["percent"] + self.trailing_stop
               print("clicking stop loss button")
               await self.current_monitor.message.click(text=self.get_stop_loss_button(self.buttons)["text"])               
            
            # iterate trades
            else:
               print(f'No need to set Stop loss, old: {primary_trade["stop_loss"]} new: {primary_trade["percent"] + self.trailing_stop}')
               print(f'Navigating to next trade. Current trade: {primary_trade_name}')
               nav_right_button = self.get_right_nav_button(self.buttons)
               await event.message.click(text=nav_right_button["text"])
               time.sleep(self.sleep_period)
            

     
   
   async def send_command(self, client, command):
      await client.send_message(self.maestro_username, f'/{command}')

   async def click_button_by_text(self, message, button_text):
      await message.click(text=button_text)

   async def click_button_by_code(self, message, code):
      await message.click(data=code)

   def get_buttons_from_menu(self, update: UpdateEditMessage):
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

   def try_get_button_index_by_text(self, buttons, text):
      try:
         return list(map(lambda x: x['text'] , buttons)).index(text)
      except:
         return None



# phone = os.environ.get("PHONE")
# session = os.environ.get("SESSION")
# api_id = os.environ.get("API_ID") 
# api_hash = os.environ.get("API_HASH")
# code_file = os.environ.get("CODE_FILE")








# async def main(client: TelegramClient):
#    interactor =  MaestroInteractor(client)
#    await client.start(phone=phone, code_callback= lambda : getCodeFromFile(15))
#    async with client:
#       await interactor.send_command(client, 'monitor')
#       await client.run_until_disconnected()      
#       #await client.disconnect()      
   
# asyncio.run(main(TelegramClient(session, api_id, api_hash)))
