from telethon import TelegramClient, errors, events
from telethon.tl.types import InputMessagesFilterPinned # Для фильтрации закрепленных сообщений
from telethon.tl.functions.channels import GetForumTopicsRequest  # Для получения списка тем форума
import asyncio
from asyncio.exceptions import TimeoutError
from dotenv import load_dotenv # Для загрузки конфигурации из .env
from datetime import datetime
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
        
async def fetch_chat_history(client, chat_id, output_file="chat_history.json", topic_id=None, limit=None):
    """
    Скачивает историю сообщений из указанного чата или топика форума.

    :param client: TelegramClient, авторизованный клиент.
    :param chat_id: ID чата или username.
    :param output_file: Имя файла для сохранения истории (по умолчанию "chat_history.json").
    :param topic_id: ID топика форума (если указан, загружаются сообщения только из этого топика).
    :param limit: Максимальное количество сообщений для загрузки (по умолчанию None).
    """
    try:
        logger.info(f"Fetching history for chat ID {chat_id} with topic ID {topic_id}...")

        # Преобразуем chat_id в int, если это строка
        if isinstance(chat_id, str):
            chat_id = int(chat_id)

        # Получаем Entity чата
        entity = await client.get_entity(chat_id)
        logger.info(f"Entity fetched: {entity.title if hasattr(entity, 'title') else entity.id}")

        # Итерируем сообщения
        messages = []
        
        offset_id = 0  # Начинаем с самого нового сообщения
        remaining_limit = limit  # Начинаем с указанного лимита (или None)
        
        while True:
            try:
                
                # Если лимит не задан, запрашиваем максимум 100 сообщений за раз
                fetch_limit = 100 if remaining_limit is None else min(100, remaining_limit)
                batch_messages = []  # Сообщения за текущую итерацию
                
                async for message in client.iter_messages(entity, limit=fetch_limit, offset_id=offset_id, reply_to=topic_id):
                    batch_messages.append({
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text or "",
                        "sender_id": message.sender_id,
                        "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None,
                    })
                    offset_id = message.id  # Устанавливаем новый offset_id

                messages.extend(batch_messages)
                if batch_messages:
                    logger.info(f"Fetched {len(batch_messages)} messages. Total fetched: {len(messages)}. Last message ID: {offset_id}")

                # Если сервер больше не возвращает сообщений, завершаем
                if not batch_messages:
                    break
                    
                # Уменьшаем лимит, если он задан
                if remaining_limit is not None:
                    remaining_limit -= len(messages)
                    if remaining_limit <= 0:
                        break
                        
                # Задержка между запросами
                await asyncio.sleep(2)

            except errors.FloodWaitError as e:
                logger.warning(f"Rate limit exceeded. Waiting for {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise  # Пробрасываем неиспользуемое исключение

        # Сохраняем историю сообщений в файл
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=4)
        logger.info(f"Chat history saved to {output_file}")

        console.print(f"[bold green]Chat history successfully saved to {output_file}[/bold green]")

    except errors.FloodWaitError as e:
        logger.warning(f"Rate limit exceeded. Waiting for {e.seconds} seconds...")
        await asyncio.sleep(e.seconds)
    except ValueError as e:
        logger.error(f"Chat {chat_id} not found: {e}")
    except errors.RPCError as e:
        logger.error(f"Telegram API error while fetching history: {e}")
    except Exception as e:
        logger.critical(f"Unexpected error while fetching history: {e}")
        
