import logging
import os
from bot import bot

if __name__ == '__main__':
    logging.basicConfig(filename='bot.log', encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s: %(message)s', 
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    logger = logging.getLogger(__name__)
    logging.getLogger('discord').disabled = True

    key = os.environ.get('DISCORD_API_KEY')
    try:
        bot.run(key)
    except Exception as e:
        logger.error(str(e))