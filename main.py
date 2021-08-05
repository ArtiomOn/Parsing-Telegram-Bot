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
from aiogram.types import ParseMode
from bs4 import BeautifulSoup
from googletrans import Translator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.util import asyncio
from tabulate import tabulate

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
    shop = State()


@dp.message_handler(commands=['start'])
async def bot_send_greeting(message: types.Message):
    await bot.send_message(message.chat.id, f'Привіт, я Піксель, найменший член родини, '
                                            f'але я служу так, що багатьом позаздрять 😊\n\n'
                                            f'З чого почнемо <b>{message.chat.first_name}</b>? '
                                            f'Підказка - /menu', parse_mode='html')


@dp.message_handler(commands=['menu'])
async def bot_create_main_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/repeat_by_me'),
            types.KeyboardButton('/notes'),
        ],
        [
            types.KeyboardButton('/additional_functionality'),
            types.KeyboardButton('/product_search'),
        ]
    ])

    await bot.send_message(message.chat.id, 'Menu:', reply_markup=markup)


@dp.message_handler(commands=['exit'])
async def bot_create_command_exit_main_menu(message: types.Message):
    await bot_create_main_menu(message)


@dp.message_handler(commands=['repeat_by_me'], state='*')
async def bot_create_command_repeat(message: types.Message):
    logging.info(f'The bot started repeating after the user {message.from_user.id}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/cancel_repetition')
        ]
    ], one_time_keyboard=True)
    await Form.repeat.set()
    await message.reply('Write something:', reply_markup=markup)


@dp.message_handler(state='*', commands='cancel_repetition')
async def bot_handler_cancel_repeat(message: types.Message, state: FSMContext):
    logging.info(f'Cancelling repeating by user {message.from_user.id}')
    await state.finish()
    await message.reply('Successfully')
    await bot_create_main_menu(message)


@dp.message_handler(state=Form.repeat)
async def bot_handler_repeat(message: types.Message):
    await message.reply(message.text)


@dp.message_handler(state='*', commands='notes')
async def bot_create_note_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/create_note'),
            types.KeyboardButton('/last_note'),
        ],
        [
            types.KeyboardButton('/search_note'),
        ],
        [
            types.KeyboardButton('/exit')
        ]
    ])
    await message.reply('Choose:', reply_markup=markup)


@dp.message_handler(state='*', commands='additional_functionality')
async def bot_create_additional_features(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/random_joke'),
            types.KeyboardButton('/translate_text')
        ],
        [
            types.KeyboardButton('/exit')
        ]
    ])
    await message.reply('Choose:', reply_markup=markup)


@dp.message_handler(state='*', commands='create_note')
async def bot_create_command_save_note(message: types.Message):
    logging.info(f'The note was created by the user {message.from_user.id}')
    await Form.note.set()
    await bot.send_message(
        message.chat.id,
        "Write a note and I'll record it\n(P.S: I swear I won't show anyone 😁)",
        parse_mode='html'
    )


@dp.message_handler(state=Form.note)
async def bot_handler_save_note(message: types.Message, state: FSMContext):
    logging.info(f'The note was saved for the user {message.from_user.id}')
    query = Note(user_id=message.from_user.id, note=message.text, created_at=datetime.datetime.now())
    session.add(query)
    session.commit()
    await state.finish()
    await bot.send_message(message.chat.id, 'Recorded, thank you 😉')


@dp.message_handler(commands='last_note', state='*')
async def bot_view_last_note(message: types.Message, state: FSMContext):
    logging.info(f'The last note was viewed by the user {message.from_user.id}')
    try:
        note_data = session.query(Note).filter(Note.user_id == message.from_user.id).order_by(Note.id.desc()).first()
        await bot.send_message(message.chat.id, note_data.note)
        await state.finish()
    except AttributeError as e:
        await bot.send_message(message.chat.id, f"You don't have any notes yet\n")
        logging.info(f' Error: {e} with user. Error occurred with user: {message.from_user.id}')


@dp.message_handler(commands='random_joke')
async def bot_handler_random_joke(message: types.Message):
    logging.info(f'The joke was created by the user {message.from_user.id}')
    url = r"https://official-joke-api.appspot.com/random_joke"
    request = requests.get(url)
    data = json.loads(request.text)
    await bot.send_message(message.chat.id, 'Your joke 😂')
    await asyncio.sleep(1)
    await bot.send_message(message.chat.id, data["setup"])
    await asyncio.sleep(2)
    await bot.send_message(message.chat.id, data['punchline'])


