from bs4 import BeautifulSoup
import requests
import scrap_real_website

url = 'https://example.com'
try:
    fetch_jobs = scrap_real_website.fetch_jobs(url)
    with open('index.html', 'r') as html_file:
        content = html_file.read()
        soup = BeautifulSoup(content, 'lxml')
        tags = soup.find('h1')#returns result set
        for tag in tags:
            print(tag.text)
        cards = soup.find_all('h5', class_='h5')
        for card in cards:
            print(card.text)  
        all_divs = soup.find_all('div', class_='portfolio')
        for div in all_divs:
            print(div)
            print(div.h6)
            print(div.h6.text)
except Exception as e:
    print(f"An error occurred while fetching the URL: {e}")
