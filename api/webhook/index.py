from bot import dp, bot
from aiogram import types
from aiogram.dispatcher.webhook import SendMessage

async def handler(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}
