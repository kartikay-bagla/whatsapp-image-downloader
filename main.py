from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import base64
import time
import requests
from datetime import datetime
from uuid import uuid4

import traceback

# Set the contact name and local directory for saving images
CONTACT_NAME = "CONTACT NAME"
SAVE_DIRECTORY = "images/"


def get_file_content_chrome(driver, uri):
    result = driver.execute_async_script(
        """
        var uri = arguments[0];
        var callback = arguments[1];
        var toBase64 = function(buffer){for(var r,n=new Uint8Array(buffer),t=n.length,a=new Uint8Array(4*Math.ceil(t/3)),i=new Uint8Array(64),o=0,c=0;64>c;++c)i[c]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charCodeAt(c);for(c=0;t-t%3>c;c+=3,o+=4)r=n[c]<<16|n[c+1]<<8|n[c+2],a[o]=i[r>>18],a[o+1]=i[r>>12&63],a[o+2]=i[r>>6&63],a[o+3]=i[63&r];return t%3===1?(r=n[t-1],a[o]=i[r>>2],a[o+1]=i[r<<4&63],a[o+2]=61,a[o+3]=61):t%3===2&&(r=(n[t-2]<<8)+n[t-1],a[o]=i[r>>10],a[o+1]=i[r>>4&63],a[o+2]=i[r<<2&63],a[o+3]=61),new TextDecoder("ascii").decode(a)};
        var xhr = new XMLHttpRequest();
        xhr.responseType = 'arraybuffer';
        xhr.onload = function(){ callback(toBase64(xhr.response)) };
        xhr.onerror = function(){ callback(xhr.status) };
        xhr.open('GET', uri);
        xhr.send();
        """,
        uri,
    )
    if type(result) == int:
        raise Exception(f"Request for uri {uri} failed with status {result}")
    return base64.b64decode(result)


# Start the web driver and navigate to WhatsApp Web
driver = webdriver.Firefox()

driver.get("https://web.whatsapp.com/")

# Wait for the user to scan the QR code and log in
input("Scan the QR code and press Enter once you're logged in...")

# Find the chat for the specified contact
search_box = driver.find_element(
    By.XPATH, '//div[contains(@class,"copyable-text selectable-text")]'
)
search_box.click()
search_box.send_keys(CONTACT_NAME)
time.sleep(2)
chat = driver.find_element(By.XPATH, f'//span[@title="{CONTACT_NAME}"]')
chat.click()


downloaded_urls = set()
while True:
    # Scroll to the bottom of the chat to load all messages
    message_count = len(driver.find_elements(By.XPATH, '//div[@class="message-in"]'))
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_message_count = len(
            driver.find_elements(By.XPATH, '//div[@class="message-in"]')
        )
        if new_message_count == message_count:
            break
        message_count = new_message_count

    # Find all images sent by the contact and download them to a local directory
    images = driver.find_elements(By.XPATH, '//div[@data-testid="image-thumb"]//img')
    for image in images:
        image_src = image.get_attribute("src")
        if image_src is None:
            continue
        if image_src in downloaded_urls:
            continue

        downloaded_urls.add(image_src)

        counter = 0
        while counter < 5:
            try:
                # Execute JavaScript to extract binary data from blob URL
                image_data = get_file_content_chrome(driver, uri=image_src)

                with open(f"{SAVE_DIRECTORY}{datetime.now()} - {uuid4()}.jpg", "wb") as file:
                    file.write(image_data)
                    break
            except Exception:
                print(f"Try number {counter}")
                traceback.print_exc()
            finally:
                counter += 1
        if counter >= 5:
            print("I give up on on this one. For now.")
            downloaded_urls.remove(image_src)
    # Wait for a few seconds before checking for new images
    time.sleep(10)
