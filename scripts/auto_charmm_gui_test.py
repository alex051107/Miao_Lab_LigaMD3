import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

EMAIL = "liualex@unc.edu"
PASSWORD = "lzpcjxhHYY1!"
PDB_PATH = "/Users/liuzhenpeng/Desktop/UNC/Miao's Lab/HSP90_structures/test_5J64/5J64_complex.pdb"

def main():
    print("Initializing Chrome...")
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # keep head on for visual debugging
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    
    try:
        # 1. Open the homepage
        print("Opening CHARMM-GUI homepage...")
        driver.get("https://charmm-gui.org/")
        time.sleep(3)
        
        print("Dumping HTML...")
        with open("charmm_page.html", "w") as f:
            f.write(driver.page_source)
        print("Done.")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        
    finally:
        print("Closing browser.")
        driver.quit()

if __name__ == "__main__":
    main()
