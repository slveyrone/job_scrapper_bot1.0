import os
import time
import random
import sqlite3
import logging
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async, stealth_sync

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class JobScraperBot:
    def __init__(self):
        load_dotenv()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.db_path = "jobs.db"
        self.init_db()

    def init_db(self):
        """SQLite veritabanını ve tabloyu başlatır."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        company TEXT,
                        location TEXT,
                        work_type TEXT,
                        link TEXT UNIQUE,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
            logger.info("Veritabanı başarıyla başlatıldı.")
        except sqlite3.Error as e:
            logger.error(f"Veritabanı başlatılırken hata oluştu: {e}")

    def is_job_exists(self, link):
        """İlanın veritabanında olup olmadığını kontrol eder."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM jobs WHERE link = ?", (link,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Veritabanı okuma hatası: {e}")
            return True # Hata durumunda spam yapmamak için var kabul et

    def add_job_to_db(self, job):
        """Yeni ilanı veritabanına ekler."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO jobs (title, company, location, work_type, link)
                    VALUES (?, ?, ?, ?, ?)
                ''', (job['title'], job['company'], job['location'], job['work_type'], job['link']))
                conn.commit()
        except sqlite3.IntegrityError:
            pass # UNIQUE constraint hatası, zaten var
        except sqlite3.Error as e:
            logger.error(f"Veritabanı yazma hatası: {e}")

    def send_telegram_message(self, job):
        """Telegram üzerinden formatlanmış bildirim gönderir."""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram token veya chat ID eksik!")
            return

        message = (
            f"🔔 YENİ İLAN\n"
            f"🏢 Firma & Konum: {job['company']} — {job['location']}\n"
            f"💼 Pozisyon: {job['title']}\n"
            f"⏱️ Çalışma Şekli: {job['work_type']}\n"
            f"🔗 İlan Linki: {job['link']}"
        )

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Telegram mesajı gönderildi: {job['title']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram gönderim hatası: {e}")

    def simulate_human_delay(self, min_sec=2.0, max_sec=5.0):
        """Sayfa geçişleri arasında insansı bekleme süresi."""
        time.sleep(random.uniform(min_sec, max_sec))

    def scrape_example_platform(self, page, url):
        """
        Örnek scraping metodu (Örn: Kariyer.net veya Indeed).
        Not: Platformların HTML yapıları sık değiştiği için selector'ları kendi
        arama URL'ne ve güncel HTML yapısına göre revize etmelisin.
        """
        jobs = []
        try:
            logger.info(f"Taranıyor: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.simulate_human_delay(3, 7)

            # ÖRNEK SELECTOR MANTIĞI (Burayı hedef siteye göre değiştirmelisin)
            # İlan kartlarını bul
            job_cards = page.query_selector_all('.job-card-class') # Örnek Sınıf
            
            for card in job_cards:
                try:
                    title = card.query_selector('.title-class').inner_text().strip()
                    company = card.query_selector('.company-class').inner_text().strip()
                    location = card.query_selector('.location-class').inner_text().strip()
                    work_type = card.query_selector('.work-type-class').inner_text().strip()
                    
                    # Linki al ve tam URL'ye çevir
                    href = card.query_selector('a').get_attribute('href')
                    link = f"https://www.orneksite.com{href}" if href.startswith('/') else href

                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "work_type": work_type,
                        "link": link
                    })
                except Exception as e:
                    logger.warning(f"İlan kartı ayrıştırılırken hata (Atlanıyor): {e}")
                    continue

        except PlaywrightTimeoutError:
            logger.error(f"Zaman aşımı hatası: {url}")
        except Exception as e:
            logger.error(f"Scraping sırasında beklenmeyen hata: {e}")

        return jobs

    def run(self):
        """Ana çalışma döngüsü"""
        # 1. GitHub Actions'ta çalıştığında botları atlatmak için rastgele 0-10 dk bekleme
        startup_delay = random.randint(0, 600)
        logger.info(f"İnsan davranışı simülasyonu: {startup_delay} saniye bekleniyor...")
        time.sleep(startup_delay)

        # 2. Playwright Başlatma
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            
            # Gerçekçi bir User-Agent
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True
            )
            
            page = context.new_page()
            stealth_sync(page) # Cloudflare ve bot korumalarını atlatmak için stealth mode
            
            # Taranacak URL'ler listesi (Kendi filtrelediğin URL'leri buraya ekle)
            target_urls = [
                "https://www.orneksite.com/is-ilanlari?param=1",
                # "https://www.baskasite.com/arama?q=python"
            ]

            all_scraped_jobs = []
            
            # 3. Scraping İşlemi
            for url in target_urls:
                jobs = self.scrape_example_platform(page, url)
                all_scraped_jobs.extend(jobs)
                self.simulate_human_delay(5, 10) # Sayfalar arası bekleme
                
            browser.close()

        # 4. Veritabanı Kontrolü ve Telegram Bildirimi
        new_jobs_count = 0
        for job in all_scraped_jobs:
            if not self.is_job_exists(job['link']):
                self.send_telegram_message(job)
                self.add_job_to_db(job)
                new_jobs_count += 1
                self.simulate_human_delay(1, 3) # Telegram API limitlerine takılmamak için

        logger.info(f"İşlem tamamlandı. Toplam bulunan yeni ilan: {new_jobs_count}")


if __name__ == "__main__":
    bot = JobScraperBot()
    bot.run()
