from telethon import TelegramClient, errors
from telethon.tl.types import InputMessagesFilterPinned
from telethon.tl.functions.channels import GetForumTopicsRequest
import asyncio
from asyncio.exceptions import TimeoutError
from dotenv import load_dotenv
import json
import logging
import colorlog
import os
from rich.console import Console

console = Console()

# Загрузка переменных из .env
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
TELEGRAM_PASSWORD = os.getenv("TELEGRAM_PASSWORD")

# Настройка логгера
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(message)s'))

file_handler = logging.FileHandler("application.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = colorlog.getLogger('example')
logger.addHandler(handler)
logger.addHandler(file_handler)

# Устанавливаем минимальный уровень логирования
logger.setLevel(logging.INFO)

async def manual_authorization():
    client = TelegramClient("session", API_ID, API_HASH)
    await client.connect()

    # Проверяем, авторизован ли пользователь
    if not await client.is_user_authorized():
        logger.warning(f"Not authorized. Sending code to: {PHONE_NUMBER}")

        try:
            await client.send_code_request(PHONE_NUMBER)
        except errors.AuthRestartError:
            logger.warning("Telegram requested to restart the authorization process.")
            console.print("[bold yellow]Telegram is having internal issues. Please try again later.[/bold yellow]")
            return
        except Exception as e:
            logger.error(f"Failed to send code: {e}")
            return

        code = input("Enter the code you received: ")
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except errors.SessionPasswordNeededError:
            logger.warning("Password is required for 2FA. Enter your password:")
            password = TELEGRAM_PASSWORD or input("Enter your Telegram password: ")
            try:
                await client.sign_in(password=password)
                logger.info("Successfully signed in with password!")
            except Exception as e:
                logger.error(f"Error during password authorization: {e}")
                return
        except Exception as e:
            logger.error(f"Error during sign-in: {e}")
            return

    logger.info("Authorization successful!")
    return client
    
async def send_message_safe(client, chat_id, message_text):
    """
    Отправляет сообщение в чат с проверкой, что пользователь имеет права на отправку.

    :param client: TelegramClient.
    :param chat_id: ID чата или username.
    :param message_text: Текст сообщения.
    """
    try:
        # async for dialog in client.iter_dialogs():
        #    logger.info(f"Name: {dialog.name}, ID: {dialog.id}")
            
        # Преобразуем chat_id в int, если он строка
        if isinstance(chat_id, str):
            chat_id = int(chat_id)
        
        # Получаем Entity (сущность чата, группы или канала)
        try:
            entity = await client.get_entity(chat_id)
        except ValueError as e:
            logger.error(f"Chat {chat_id} not found: {e}")
            return False
            
        # Если это канал (broadcast)
        if getattr(entity, "broadcast", False):
            logger.warning(f"Chat {chat_id} is a channel. Sending messages may require admin rights.")
            # Просто отправляем сообщение, так как проверка разрешений недоступна
            await client.send_message(entity, message_text)
            logger.info(f"Message sent to channel {chat_id}: {message_text}")
            return True
            
        # Если это не канал, проверяем разрешения на отправку сообщений
        if hasattr(entity, "creator") and entity.creator:
            logger.info(f"You are the creator of the chat: {chat_id}.")
            can_send_messages = True
        elif hasattr(entity, "admin_rights") and entity.admin_rights:
            logger.info(f"You are an admin in the chat: {chat_id}.")
            can_send_messages = True
        else:
            permissions = await client.get_permissions(entity)
            can_send_messages = permissions.send_messages
            
        if not can_send_messages:
            logger.warning(f"No permission to send messages to {chat_id}")
            return False

        # Отправляем сообщение
        await client.send_message(entity, message_text)
        logger.info(f"Message sent to chat {chat_id}: {message_text}")
        return True

    except errors.ChatWriteForbiddenError:
        logger.error(f"Cannot send message to {chat_id}: Write permissions are forbidden.")
        return False
    except errors.RPCError as e:
        logger.error(f"RPCError while sending message to {chat_id}: {e}")
        return False
    except ValueError as e:
        logger.error(f"Chat {chat_id} not found: {e}")
        return False
    except Exception as e:
        logger.critical(f"Unexpected error while sending message to {chat_id}: {e}")
        raise
    
async def fetch_forum_topics(client, chat_id):
    """
    Получает список тем форума в указанном чате.
    :param client: Авторизованный TelegramClient.
    :param chat_id: ID чата с форумом.
    :return: Список тем форума.
    """
    topics = []
    try:
        logger.info(f"Fetching forum topics for chat: {chat_id}")
        response = await client(GetForumTopicsRequest(
            channel=chat_id,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=100  # Количество тем, которое нужно получить (максимум 100 за раз)
        ))

        # Сохраняем темы в список
        for topic in response.topics:
            topics.append({
                "id": topic.id,
                "title": topic.title,
            })
            logger.info(f"Topic ID: {topic.id}, Title: {topic.title}")
    except Exception as e:
        logger.error(f"Error fetching forum topics: {e}")

    return topics
    
async def save_all_chats(client: TelegramClient, output_file: str = "chats.json"):
    """
    Сохраняет все чаты, включая темы, в указанный файл.

    :param client: Авторизованный TelegramClient.
    :param output_file: Имя файла для сохранения данных (по умолчанию "chats.json").
    """
    try:
        logger.info("Fetching chats...")
        all_chats = []

        async for dialog in client.iter_dialogs():
            chat_data = {
                "name": dialog.name,
                "id": dialog.id,
                "type": type(dialog.entity).__name__,
            }
            
            # Если это супергруппа с форумом, получаем темы
            if getattr(dialog.entity, "forum", False):
                logger.info(f"Chat {dialog.name} is a forum. Fetching topics...")
                chat_data["topics"] = await fetch_forum_topics(client, dialog.id)

            all_chats.append(chat_data)

        # Сохраняем в файл
        try:
            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(all_chats, file, ensure_ascii=False, indent=4)
            logger.info(f"Chats saved successfully to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save chats to file: {e}")

    except errors.TimeoutError as e:
        logger.critical(f"Timeout error: {e}")
        await client.disconnect()
        raise
    except errors.RPCError as e:
        logger.critical(f"Telegram API error: {e}")
        raise
    except ConnectionError as e:
        logger.critical(f"Connection error: {e}")
        await client.disconnect()
        raise
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        raise

async def check_libraries():
    try:
        # Проверка Telethon
        console.print("[bold green]Checking Telethon...[/bold green]")
        try:
            client = TelegramClient("test_session", API_ID, API_HASH)
            console.print("[bold green]Telethon successfully imported![/bold green]")
        except errors.ValueError as ve:
            console.print(f"[bold red]Telethon configuration error: {ve}[/bold red]")
            logger.error(f"Telethon configuration error: {ve}")
        except Exception as e:
            console.print(f"[bold red]Error in Telethon: {e}[/bold red]")
            logger.error(f"General Telethon error: {e}")

        # Проверка dotenv
        console.print("[bold green]Checking python-dotenv...[/bold green]")
        try:
            load_dotenv()
            console.print("[bold green]python-dotenv successfully imported![/bold green]")
        except FileNotFoundError as fnf:
            console.print(f"[bold red].env file not found: {fnf}[/bold red]")
            logger.error(f".env file not found: {fnf}")
        except Exception as e:
            console.print(f"[bold red]Error in python-dotenv: {e}[/bold red]")
            logger.error(f"General dotenv error: {e}")

        # Проверка colorlog
        console.print("[bold green]Checking colorlog...[/bold green]")
        try:
            handler = colorlog.StreamHandler()
            handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(message)s'))
            logger.info("colorlog successfully imported!")
        except Exception as e:
            console.print(f"[bold red]Error in colorlog: {e}[/bold red]")
            logger.error(f"General colorlog error: {e}")

        # Вывод сообщения Hello World
        console.print("[bold blue]Hello, World! All libraries imported successfully![/bold blue]")

    except Exception as e:
        # Глобальная обработка ошибок
        logger.critical(f"Unhandled error: {e}")
        
        
async def test_send_message(client, chat_id: str, message_text: str) -> bool:
    """
    Тестирует отправку сообщения в указанный чат или канал.

    :param client: TelegramClient, авторизованный клиент.
    :param chat_id: ID чата или username.
    :param message_text: Текст сообщения.
    :return: True, если сообщение отправлено успешно, иначе False.
    """
    success = await send_message_safe(client, chat_id, message_text)
    if success:
        console.print("[bold green]Message sent successfully![/bold green]")
    else:
        console.print("[bold yellow]Message sending failed.[/bold yellow]")
        
async def main():
    # Выполняем асинхронную авторизацию
    client = await manual_authorization()
    if client is None:
        logger.critical("Authorization failed. Exiting...")
        return

    while True:
        await asyncio.sleep(1)
        console.print("[bold cyan]Choose an action:[/bold cyan]")
        console.print("[1] Send a message")
        console.print("[2] Load and display chat list")
        console.print("[3] Exit")
        
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            chat_id = input("Enter the chat ID or username: ").strip()
            message_text = input("Enter the message text: ").strip()
            await test_send_message(client, chat_id, message_text)
        elif choice == "2":
            # Сохранение чатов в файл
            await save_all_chats(client, output_file="all_chats.json")
        elif choice == "3":
            console.print("[bold green]Exiting program. Goodbye![/bold green]")
            # Завершаем соединение
            await client.disconnect()
            break
        else:
            console.print("[bold red]Invalid choice. Please try again.[/bold red]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"[bold red]Critical failure: {e}[/bold red]")
        logger.critical(f"Critical failure in main: {e}")
