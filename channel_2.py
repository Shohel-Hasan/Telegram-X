from telethon import TelegramClient, events
import os
import tweepy
import subprocess
import re
import sqlite3
import schedule
import time
from datetime import datetime, time as dt_time
import asyncio
import logging
import sys
from telethon.errors import FloodWaitError, MediaEmptyError, MessageEmptyError, MessageNotModifiedError, UserIsBlockedError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -1001056334519 - Darkweb Haber
# Replace these values with your own Twitter API credentials
consumer_key = 'RVBi0zezcgTmkjxGKlS2mDVto'
consumer_secret = 'omlBycWI0TiZXPPEAXygmFrwsfZUDd4QWSRRJVS2S6l2qLYvJi'
bearer_token = 'AAAAAAAAAAAAAAAAAAAAAAmRuAEAAAAApKtRWHyctfZVvMLS4%2B2OpZCpzJ4%3DwMQU7ucsz16jRpMKThEcEOPR2um8sPTEsilfkG2PT8DqMgcOAu'
access_token = '1134516108487266307-pZdmnweRd3gcuiDGIXXvNtaVbqf8qa'
access_token_secret = 'j4EEXM7AkYIYCHZ8RZH6gQdaaPLjyIAt9jhZzuaUoV1pz'

# Authenticate to Twitter using OAuth 1.0a (User Context)
auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
api = tweepy.API(auth)

# Use your own values here
api_id = '29760685'
api_hash = '3c869d581503fc52ea765f9cd33a0e77'
channel_id = -1001056334519  # Replace this with your channel ID
download_path = 'downloads/'  # Customize your download path here
db_path = 'posted_tweets.db'  # SQLite database file

# Create the client and connect
client = TelegramClient('session_name', api_id, api_hash)

def countdown(minutes):
    total_seconds = minutes * 60
    while total_seconds > 0:
        mins, secs = divmod(total_seconds, 60)
        timer = f'{mins:02d}:{secs:02d}'
        sys.stdout.write(f'\rTime remaining: {timer}')
        sys.stdout.flush()
        time.sleep(1)
        total_seconds -= 1

# Setup SQLite database
def setup_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            message_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

# Check if message_id exists in the database
def is_posted(message_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM posts WHERE message_id = ?', (message_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Save message_id to the database
def save_post(message_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO posts (message_id) VALUES (?)', (message_id,))
    conn.commit()
    conn.close()

def links_filter(description):
    # Improved regex pattern for matching URLs
    url_pattern = re.compile(
        r'((http|https):\/\/)?(www\.)?[\w-]+(\.[\w-]+)+([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?'
    )
    # Search for the pattern in the description
    if url_pattern.search(description):
        return False
    return True


async def download_media_with_retry(message, download_path, retries=3):
    for attempt in range(retries):
        try:
            await message.download_media(file=download_path)
            print(f'Media file downloaded: {message.id}')
            return
        except (FloodWaitError, MediaEmptyError, MessageEmptyError, MessageNotModifiedError, UserIsBlockedError) as e:
            print(f'Error downloading media: {e}')
            if isinstance(e, FloodWaitError):
                wait_time = e.seconds + 5
                print(f'FloodWaitError: Waiting for {wait_time} seconds before retrying...')
                await asyncio.sleep(wait_time)
            else:
                print(f'Error: {e}. Retrying...')
                await asyncio.sleep(5)
        except Exception as e:
            print(f'Unexpected error: {e}. Retrying...')
            await asyncio.sleep(5)
    print(f'Failed to download media after {retries} attempts: {message.id}')

def post_create(tweet, message):
    # Path to the directory containing images
    image_directory = './downloads'

    # Get all image paths from the directory
    image_paths = [os.path.join(image_directory, filename) for filename in os.listdir(image_directory)]

    # Upload the images to Twitter and collect their media IDs
    media_ids = []
    try:
        for image_path in image_paths:
            media = api.media_upload(image_path)
            media_ids.append(media.media_id_string)
        logger.info("Images uploaded successfully!")
    except Exception as e:
        logger.error(f"Error uploading image: {e}")

    # Ensure we have media IDs to post
    if media_ids:
        # Post a tweet with the images using API v2
        client = tweepy.Client(bearer_token=bearer_token,
                            consumer_key=consumer_key,
                            consumer_secret=consumer_secret,
                            access_token=access_token,
                            access_token_secret=access_token_secret)

        try:
            if len(tweet) > 3:
                response = client.create_tweet(text=tweet, media_ids=media_ids)
                logger.info("Tweet posted successfully!")
                logger.info("Tweet ID: %s", response.data['id'])
        except tweepy.TweepyException as e:
            logger.error(f"Error posting tweet: {e}")

        # Clear the download directory after the tweet is posted
        for filename in os.listdir(image_directory):
            file_path = os.path.join(image_directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}. Reason: {e}")
    else:
        logger.info("No media files were uploaded.")

    # Save message ID to database
    save_post(message.id)

    logger.info("Waiting for 30 minutes!")
    countdown(30)

async def process_messages():
    # Connect to the client
    await client.start()
    # Ensure you're authorized
    if not await client.is_user_authorized():
        phone = '+905332414148'
        await client.send_code_request(phone)
        code = input('Enter the code you received: ')
        await client.sign_in(phone, code)

    # Get the channel entity using the channel ID
    entity = await client.get_entity(channel_id)

    # Ensure the download directory exists
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    # Setup the database
    setup_db()

    # Iterate over the messages in the channel
    async for message in client.iter_messages(entity, limit=6):
        print(message.id, "--> " ,message.text[:10])
        if message.media and links_filter(message.text) and not is_posted(message.id):
            # await message.download_media(file=download_path)
            await download_media_with_retry(message, download_path)
            print(f'Media files downloaded')
            # Check if the message has already been posted
            post_create(tweet=message.text, message=message)

            
                

while True:
    client.loop.run_until_complete(process_messages())
    for filename in os.listdir(download_path):
        file_path = os.path.join(download_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                os.rmdir(file_path)
        except Exception as e:
            logger.error(f"Failed to delete {file_path}. Reason: {e}")
    print('Restarting...')
    countdown(5)
    executable = sys.executable
    args = sys.argv[:]
    subprocess.Popen([executable] + args)
    sys.exit()


# client.loop.run_until_complete(process_messages())