async def save_event_to_file(event, file_name="event_debug.jsonl"):
    """
    Преобразует событие в сериализуемую структуру и сохраняет его в JSON-файл.

    :param event: Событие, которое нужно преобразовать.
    :param file_name: Имя файла для записи (по умолчанию "event_debug.jsonl").
    """
    try:
        # Преобразуем событие в словарь
        event_dict = event.to_dict()

        # Рекурсивно обрабатываем словарь, конвертируя datetime в строку
        def convert_to_serializable(obj):
            if isinstance(obj, dict):
                return {key: convert_to_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()  # Преобразуем datetime в строку
            elif hasattr(obj, "to_dict"):
                return convert_to_serializable(obj.to_dict())  # Рекурсивно обрабатываем вложенные объекты
            return obj  # Для всех других типов возвращаем как есть

        serializable_event = convert_to_serializable(event_dict)

        # Открываем файл в режиме дозаписи
        with open(file_name, "a", encoding="utf-8") as f:
            # Записываем объект как строку JSON
            f.write(json.dumps(serializable_event, ensure_ascii=False, indent=4) + "\n")
        logger.info(f"Event structure saved to {file_name}")

    except Exception as e:
        logger.error(f"Error while serializing event: {e}")
        
def normalize_chat_id(chat):
    """
    Преобразует идентификатор чата в формат с -100, если это супергруппа, форум или канал.

    :param chat: Объект чата (например, из event.get_chat()).
    :return: Преобразованный идентификатор чата в строковом формате.
    """
    if getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False) or getattr(chat, "forum", False):
        # Если ID уже имеет формат с -100, возвращаем его как есть
        if str(chat.id).startswith("-100"):
            return chat.id
        # Добавляем -100 перед ID
        return int(f"-100{abs(chat.id)}")
    return chat.id
    
def is_monitored_chat(event_chat, event_topic, monitored_chats):
    """
    Проверяет, принадлежит ли событие отслеживаемому чату или топику.

    :param event_chat: Чат события (объект чата).
    :param event_topic: ID топика события (или None).
    :param monitored_chats: Список фильтров чатов.
    :return: True, если событие соответствует какому-либо фильтру, иначе False.
    """
    normalized_chat_id = str(normalize_chat_id(event_chat))
    chat_title = getattr(event_chat, "title", None)
    chat_username = getattr(event_chat, "username", None)

    for chat_filter in monitored_chats:
        # Проверяем ID чата
        if "id" in chat_filter and str(chat_filter["id"]) != normalized_chat_id:
            continue
        
        # Проверяем title чата
        if "title" in chat_filter and chat_filter["title"] and chat_filter["title"] != chat_title:
            continue
        
        # Проверяем username чата
        if "username" in chat_filter and chat_filter["username"] and chat_filter["username"] != chat_username:
            continue

        # Проверяем топики
        if "topics" in chat_filter and chat_filter["topics"]:
            if event_topic not in chat_filter["topics"]:
                continue

        # Если всё совпало
        return True

    return False
        
async def listen_to_messages(client, monitored_chats, output_file="monitored_messages.json"):
    """
    Режим прослушивания сообщений из указанных чатов, включая топики форумов.

    :param client: TelegramClient, авторизованный клиент.
    :param monitored_chats: Список ID чатов или username, которые нужно мониторить.
    :param output_file: Имя файла для записи новых сообщений.
    """
    console.print("[bold cyan]Listening to messages... Press Ctrl+C to stop.[/bold cyan]")
    logger.info("Starting message listener...")

    monitored_messages = []

    @client.on(events.NewMessage())
    async def new_message_handler(event):
        try:
            chat = await event.get_chat()
            chat_name = getattr(chat, "title", None) or getattr(chat, "username", None) or "Private Chat/User"
            
            # Нормализуем идентификатор чата для проверки
            normalized_chat_id = normalize_chat_id(chat)

            # Логируем информацию о новом событии
            logger.info(f"New event detected in chat {chat_name} (ID={normalized_chat_id}): Message ID={event.message.id}")
            # logger.info(f"Normalized chat ID: {chat.id} ({type(chat.id)}), Monitored chats: {monitored_chats} ({[type(chat) for chat in monitored_chats]})")

            # Проверяем, является ли сообщение из форума
            forum_id = None
            topic_id = None
            if getattr(chat, "forum", False):  # Проверка, является ли чат форумом
                forum_id = normalized_chat_id
                topic_id = (
                    getattr(event.message.reply_to, "reply_to_top_id", None)  # ID топика
                    or getattr(event.message.reply_to, "reply_to_msg_id", None)  # Иногда используется как замена
                )
                
                logger.info(f"Forum detected: Forum ID={forum_id}, Topic ID={topic_id}")

            # Проверяем, принадлежит ли событие одному из отслеживаемых чатов
            if not is_monitored_chat(chat, topic_id, monitored_chats):
                return

            # Логируем сообщение в консоль
            console.print(f"[bold green]New message in chat {chat_name}:[/bold green] {event.message.message}")

            # Если сообщение в топике форума, логируем ID топика
            if topic_id:
                logger.info(f"Message is in topic ID: {topic_id}")

            # Сохраняем сообщение в список
            monitored_messages.append({
                "chat_id": normalized_chat_id,
                "chat_name": chat_name,
                "message_id": event.message.id,
                "date": event.message.date.isoformat(),
                "text": event.message.message,
                "sender_id": event.message.sender_id,
                "forum_id": forum_id,
                "topic_id": topic_id,
            })

            # Периодически сохраняем сообщения в файл
            if len(monitored_messages) % 10 == 0:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(monitored_messages, f, ensure_ascii=False, indent=4)
                logger.info(f"Saved monitored messages to {output_file}")

        except Exception as e:
            logger.error(f"Error while handling new message: {e}")

    try:
        await client.run_until_disconnected()
    except asyncio.exceptions.CancelledError:
        # Обработка нажатия Ctrl+C
        logger.info("Message listener stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Unexpected error in message listener: {e}")
        raise
        
