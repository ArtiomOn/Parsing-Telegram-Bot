import datetime
import json
import os

import dotenv
import logging
import requests

from sqlalchemy.orm import sessionmaker
from sqlalchemy.util import asyncio
from googletrans import Translator
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram import Bot, Dispatcher, executor, types

from models import database_dsn, Note, Translation

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()

bot = Bot(token=os.getenv('TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

session = sessionmaker(bind=database_dsn)()


class TranslateForm(StatesGroup):
    lang_src = State()
    lang_dst = State()
    execute = State()


class Form(StatesGroup):
    repeat = State()
    note = State()
    translate = State()


@dp.message_handler(commands=['start'])
async def send_greeting(message: types.Message):
    sti = open('static/AnimatedSticker.tgs', 'rb')
    await bot.send_sticker(message.chat.id, sti)
    me = await bot.get_me()
    await message.reply(f'Привет, я <b>{me.first_name}</b>\n'
                        f'Готов тебе служить - <b>{message.chat.first_name}</b>', parse_mode='html')


@dp.message_handler(commands=['menu'])
async def create_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/повторяй_за_мной'),
            types.KeyboardButton('/заметки'),
            types.KeyboardButton('/случайная_шутка'),
            types.KeyboardButton('/переведи_текст')
        ],
    ])

    await bot.send_message(message.chat.id, 'Меню:', reply_markup=markup)


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


@dp.message_handler(state='*', commands='заметки')
async def notes(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/создать_заметку'),
            types.KeyboardButton('/последняя_заметка'),
            types.KeyboardButton('/поиск_заметок'),
        ]
    ])
    await message.reply('Выберите:', reply_markup=markup)


@dp.message_handler(state='*', commands='создать_заметку')
async def command_note(message: types.Message):
    logging.info(f'The note was created by the user {message.from_user.id}')
    await Form.note.set()
    await bot.send_message(
        message.chat.id,
        'Напишите заметку и я её запишу\n(P.S: клянусь что никому не покажу 😁)',
        parse_mode='html'
    )


@dp.message_handler(state=Form.note)
async def save_note(message: types.Message, state: FSMContext):
    logging.info(f'The note was saved for the user {message.from_user.id}')
    query = Note(user_id=message.from_user.id, note=message.text, created_at=datetime.datetime.now())
    session.add(query)
    session.commit()
    await state.finish()
    await bot.send_message(message.chat.id, 'Записал, спасибо за доверие  😉')


@dp.message_handler(commands='последняя_заметка', state='*')
async def command_my_note(message: types.Message, state: FSMContext):
    logging.info(f'The last note was viewed by the user {message.from_user.id}')
    try:
        my_note = session.query(Note).filter(Note.user_id == message.from_user.id).order_by(Note.id.desc()).first()
        await bot.send_message(message.chat.id, my_note.note)
        await state.finish()
    except AttributeError as e:
        await bot.send_message(message.chat.id, f'У вас пока нет заметок\n')
        logging.info(f' Error: {e} with user. Error occurred with user: {message.from_user.id}')


@dp.message_handler(commands='случайная_шутка')
async def handler_joke(message: types.Message):
    logging.info(f'The joke was created by the user {message.from_user.id}')
    url = r"https://official-joke-api.appspot.com/random_joke"
    request = requests.get(url)
    data = json.loads(request.text)
    await bot.send_message(message.chat.id, 'Вот и твоя шутка')
    await asyncio.sleep(1)
    await bot.send_message(message.chat.id, data["setup"])
    await asyncio.sleep(3)
    await bot.send_message(message.chat.id, data['punchline'])


@dp.message_handler(commands=['поиск_заметок'])
async def command_notes(message: types.Message):
    logging.info(f'A user has started searching for notes {message.from_user.id}')
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Поиск', switch_inline_query_current_chat=''))
    await bot.send_message(message.chat.id, "Поиск заметок:", reply_markup=keyboard)


@dp.inline_handler()
async def handler_notes(query: types.InlineQuery):
    name = query.query.lower()
    note_data = session.query(Note).filter((Note.note.contains(name)) &
                                           (Note.user_id == query.from_user.id)).limit(20)
    save_note_data = []
    for i in note_data:
        content = types.InputTextMessageContent(
            message_text=f'Твоя запись: {i.note}',
        )

        data = types.InlineQueryResultArticle(
            id=i.id,
            title=i.note,
            description=f'Запись была создана: {i.created_at}',
            input_message_content=content
        )
        notes.append(data)
    await bot.answer_inline_query(inline_query_id=query.id, results=save_note_data, cache_time=False)


@dp.message_handler(commands='переведи_текст', state='*')
async def translate_data(message: types.Message):
    await Form.translate.set()
    await bot.send_message(message.chat.id, 'Готов переводить:\n<b>(Текст не должен превышать 1000 символов)</b>',
                           parse_mode='html')


@dp.message_handler(state=Form.translate)
async def handler_translate(message: types.Message, state: FSMContext):
    await message.reply('Input source language')
    await TranslateForm.lang_src.set()


@dp.message_handler(state=TranslateForm.lang_src)
async def handler_translate_lang_src(message: types.Message, state: FSMContext):
    lang_src = message.text
    await state.update_data({'lang_src': lang_src})

    await message.reply('Input destination language')
    await TranslateForm.lang_dst.set()


@dp.message_handler(state=TranslateForm.lang_dst)
async def handler_translate_lang_dst(message: types.Message, state: FSMContext):
    lang_dst = message.text
    await state.update_data({'lang_dst': lang_dst})

    await message.reply('Input text')
    await TranslateForm.execute.set()


@dp.message_handler(state=TranslateForm.execute, )
async def handler_translate_execute(message: types.Message, state: FSMContext):
    translator = Translator()

    data = await state.get_data()
    lang_src = data.get('lang_src')
    lang_dst = data.get('lang_dst')

    result = translator.translate(message.text[:1000], src=lang_src, dest=lang_dst)
    query = Translation(user_id=message.from_user.id,
                        original_text=message.text,
                        translation_text=result.text,
                        original_language=result.src,
                        translation_language=result.dest,
                        created_at=datetime.datetime.now(),
                        )
    session.add(query)
    session.commit()
    await bot.send_message(message.chat.id, result.text)
    await state.finish()


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
