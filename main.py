import datetime
import json
import os

import dotenv
import logging
import requests

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from sqlalchemy.orm import sessionmaker
from sqlalchemy.util import asyncio

from models import database_dsn, Note

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()

bot = Bot(token=os.getenv('TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class Form(StatesGroup):
    repeat = State()
    note = State()


@dp.message_handler(commands=['start'])
async def send_greeting(message: types.Message):
    sti = open('static/AnimatedSticker.tgs', 'rb')
    await bot.send_sticker(message.chat.id, sti)
    me = await bot.get_me()
    await message.reply(f'Привет, я великий <b>{me.first_name}</b>\n'
                        f'Готов тебе служить - <b>{message.chat.first_name}</b>', parse_mode='html')


@dp.message_handler(commands=['choice'])
async def make_choice(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/повторяй_за_мной'),
        ],
        [
            types.KeyboardButton('/создать_заметку'),
            types.KeyboardButton('/последняя_заметка'),
        ],
        [
            types.KeyboardButton('/случайная_шутка'),
            types.KeyboardButton('/поиск_заметок')
        ],
    ])

    await bot.send_message(message.chat.id, 'Выбирай то что тебе нравится', reply_markup=markup)


@dp.message_handler(state='*', commands='отключить_повторение')
async def handler_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    await state.finish()
    await message.reply('Успешно')


@dp.message_handler(commands=['повторяй_за_мной'], state='*')
async def command_repeat(message: types.Message):
    logging.info(f'The bot started repeating after the user {message.from_user.id}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[types.KeyboardButton('/отключить_повторение')]],
                                       one_time_keyboard=True)
    await Form.repeat.set()
    await message.reply('Напиши что-то:', reply_markup=markup)


@dp.message_handler(state=Form.repeat)
async def handler_repeat(message: types.Message):
    await message.reply(message.text)


@dp.message_handler(state='*', commands='создать_заметку')
async def command_note(message: types.Message):
    logging.info(f'The note was created by the user {message.from_user.id}')
    await Form.note.set()
    await bot.send_message(
        message.chat.id,
        'Напишите заметку и я её запишу\n(P.S: клянусь что никому не покажу 😁)',
        parse_mode='html'
    )


@dp.message_handler(commands='последняя_заметка', state='*')
async def command_my_note(message: types.Message, state: FSMContext):
    logging.info(f'The last note was viewed by the user {message.from_user.id}')
    try:
        session = sessionmaker(bind=database_dsn)()
        my_note = session.query(Note).filter(Note.user_id == message.from_user.id).order_by(Note.id.desc()).first()
        await bot.send_message(message.chat.id, my_note.note)
        await state.finish()
    except Exception as e:
        await bot.send_message(message.chat.id, f'У вас пока нет заметок\n'
                                                f'<b>For Admin</b> - <b>{e}</b>', parse_mode='html')


@dp.message_handler(state=Form.note)
async def save_note(message: types.Message, state: FSMContext):
    logging.info(f'The note was saved for the user {message.from_user.id}')
    session = sessionmaker(bind=database_dsn)()
    query = Note(user_id=message.from_user.id, note=message.text, created_at=datetime.datetime.now())
    session.add(query)
    session.commit()
    await state.finish()
    await bot.send_message(message.chat.id, 'Записал, спасибо за доверие  😉')


@dp.message_handler(commands='случайная_шутка')
async def handler_joke(message: types.Message):
    logging.info(f'The joke was created by the user {message.from_user.id}')
    url = r"https://official-joke-api.appspot.com/random_joke"
    data = requests.get(url)
    tt = json.loads(data.text)
    await bot.send_message(message.chat.id, 'Вот и твоя шутка')
    await asyncio.sleep(1)
    await bot.send_message(message.chat.id, tt["setup"])
    await asyncio.sleep(3)
    await bot.send_message(message.chat.id, tt['punchline'])


@dp.message_handler(commands=['поиск_заметок'])
async def command_choice(message: types.Message):
    logging.info(f'A user has started searching for notes {message.from_user.id}')
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Поиск', switch_inline_query_current_chat=''))
    await bot.send_message(message.chat.id, "Поиск заметок:", reply_markup=keyboard)


@dp.inline_handler()
async def handler_choice(query: types.InlineQuery):
    name = query.query.lower()
    session = sessionmaker(bind=database_dsn)()
    note_data = session.query(Note).filter((Note.note.contains(name)) & (Note.user_id == query.from_user.id)).limit(20)
    notes = []
    for i in note_data:
        content = types.InputTextMessageContent(
            message_text=f'Твоя запись: {i.note}',
        )

        data = types.InlineQueryResultArticle(
            id=i.id,
            title=i.note,
            description=f'Запись была создана {i.created_at}',
            input_message_content=content
        )
        notes.append(data)
    await bot.answer_inline_query(inline_query_id=query.id, results=notes, cache_time=False)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
