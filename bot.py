import os
import tempfile
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, error as MP3Error
from mutagen.mp4 import MP4, MP4Cover

BOT_TOKEN = "9022968857:AAEUM24Mv1w64XJrM4OUELO9wU59hZrG4mU"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to the Music Bot!\n\n"
        "Send me a YouTube link like this:\n"
        "`/mp3 https://youtu.be/...`",
        parse_mode="Markdown"
    )

async def download_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a YouTube link.\nExample: /mp3 <url>")
        return

    url = context.args[0]
    status_msg = await update.message.reply_text("⏳ Fetching audio... Please wait.")

    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'format': 'best',
        'nocheckcertificate': True,
        'outtmpl': os.path.join(temp_dir, 'audio_file.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',
        'extractor_args': {
            'youtube': {
                'player_client': ['android']
            }
        },
    }

    try:
        max_retries = 3
        info = None
        filename = None

        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    await status_msg.edit_text(f"🔄 YouTube busy. Retrying ({attempt+1}/{max_retries})...")
                    time.sleep(3)
                else:
                    raise e

        title = info.get('title', 'Unknown Title')
        artist = info.get('uploader', 'Unknown Artist')
        thumbnail_url = info.get('thumbnail')
        
        ext = info.get('ext', 'mp4')
        final_filename = os.path.join(temp_dir, f"final_song.{ext}")
        os.rename(filename, final_filename)

        await status_msg.edit_text("🖼️ Setting album cover...")

        thumb_path = ""
        if thumbnail_url:
            thumb_path = os.path.join(temp_dir, "cover.jpg")
            try:
                img_data = requests.get(thumbnail_url).content
                with open(thumb_path, 'wb') as handler:
                    handler.write(img_data)
            except Exception:
                pass

        try:
            if ext == 'mp3':
                audio = MP3(final_filename, ID3=ID3)
                try:
                    audio.add_tags()
                except MP3Error:
                    pass
                audio.tags.add(TIT2(encoding=3, text=title))
                audio.tags.add(TPE1(encoding=3, text=artist))
                if thumb_path and os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as img_file:
                        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_file.read()))
                audio.save()
                
            elif ext in ['m4a', 'mp4']:
                audio = MP4(final_filename)
                audio['\xa9nam'] = title
                audio['\xa9ART'] = artist
                if thumb_path and os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as img_file:
                        audio['covr'] = [MP4Cover(img_file.read(), imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()
        except Exception:
            pass

        await status_msg.edit_text("📤 Uploading to Telegram...")
        
        thumb_file = open(thumb_path, 'rb') if os.path.exists(thumb_path) else None
        
        with open(final_filename, 'rb') as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                performer=artist,
                thumbnail=thumb_file
            )

        if thumb_file:
            thumb_file.close()
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        os.remove(final_filename)
        os.rmdir(temp_dir)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text("❌ Error: Could not download.\nMake sure the link is valid and public.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", download_mp3))
    
    app.run_polling()

if __name__ == "__main__":
    main()