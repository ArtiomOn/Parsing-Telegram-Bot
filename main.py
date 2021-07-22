import os
import dotenv
import logging

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from sqlalchemy.orm import sessionmaker

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
                        f'Готов тебе служить - <b>{message.from_user.first_name}</b>', parse_mode='html')


@dp.message_handler(commands=['choice'])
async def make_choice(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            types.KeyboardButton('/повторяй_за_мной'),
            types.KeyboardButton('/отключить_повторение'),
        ],
        [
            types.KeyboardButton('/создать_заметку'),
            types.KeyboardButton('/мои_заметки'),
        ],
        [
            types.KeyboardButton('/will')
        ],
    ])

    await bot.send_message(message.chat.id, 'Выбирай то что тебе нравится', reply_markup=markup)


@dp.message_handler(state='*', commands='отключить_повторение')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def handler_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    await state.finish()
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands=['повторяй_за_мной'], state='*')
async def command_repeat(message: types.Message):
    await Form.repeat.set()
    await message.reply('Напиши что-то:')


@dp.message_handler(state=Form.repeat)
async def handler_repeat(message: types.Message):
    await message.reply(message.text)


@dp.message_handler(state='*', commands='создать_заметку')
async def command_note(message: types.Message):
    await Form.note.set()
    await bot.send_message(
        message.chat.id,
        'Напишите заметку и я её запишу\n(P.S: клянусь что никому не покажу 😁)',
        parse_mode='html'
    )


@dp.message_handler(commands='мои_заметки', state='*')
async def command_my_note(message: types.Message, state: FSMContext):
    session = sessionmaker(bind=database_dsn)()
    my_note = session.query(Note).filter(Note.user_id == message.from_user.id).order_by(Note.id.desc()).first()
    await bot.send_message(message.from_user.id, my_note.note)
    await state.finish()


@dp.message_handler(state=Form.note)
async def save_note(message: types.Message, state: FSMContext):
    session = sessionmaker(bind=database_dsn)()
    query = Note(user_id=message.from_user.id, note=message.text)
    session.add(query)
    session.commit()
    await state.finish()
    await bot.send_message(message.from_user.id, 'Записал, спасибо за доверие  😉')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
