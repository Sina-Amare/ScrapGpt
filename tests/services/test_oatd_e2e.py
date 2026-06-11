import pytest
from DrissionPage import ChromiumPage, ChromiumOptions
import time

def test_drissionpage_bypass():
    url = "https://www.oatd.org/oatd/search?q=statistics&form=basic&last2yr=y&level.facet=doctoral"
    print(f"\n--- FETCHING WITH DrissionPage ---")
    try:
        co = ChromiumOptions()
        co.headless(False)  # Run with UI first to solve Cloudflare
        co.set_argument('--window-size=1920,1080')
        co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        page = ChromiumPage(co)
        page.get(url)
        
        print("[*] Waiting up to 15 seconds for page load / Cloudflare bypass...")
        page.wait.load_start()
        
        # DrissionPage handles wait automatically, but wait a bit to be sure
        time.sleep(8)
        
        html = page.html
        title = page.title
        
        print(f"[SUCCESS] HTML length: {len(html)}")
        print(f"[SUCCESS] HTML title: {title}")
        
        if "Just a moment" in title or "Cloudflare" in title:
            print("[FAILED] Cloudflare challenge not bypassed.")
        else:
            print("[SUCCESS] Cloudflare bypass successful!")
            
        page.quit()
    except Exception as e:
        print(f"[FAILED] Error: {e}")
