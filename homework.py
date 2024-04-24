import logging
import os
import time
import sys
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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


def check_message(message_last, message, bot):
    """Проверяем новое ли сообщение, чтобы бот не дублировал информацию."""
    if message_last != message:
        message_last = message
        send_message(bot, message_last)
    return message_last


def check_tokens():
    """Проверяем наличие всех данных в окружении."""
    list_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(list_tokens)


def send_message(bot, message):
    """Функция отправки сообщения при изменении статуса."""
    try:
        logging.debug('Пытаемся отправить сообщение.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено.')
    except telegram.error.TelegramError:
        raise exceptions.CantSendMessage(
            'Не удалось отправить сообщение.'
        )


def get_api_answer(timestamp):
    """Получаем данные из ответа API."""
    try:
        logging.debug('Пытаемся получить API ответ.')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )
    except Exception as error:
        return f'API сервис недоступен: {error}.'
    if response.status_code == HTTPStatus.OK:
        return response.json()
    raise Exception('Страница недоступна')


def check_response(response):
    """Проверяем ответ на соответствие формату данных."""
    if not isinstance(response, dict):
        raise TypeError('Данные пришли не формате словаря, как мы ожидали.')
    if 'homeworks' not in response:
        raise exceptions.ValueDictNone(
            'Данные не соответствуют запросу, нет названия работы.'
        )
    if 'current_date' not in response:
        raise exceptions.ValueDictNone(
            'Данные не соответствуют запросу, нет текущей даты.'
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Под ключом <homeworks> не список, как мы ожидали.'
        )


def parse_status(homework):
    """Проверяем изменился ли статус проекта."""
    if 'homework_name' not in homework:
        raise exceptions.ValueDictNone(
            'Данные не соответствуют запросу, нет ключа: homework_name.'
        )
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise exceptions.ValueDictNone(
            'Данные не соответствуют запросу, нет ключа: status.'
        )
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
    message_check, message, error_check = '', '', ''
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response.get('homeworks')
            message = parse_status(homework[0])
        except Exception as error:
            error_check = check_message(error_check, error, bot)
            logging.error(message, exc_info=True)
        finally:
            try:
                message_check = check_message(message_check, message, bot)
            except exceptions.CantSendMessage:
                logging.error(
                    'Я не смог отправить тебе сообщение об ошибке.',
                    exc_info=True
                )
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
