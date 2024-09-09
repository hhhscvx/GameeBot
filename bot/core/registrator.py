from pyrogram import Client

from bot.config import settings
from bot.utils import logger


async def register_session():
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH

    if not API_ID or not API_HASH:
        raise ValueError('API_ID or API_HASH not found in .env file')

    session_name = input('\nEnter the session name (press Enter to exit):')

    session = Client(
        name=session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir='sessions/'
    )

    async with session:
        user_data = await session.get_me()

    logger.success(f'Session added successfully @{user_data.username} | {user_data.first_name} | {user_data.last_name}')
