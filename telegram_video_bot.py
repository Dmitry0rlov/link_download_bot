import asyncio
import logging
import re
import os
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import yt_dlp
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


BOT_TOKEN = "7553558482:AAEuDLjqz-a7uHXKzjPpmMu8CGbhqJqXsDc"

class VideoDownloadBot:
    def __init__(self):
        self.download_folder = "downloads"
        os.makedirs(self.download_folder, exist_ok=True)
    
    def extract_urls(self, text):
        """Витягує всі URL з тексту"""
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        return url_pattern.findall(text)
    
    def is_video_url(self, url):
     
        video_domains = [
            'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'tiktok.com', 'instagram.com', 'twitter.com', 'x.com',
            'facebook.com', 'twitch.tv'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        return any(video_domain in domain for video_domain in video_domains)
    
    async def download_video(self, url, max_size_mb=50):
      
        try:
            ydl_opts = {
                'format': 'best[filesize<50M]/best',
                'outtmpl': f'{self.download_folder}/%(title)s.%(ext)s',
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                
                # Перевіряємо розмір файлу
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                if filesize and filesize > max_size_mb * 1024 * 1024:
                    return None, f"Відео занадто велике ({filesize/(1024*1024):.1f}MB). Максимум {max_size_mb}MB"
                
             
                ydl.download([url])
                
            
                for file in os.listdir(self.download_folder):
                    if title.replace('/', '_') in file or info.get('id', '') in file:
                        filepath = os.path.join(self.download_folder, file)
                        return filepath, None
                        
                return None, "Файл не знайдено після завантаження"
                
        except Exception as e:
            logger.error(f"Помилка завантаження відео {url}: {e}")
            return None, f"Помилка завантаження: {str(e)}"
    
    def get_page_description(self, url):
      
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Пробуємо різні способи отримання опису
            description = None
            
            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '').strip()
            
            # Open Graph description
            if not description:
                og_desc = soup.find('meta', attrs={'property': 'og:description'})
                if og_desc:
                    description = og_desc.get('content', '').strip()
            
            # Twitter description
            if not description:
                twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
                if twitter_desc:
                    description = twitter_desc.get('content', '').strip()
            
            # Заголовок сторінки
            title = soup.find('title')
            title_text = title.text.strip() if title else "Без заголовка"
            
            # Якщо немає опису, беремо перший параграф
            if not description:
                paragraph = soup.find('p')
                if paragraph:
                    description = paragraph.text.strip()[:200] + "..."
            
            return {
                'title': title_text[:100],
                'description': description[:300] if description else "Опис недоступний",
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Помилка отримання опису для {url}: {e}")
            return {
                'title': "Помилка",
                'description': f"Не вдалося отримати опис: {str(e)}",
                'url': url
            }


bot = VideoDownloadBot()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє повідомлення з посиланнями"""
    message = update.message
    text = message.text
    
    # Витягуємо всі URL з повідомлення
    urls = bot.extract_urls(text)
    
    if not urls:
        return
    
    await message.reply_text("🔍 Знайдено посилання! Обробляю...")
    
    for url in urls:
        try:
            if bot.is_video_url(url):
                # Спробуємо завантажити відео
                await message.reply_text(f"📹 Завантажую відео з: {url}")
                
                filepath, error = await bot.download_video(url)
                
                if filepath and os.path.exists(filepath):
                    # Відправляємо відео
                    with open(filepath, 'rb') as video_file:
                        await message.reply_video(
                            video=video_file,
                            caption=f"📹 Завантажено з: {url}"
                        )
                    
                    # Видаляємо файл після відправки
                    os.remove(filepath)
                    
                elif error:
                    await message.reply_text(f"❌ {error}")
                    # Якщо не вдалося завантажити відео, робимо опис
                    page_info = bot.get_page_description(url)
                    description_text = f"📄 **{page_info['title']}**\n\n{page_info['description']}\n\n🔗 {page_info['url']}"
                    await message.reply_text(description_text, parse_mode='Markdown')
            else:
                # Для не-відео посилань робимо короткий опис
                await message.reply_text(f"📄 Створюю опис для: {url}")
                
                page_info = bot.get_page_description(url)
                description_text = f"📄 **{page_info['title']}**\n\n{page_info['description']}\n\n🔗 {page_info['url']}"
                
                await message.reply_text(description_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Помилка обробки URL {url}: {e}")
            await message.reply_text(f"❌ Помилка обробки {url}: {str(e)}")

def main():
  
    # Створюємо додаток
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Додаємо обробник повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущено! Надсилайте посилання для обробки...")
    
    # Запускаємо бота
    application.run_polling()

if __name__ == '__main__':
    main()
