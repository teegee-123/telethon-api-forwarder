import datetime
import os


class ReportHandler:

    def __init__(self, client) -> None:
        self.maestro_username = os.environ.get("TRADEBOTNAME")
        self.client = client


    async def get_trade_report(self, event):        
        message_text = event.message.message
        report_time = 8
        try:
            report_time = int(message_text.lower().split(" ")[1].strip() or 8)
        except:
            print("Invalid args")
        # at most 2 days worth
        if(report_time > 48):
            report_time = 8
        num_trades = 0
        total_percent = 0
        won_trades = 0
        loss_trades = 0
        now = datetime.datetime.today()
        date_from =  now - datetime.timedelta(hours=report_time) 
        print(f"date_from {date_from}")
        async for message in self.client.iter_messages(self.maestro_username, search='⚠️ Initiating auto'):
            if(date_from.replace(tzinfo=None) <= message.date.replace(tzinfo=None)):
                # print(message.message, message.date)
                percent_on_trade = round(float(message.message.split("has been met (")[1].split("%")[0]), 2)
                num_trades += 1
                if(percent_on_trade > 0):
                    won_trades += 1
                else:
                    loss_trades += 1
                total_percent += percent_on_trade
        
        response_message = f'Total trades in the passed {report_time} hours: **{num_trades}**\n'
        response_message  += f'P/L in this period: **{round(float(total_percent), 2)}**\n'
        response_message  += f'Won: **{won_trades}**\n'
        response_message  += f'Loss: **{loss_trades}**\n'
        return response_message