@dp.message_handler(state='*', commands='translate_text')
async def bot_create_command_translate(message: types.Message):
    await bot.send_message(message.chat.id, 'Rules:\n1.The language must be written in English<b>!</b>\n'
                                            '<b>Example</b>: Russian or ru\n'
                                            '2.Almost all languages of the world are available<b>!</b>\n'
                                            '3.If you write the wrong language the translation will be <b>Wrong!</b>\n'
                                            '4.Text must not exceed 1000 characters<b>!</b>', parse_mode='html')
    await message.reply('In what language your text is written?')
    await TranslateForm.lang_src.set()


@dp.message_handler(state=TranslateForm.lang_src)
async def handler_translate_lang_src(message: types.Message, state: FSMContext):
    lang_src = message.text
    await state.update_data({'lang_src': lang_src})
    await message.reply('In which language do you want to translate it?')
    await TranslateForm.lang_dst.set()


@dp.message_handler(state=TranslateForm.lang_dst)
async def handler_translate_lang_dst(message: types.Message, state: FSMContext):
    lang_dst = message.text
    await state.update_data({'lang_dst': lang_dst})

    await bot.send_message(message.chat.id, 'Write your text:\n'
                                            '<b>Warning - Text must not exceed 1000 characters</b>', parse_mode='html')
    await TranslateForm.execute.set()


@dp.message_handler(state=TranslateForm.execute)
async def handler_translate_execute(message: types.Message, state: FSMContext):
    translator = Translator()
    state_data = await state.get_data()
    lang_src = state_data.get('lang_src')
    lang_dst = state_data.get('lang_dst')
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
        await bot.send_message(message.chat.id, f'You input the wrong language - {e}')
        await bot_create_command_translate(message)
        logging.info(f'User {message.from_user.id} translated the text')


@dp.inline_handler(lambda query: len(query.query) > 0, state='*')
async def bot_inline_handler(query: types.InlineQuery):
    if query.query.lower().split(':')[0] == 'notes':
        note_title, save_note_data = await bot_handler_note(query)
        await bot.answer_inline_query(note_title, save_note_data, cache_time=False)
    elif query.query.lower().split(':')[0] == 'product':
        product_title, save_product_data = await bot_handler_goods(query)
        await bot.answer_inline_query(product_title, save_product_data, cache_time=False)
        await Form.shop.set()


@dp.message_handler(commands=['search_note'])
async def bot_create_command_note(message: types.Message):
    logging.info(f'A user has started searching for notes {message.from_user.id}')
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Search', switch_inline_query_current_chat='notes:'))
    await bot.send_message(message.chat.id, "Please:", reply_markup=keyboard)


@dp.inline_handler()
async def bot_handler_note(note_title):
    title = note_title.query.lower().split(':')[-1]
    note_data = session.query(Note).filter((Note.note.contains(title)) &
                                           (Note.user_id == note_title.from_user.id)).limit(20)
    save_note_data = []
    for i in note_data:
        content = types.InputTextMessageContent(
            message_text=f'Your record: {i.note}',
        )

        data = types.InlineQueryResultArticle(
            id=i.id,
            title=i.note,
            description=f'The record was created: {i.created_at}',
            input_message_content=content
        )
        save_note_data.append(data)
    return note_title.id, save_note_data


@dp.message_handler(commands='product_search')
async def bot_create_command_goods(message: types.Message):
    logging.info(f'User {message.from_user.id} started searching for products')
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Search', switch_inline_query_current_chat='product:'))
    await bot.send_message(message.chat.id, "Please:", reply_markup=keyboard)


@dp.inline_handler()
async def bot_handler_goods(product_title):
    i = 0
    page = 1
    elements = 0

    product = product_title.query.lower().split(':')[-1]
    save_product_data = []
    while True:
        r = requests.get(f'https://e-catalog.md/ro/search?q={product}&page={page}')
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

                    i += 1
                    elements += 1

                    content = types.InputTextMessageContent(
                        message_text=title[0].get('href')
                    )

                    data = types.InlineQueryResultArticle(
                        id=str(i),
                        title=f'Title: {title[0].text}',
                        description=f'Price: {price}',
                        input_message_content=content,
                        thumb_url=image[0].get('src'),
                        thumb_width=48,
                        thumb_height=48

                    )
                    save_product_data.append(data)
            page += 1
        return product_title.id, save_product_data


