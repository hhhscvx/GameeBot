import asyncio
import glob
from itertools import cycle
import os

from better_proxy import Proxy
from pyrogram import Client

from bot.config import settings
from bot.utils import logger
from bot.core.registrator import register_sessions
from bot.core.tapper import run_tapper

start_text = """
  ____                                ____          _   
 / ___|  __ _  _ __ ___    ___   ___ | __ )   ___  | |_ 
| |  _  / _` || '_ ` _ \  / _ \ / _ \|  _ \  / _ \ | __|
| |_| || (_| || | | | | ||  __/|  __/| |_) || (_) || |_ 
 \____| \__,_||_| |_| |_| \___| \___||____/  \___/  \__|

Select an action:

    1. Create session
    2. Run clicker
"""

global tg_clients


def get_session_names() -> list[str]:
    session_names = glob.glob("sessions/*.session")
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names


def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file="bot/config/proxies.txt", encoding="utf-8-sig") as file:
            proxies = [Proxy.from_str(proxy=row.strip()).as_url for row in file]
    else:
        proxies = []

    return proxies


async def get_tg_clients() -> list[Client]:
    global tg_clients

    session_names = get_session_names()

    if not session_names:
        raise FileNotFoundError("Not found session files")

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID and API_HASH not found in .env file")

    tg_clients = [
        Client(
            name=session_name,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            workdir="sessions/"
        )
        for session_name in session_names
    ]

    return tg_clients


async def process() -> None:

    logger.info(f"Detected {len(get_session_names())} sessions | {len(get_proxies())} proxies")

    print(start_text)

    while True:
        action = input("> ")

        if not action.isdigit():
            logger.warning("Action must be number")
        elif action not in ['1', '2']:
            logger.warning("Action must be 1 or 2")
        else:
            action = int(action)
            break

    if action == 1:
        await register_sessions()
    elif action == 2:
        tg_clients = await get_tg_clients()

        await run_tasks(tg_clients)


async def run_tasks(tg_clients: list[Client]) -> None:
    proxies = get_proxies()
    proxies_cycle = cycle(proxies) if proxies else None

    tasks = [
        asyncio.create_task(
            run_tapper(tg_client,
                       proxy=next(proxies_cycle) if proxies_cycle else None)
        )
        for tg_client in tg_clients
    ]

    await asyncio.gather(*tasks)
