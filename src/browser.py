

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.utils import load_config


def get_driver() -> webdriver.Chrome:
    
    cfg      = load_config()
    headless = cfg.get("HEADLESS", True)

    opts = webdriver.ChromeOptions()

    if headless:
        opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--ignore-certificate-errors")

   
    opts.add_argument("--window-size=1920,1080")

   
    opts.add_experimental_option("prefs", {
        "plugins.always_open_pdf_externally"   : True,   # download, don't open
        "download.prompt_for_download"          : False,
        "download.default_directory"            : "/dev/null",
        "profile.default_content_settings.popups": 0,
    })

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)
