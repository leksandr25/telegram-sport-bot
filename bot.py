import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN environment variable is required')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-memory session storage for admin flow and events storage
sessions = {}  # user_id -> {step, data, chat_id}
events = {}    # (chat_id, message_id) -> {title, datetime, description, yes:set, no:set}

async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ('administrator', 'creator')
    except Exception:
        return False

@dp.message(Command('event'))
async def cmd_event(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Only in groups/supergroups
    if message.chat.type not in ('group', 'supergroup'):
        await message.reply('Команду потрібно виконувати у групі.')
        return

    if not await is_admin(chat_id, user_id):
        await message.reply('Тільки адміністратор може створювати події.')
        return

    sessions[user_id] = {'step': 1, 'data': {}, 'chat_id': chat_id}
    await message.reply('🔹 Введіть назву заходу:')

@dp.message()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in sessions:
        return  # ignore unrelated messages

    session = sessions[user_id]
    text = message.text.strip()

    # Step 1: title
    if session['step'] == 1:
        session['data']['title'] = text
        session['step'] = 2
        await message.reply('🕒 Введіть дату та час (наприклад: Завтра 18:00):')
        return

    # Step 2: datetime
    if session['step'] == 2:
        session['data']['datetime'] = text
        session['step'] = 3
        await message.reply('📍 Введіть опис (необовʼязково) або напишіть "-" для пропуску:')
        return

    # Step 3: description
    if session['step'] == 3:
        session['data']['description'] = '' if text == '-' else text
        session['step'] = 4
        data = session['data']
        preview = f"""Підтвердити підготовку події?\n\n📌 *{data['title']}*\n🕒 {data['datetime']}\n"""
        if data['description']:
            preview += f"📍 {data['description']}\n"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Підтвердити', callback_data=f'CONFIRM:{user_id}'),
             InlineKeyboardButton(text='❌ Скасувати', callback_data=f'CANCEL:{user_id}')]
        ])
        await message.reply(preview, parse_mode='Markdown', reply_markup=kb)
        return

@dp.callback_query(lambda c: True)
async def callbacks(cb: types.CallbackQuery):
    data = cb.data or ''
    user_id = cb.from_user.id

    if data.startswith('CONFIRM:'):
        owner_id = int(data.split(':',1)[1])
        if owner_id != user_id:
            await cb.answer('Тільки ініціатор може підтвердити.', show_alert=True)
            return
        session = sessions.get(owner_id)
        if not session:
            await cb.answer('Сесія не знайдена або вже закінчена.', show_alert=True)
            return
        d = session['data']
        chat_id = session['chat_id']
        # send event message to group
        text = f"🎯 *{d['title']}*\n🕒 {d['datetime']}\n"
        if d['description']:
            text += f"📍 {d['description']}\n"
        text += '\nХто буде?'

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        sent = await bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='👍 Буду (0)', callback_data=f'JOIN:{chat_id}:0'), InlineKeyboardButton(text='👎 Не буду (0)', callback_data=f'NO:{chat_id}:0')]
        ]))

        # store event by message id
        events[(chat_id, sent.message_id)] = {
            'title': d['title'], 'datetime': d['datetime'], 'description': d['description'], 'yes': set(), 'no': set()
        }

        # edit original confirmation message
        try:
            await cb.message.edit_text('Подію опубліковано ✅')
        except Exception:
            pass

        del sessions[owner_id]
        await cb.answer()
        return

    if data.startswith('CANCEL:'):
        owner_id = int(data.split(':',1)[1])
        if owner_id != user_id:
            await cb.answer('Тільки ініціатор може скасувати.', show_alert=True)
            return
        try:
            await cb.message.edit_text('❌ Подію скасовано')
        except Exception:
            pass
        if owner_id in sessions:
            del sessions[owner_id]
        await cb.answer()
        return

    # Join / No buttons from event message
    if data.startswith('JOIN:') or data.startswith('NO:'):
        parts = data.split(':')
        action = parts[0]
        try:
            chat_id = int(parts[1])
            # message_id is available on cb.message.message_id
            msg_id = cb.message.message_id
        except Exception:
            await cb.answer('Помилка даних', show_alert=True)
            return

        key = (chat_id, msg_id)
        if key not in events:
            await cb.answer('Подія не знайдена', show_alert=True)
            return

        ev = events[key]
        user = cb.from_user
        uid = user.id
        if action == 'JOIN':
            # move from no to yes if present
            ev['no'].discard(uid)
            ev['yes'].add(uid)
        else:
            ev['yes'].discard(uid)
            ev['no'].add(uid)

        yes_count = len(ev['yes'])
        no_count = len(ev['no'])

        # update buttons text
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f'👍 Буду ({yes_count})', callback_data=f'JOIN:{chat_id}:0'), InlineKeyboardButton(text=f'👎 Не буду ({no_count})', callback_data=f'NO:{chat_id}:0')]
        ])

        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

        await cb.answer()
        return

async def handle_update(update: dict):
    # Aiogram expects JSON update dict
    await dp.feed_raw_update(bot, update)