@dp.message_handler(state=Form.shop)
async def bot_detail_specifications_goods(message: types.Message, state: FSMContext):
    column = []
    row = []
    table = []

    detail_goods = message.text
    await state.update_data({'detail_goods': detail_goods})
    data = await state.get_data()
    data = data.get('detail_goods')

    try:
        request = requests.get(data)
    except Exception as e:
        logging.info(f'User with id {message.from_user.id} violated parsing processing. Error: {e}')
        await bot.send_message(message.chat.id, '🚨Please do not write in the chat while the process is running!🚨')
        await state.finish()
    else:
        html_content = BeautifulSoup(request.text, 'html.parser')
        await bot.send_message(message.chat.id, 'One second, collecting information...')
        await asyncio.sleep(1)
        for detail_data in html_content.select('.spec > .spec__section > .spec__row'):
            title = detail_data.select('.spec__name')
            detail = detail_data.select('.spec__value')
            row.append(title[0].text)
            column.append(detail[0].text)

        headers = ["Category", "Description"]

        for i in range(len(column)):
            table.append([row[i], column[i]])
        data = tabulate(tabular_data=table, headers=headers, tablefmt="fancy_grid")
        await bot.send_message(message.chat.id, 'Product characteristics:')
        await bot.send_message(message.chat.id, f'```{data}```', parse_mode="Markdown")
        await bot_detail_reviews_goods(message, state)


@dp.message_handler(state=Form.shop)
async def bot_detail_reviews_goods(message: types.Message, state: FSMContext):
    comments_author = []
    comments_content = []
    comments_date = []
    formatted_text = []
    tb = []

    data_state = await state.get_data()
    data = data_state.get('detail_goods')

    try:
        request = requests.get(data)
    except Exception as e:
        logging.info(f'User with id {message.from_user.id} violated parsing processing. Error: {e}')
        await bot.send_message(message.chat.id, '🚨Please do not write in the chat while the process is running!🚨')
        await state.finish()
    else:
        html_content = BeautifulSoup(request.text, 'html.parser')

        def group_by_length(words, length=100):
            current_index = 0
            current_length = 0
            for k, word in enumerate(words):
                current_length += len(word) + 1
                if current_length > length:
                    yield words[current_index:k]
                    current_index = k
                    current_length = len(word)
            else:
                yield words[current_index:]

        for detail_comments in html_content.select('.reviews-list__content > .reviews-list__item'):
            author = detail_comments.select('.review > .review__content > .review__author')
            text = detail_comments.select('.review > .review__content > .review__text')
            date = detail_comments.select('.review > .review__content > .review__date')
            comments_author.append(author[0].text)
            comments_content.append(text[0].text)
            comments_date.append(date[0].text)
            formatted_text.append('\n'.join(' '.join(row) for row in group_by_length(text[0].text.split(' '), 50)))
        await bot.send_message(message.chat.id, 'Reviews:')
        if not comments_author:
            await bot.send_message(message.chat.id, 'Unfortunately, this product has no reviews! 😢')
            await bot_detail_offer_goods(message, state)
        else:
            for i in range(len(comments_content)):
                tb.append([comments_author[i], comments_date[i], formatted_text[i]])

            data = tabulate(tabular_data=tb, tablefmt="fancy_grid", headers=["User", "Date", "Content"],
                            stralign='left')

            await bot.send_message(message.chat.id, f'```{data}```', parse_mode="Markdown")
            await bot_detail_offer_goods(message, state)


@dp.message_handler(state=Form.shop)
async def bot_detail_offer_goods(message: types.Message, state: FSMContext):
    shop_name = []
    shop_price = []
    shop_link = []
    link_data = []
    count = 0

    data_state = await state.get_data()
    data = data_state.get('detail_goods')

    try:
        request = requests.get(data)
        await state.finish()
    except Exception as e:
        logging.info(f'User with id {message.from_user.id} violated parsing processing. Error: {e}')
        await bot.send_message(message.chat.id, '🚨Please do not write in the chat while the process is running!🚨')

    else:
        html_content = BeautifulSoup(request.text, 'html.parser')
        for detail_shop in html_content.select('.listing_container > .available'):
            image = detail_shop.select('.item_info > .item_merchant > .merchant_logo > img')
            price = detail_shop.select('.item_price > .item_basic_price')
            link = detail_shop.select('.item_actions > a')

            shop_name.append(image[0].get('alt'))
            shop_price.append(price[0].text)
            shop_link.append(link[0].get('href'))

        await bot.send_message(message.chat.id, 'Offers:')

        for i in range(len(shop_name)):
            count += 1
            link_data.append(f"<a href='{shop_link[i]}'>{count}. {shop_name[i]} - {shop_price[i].strip()} </a>")

        link_data = "\n".join(link_data)
        await bot.send_message(message.chat.id, text=''.join(link_data),
                               parse_mode=ParseMode.HTML, disable_web_page_preview=True)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
