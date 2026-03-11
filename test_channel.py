# test_channel.py
import asyncio
from telegram import Bot

BOT_TOKEN = "8559871675:AAHQ93Ov3g5wK3b8R8akReOeFYsIXjEG50M"
CHANNEL_ID = "@free_crypto_trading_bot"

async def test():
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ Test message from CryptoSignal Bot!"
        )
        print("SUCCESS — message sent to channel!")
    except Exception as e:
        print("FAILED — {}".format(e))

asyncio.run(test())