import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from telegram.ext import Updater

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(lineno)s',
    level=logging.INFO
)


def check_tokens():
    """Проверяем наличие всех данных в окружении."""
    list_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(list_tokens)


def send_message(bot, message):
    """Функция отправки сообщения при изменении статуса."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        message = 'Сообщение успешно отправлено.'
        logging.debug(message)
    except telegram.error.TelegramError:
        message = 'Не удалось отправить сообщение.'
        raise exceptions.CantSendMessage(message)


def get_api_answer(timestamp):
    """Получаем данные из ответа API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )
    except Exception as error:
        message = f'API сервис недоступен: {error}.'
        return message
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception('Страница недоступна')


def check_response(response):
    """Проверяем ответ на соответствие формату данных."""
    if type(response).__name__ == 'dict':
        if 'homeworks' not in response:
            raise exceptions.ValueDictNone(
                'Данные не соответствуют запросу, нет названия работы.'
            )
        if not response['current_date']:
            raise exceptions.ValueDictNone(
                'Данные не соответствуют запросу, нет текущей даты.'
            )
        if type(response['homeworks']).__name__ != 'list':
            message = 'Под ключом <homeworks> не список, как мы ожидали.'
            raise TypeError(message)
    else:
        raise TypeError('Данные пришли не формате словаря, как мы ожидали.')


def parse_status(homework):
    """Проверяем изменился ли статус проекта."""
    if not homework:
        message = 'Словарь пришел пустой. А мы ожидали словарь с данными.'
        raise ValueError(message)

    if 'homework_name' not in homework:
        raise exceptions.ValueDictNone(
            'Данные не соответствуют запросу, нет ключа: homework_name.'
        )
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise exceptions.ValueDictNone(
            'Нет подходящего статуса в существующих для твоей работы.'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'В окружении не хватает токенов. Мне нужно больше токенов!!!!'
        )
        sys.exit(1)
    message, error_check = '', ''
    updater = Updater(token=TELEGRAM_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response.get('homeworks')
            message_check = parse_status(homework[0])
            if message_check != message:
                message = message_check
                send_message(bot, message)
        except Exception as error:
            logging.error(error, exc_info=True)
            if error_check != error:
                error_check = error
                try:
                    send_message(bot, error_check)
                except exceptions.CantSendMessage:
                    logging.error(
                        'Я не смог отправить тебе сообщение об ошибке.',
                        exc_info=True
                    )
        time.sleep(RETRY_PERIOD)
        updater.start_polling()
        updater.idle()


if __name__ == '__main__':
    main()
