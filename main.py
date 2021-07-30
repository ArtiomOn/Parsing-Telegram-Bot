import datetime
import json
import logging
import os

import dotenv
import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from bs4 import BeautifulSoup
from googletrans import Translator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.util import asyncio

from models import database_dsn, Note, Translation
from graphs import draw_font_table

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
    magazine = State()


technical_site = 'site:darwin.md'


@dp.message_handler(commands=['start'])
async def send_greeting(message: types.Message):
    sti = open('static/car.gif', 'rb')
    await bot.send_sticker(message.chat.id, sti)
    me = await bot.get_me()
    await message.reply(f'Привет, я <b>{me.first_name}</b>\n'
                        f'Готов тебе служить - <b>{message.chat.first_name}</b>', parse_mode='html')


@dp.message_handler(commands=['menu'])
async def create_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/повторяй_за_мной'),
            types.KeyboardButton('/заметки'),
        ],
        [
            types.KeyboardButton('/случайная_шутка'),
            types.KeyboardButton('/переведи_текст'),
        ],
        [
            types.KeyboardButton('/поиск_в_магазинах')
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
        ],
        [
            types.KeyboardButton('/последняя_заметка'),
        ],
        [
            types.KeyboardButton('/поиск_заметок'),
        ],
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


@dp.message_handler(state='*', commands='переведи_текст')
async def handler_translate(message: types.Message):
    await bot.send_message(message.chat.id, 'Правила:\n1.Язык должен быть написан на английском<b>!</b>\n'
                                            '<b>Пример</b>: Russian или ru\n'
                                            '2.Доступны почти все языки мира<b>!</b>\n'
                                            '3.Если вы напишите неправилный язык то перевод будет <b>Неверный!</b>\n'
                                            '4.Текст не должен превышать 1000 символов<b>!</b>',
                           parse_mode='html')
    await message.reply('На каком языке написан ваш текст?')
    await TranslateForm.lang_src.set()


@dp.message_handler(state=TranslateForm.lang_src)
async def handler_translate_lang_src(message: types.Message, state: FSMContext):
    lang_src = message.text
    await state.update_data({'lang_src': lang_src})

    await message.reply('В какой язык вы хотите его перевести?')
    await TranslateForm.lang_dst.set()


@dp.message_handler(state=TranslateForm.lang_dst)
async def handler_translate_lang_dst(message: types.Message, state: FSMContext):
    lang_dst = message.text
    await state.update_data({'lang_dst': lang_dst})

    await bot.send_message(message.chat.id, 'Пишите текст:\n'
                                            '<b>Warning - (Текст не должен превышать 1000 символов)</b>',
                           parse_mode='html')
    await TranslateForm.execute.set()


@dp.message_handler(state=TranslateForm.execute)
async def handler_translate_execute(message: types.Message, state: FSMContext):
    translator = Translator()
    data = await state.get_data()
    lang_src = data.get('lang_src')
    lang_dst = data.get('lang_dst')
    try:
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
    except ValueError as e:
        await bot.send_message(message.chat.id, f'Вы ввели неверный язык - {e}')
        await handler_translate(message)


@dp.inline_handler(lambda query: len(query.query) > 0, state='*')
async def view_data(query: types.InlineQuery):
    if query.query.lower().split(':')[0] == 'notes':
        note_title, save_note_data = await handler_notes(query)
        await bot.answer_inline_query(note_title, save_note_data, cache_time=False)
    elif query.query.lower().split(':')[0] == 'shop':
        product_title, save_product_data = await handler_goods(query)
        await bot.answer_inline_query(product_title, save_product_data, cache_time=False)
        await Form.magazine.set()


@dp.message_handler(commands=['поиск_заметок'])
async def command_notes(message: types.Message):
    logging.info(f'A user has started searching for notes {message.from_user.id}')
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Поиск', switch_inline_query_current_chat='notes:'))
    await bot.send_message(message.chat.id, "Поиск заметок:", reply_markup=keyboard)


@dp.inline_handler()
async def handler_notes(note_title):
    name = note_title.query.lower().split(':')[-1]
    note_data = session.query(Note).filter((Note.note.contains(name)) &
                                           (Note.user_id == note_title.from_user.id)).limit(20)
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
        save_note_data.append(data)
    return note_title.id, save_note_data


@dp.message_handler(commands='поиск_в_магазинах')
async def command_goods(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Поиск', switch_inline_query_current_chat='shop:'))
    await bot.send_message(message.chat.id, "Поиск магазинов:", reply_markup=keyboard)


@dp.inline_handler()
async def handler_goods(product_title):
    product_name = product_title.query.lower().split(':')[-1]
    save_product_data = []
    i = 0
    page = 1
    elements = 0
    while True:
        r = requests.get(f'https://e-catalog.md/ro/search?q={product_name}&page={page}')
        html = BeautifulSoup(r.text, 'html.parser')
        items = html.select('.products-list__body > .products-list__item')
        if len(items):
            for el in items:
                if elements == 20:
                    break
                else:
                    image = el.select('.product-card > .product-card__image > a > img')
                    title = el.select('.product-card > .product-card__info > .product-card__name > a')
                    price = el.select('.product-card > .product-card__actions > .product-card__prices > span')

                    if not price:
                        price = 'Not found'
                    else:
                        price = price[0].text

                    content = types.InputTextMessageContent(
                        message_text=title[0].get('href')
                    )
                    i += 1
                    elements += 1
                    data = types.InlineQueryResultArticle(
                        id=str(i),
                        title=f'Название: {title[0].text}',
                        description=f'Цена: {price}',
                        input_message_content=content,
                        thumb_url=image[0].get('src'),
                        thumb_width=48,
                        thumb_height=48

                    )
                    save_product_data.append(data)
                    continue
            page += 1
        return product_title.id, save_product_data


@dp.message_handler(state=Form.magazine)
async def detail_good(message: types.Message, state: FSMContext):
    detail_goods = message.text
    await state.update_data({'detail_goods': detail_goods})
    data = await state.get_data()

    data = data.get('detail_goods')
    try:
        request = requests.get(data)
        html_content = BeautifulSoup(request.text, 'html.parser')
        await bot.send_message(message.chat.id, 'Одну секунду, собираю информацию...')
        await asyncio.sleep(2)
    except Exception as e:
        await state.finish()
        logging.info(f'Basic search error with user {message.from_user.id}. GREEN code - {e}')
    else:
        column = []
        row = []
        for detail_data in html_content.select(
                '.product-tabs > .product-tabs__content > .product-tabs__pane > .spec > .spec__section > .spec__row'):
            title = detail_data.select('.spec__name')
            detail = detail_data.select('.spec__value')
            await bot.send_message(message.chat.id, f'{title[0].text} = {detail[0].text}')
            row.append(title[0].text)
            column.append(detail[0].text)
            await state.finish()
            continue
        draw_font_table(None, row, column)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
