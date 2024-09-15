import asyncio
from contextlib import suppress

from bot.utils.launcher import process


async def main():
    await process()


if __name__ == '__main__':
    with suppress(KeyboardInterrupt):  # Ignore CTRL + C
        asyncio.run(main())