async def main():
    console.print("[bold magenta]Telegram Monitoring Tool[/bold magenta]")
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
        console.print("[3] Fetch chat history")
        console.print("[4] Listen to messages in chats")
        console.print("[5] Exit")
        
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            chat_id = input("Enter the chat ID or username: ").strip()
            message_text = input("Enter the message text: ").strip()
            await test_send_message(client, chat_id, message_text)
        elif choice == "2":
            # Сохранение чатов в файл
            await save_all_chats(client, output_file="all_chats.json")
        elif choice == "3":
            # Запрос данных для загрузки истории
            chat_id = input("Enter the chat ID or username: ").strip()
            topic_id_input = input("Enter the topic ID (optional, press Enter to skip): ").strip()
            topic_id = int(topic_id_input) if topic_id_input else None
            output_file = input("Enter the output file name (default: chat_history.json): ").strip() or "chat_history.json"
            limit_input = input("Enter the number of messages to fetch (default: None): ").strip()
            limit = None if not limit_input else int(limit_input)
            await fetch_chat_history(client, chat_id, output_file, topic_id, limit)
        elif choice == "4":
            monitored_chats = []
            console.print("[bold cyan]Add chats to monitor:[/bold cyan]")

            while True:
                chat_input = input("Enter chat ID, username, or title to monitor (leave blank to finish): ").strip()
                if not chat_input:  # Выход из цикла при пустом вводе
                    break

                # Спрашиваем список топиков (если это форум)
                topics_input = input("Enter topic IDs to monitor, separated by commas (optional): ").strip()
                topics = [int(topic.strip()) for topic in topics_input.split(",") if topic.strip()] if topics_input else None

                # Проверяем, это ID, username или title
                if chat_input.isdigit() or chat_input.startswith("-"):
                    # Введен ID
                    monitored_chats.append({
                        "id": int(chat_input),
                        "username": None,
                        "title": None,
                        "topics": topics,
                    })
                    console.print(f"[bold green]Chat added to monitor by ID: {chat_input}, topics: {topics}[/bold green]")

                elif chat_input.startswith("@"):
                    # Введен username (должен начинаться с @)
                    monitored_chats.append({
                        "id": None,
                        "username": chat_input.lstrip("@"),
                        "title": None,
                        "topics": topics,
                    })
                    console.print(f"[bold green]Chat added to monitor by username: {chat_input}, topics: {topics}[/bold green]")

                else:
                    # Иначе это предполагаемый заголовок (title)
                    monitored_chats.append({
                        "id": None,
                        "username": None,
                        "title": chat_input,
                        "topics": topics,
                    })
                    console.print(f"[bold green]Chat added to monitor by title: {chat_input}, topics: {topics}[/bold green]")

            console.print(f"[bold cyan]Final monitored chats list: {monitored_chats}[/bold cyan]")

            # Если список пуст, предупреждаем
            if not monitored_chats:
                console.print("[bold yellow]No chats added for monitoring.[/bold yellow]")
            else:
                # Запускаем прослушивание сообщений
                output_file = input("Enter the output file name for monitored messages (default: monitored_messages.json): ").strip() or "monitored_messages.json"
                await listen_to_messages(client, monitored_chats, output_file)
        elif choice == "5":
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
