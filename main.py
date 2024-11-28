from telethon import TelegramClient
from dotenv import load_dotenv
import logging
import colorlog
from rich.console import Console
import asyncio

console = Console()

# Настройка логгера
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(message)s'))

file_handler = logging.FileHandler("application.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = colorlog.getLogger('example')
logger.addHandler(handler)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

async def main():
    try:
        # Проверка Telethon
        console.print("[bold green]Checking Telethon...[/bold green]")
        try:
            client = TelegramClient("test_session", api_id="12345", api_hash="abcdef12345")
            console.print("[bold green]Telethon successfully imported![/bold green]")
        except ValueError as ve:
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
        console.print(f"[bold red]Unhandled error: {e}[/bold red]")
        logger.critical(f"Unhandled error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"[bold red]Critical failure: {e}[/bold red]")
        logger.critical(f"Critical failure in main: {e}")