from urllib import response

from bs4 import BeautifulSoup
import requests
import certifi, ssl
from playwright.sync_api import sync_playwright

url ='https://www.timesjobs.com/job-search?keywords=%22Python%22%2C&location=&experience=&refreshed=true'

def fetch_jobs(url):
    try:
        unfamiliar_skill = input("Enter a skill you are not familiar with: ")
        print(__name__)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_timeout(5000)
            soup = BeautifulSoup(page.content(), "lxml")
            jobs = soup.find_all('div', class_='p-4 md:p-6 bg-white rounded-xl mb-4 shadow-sm relative srp-card')
            for job in jobs:
                location_section = job.find('div', class_='mt-3 text-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-2')
                location = location_section.find('div', class_='block md:flex md:items-center w-[100%]') 
                loc_first = location.span
                if loc_first and 'Coimbatore' in loc_first.text:
                    skills_section = job.find('div', class_='mt-4')
                    skills = skills_section.find_all('span', class_='skill-tag border border-[#f2f2f2] mr-1 rounded-full px-2 py-0 text-xs whitespace-nowrap flex-shrink-0 bg-white text-[#666]')
                    print(f"Required skills: {[skill.text for skill in skills]}")
                    if not any(unfamiliar_skill.lower() in skill.text.lower() for skill in skills):
                        print("-"*50)
                        print(loc_first.text.replace('\n', '').strip())
                        company = job.find('span', class_='w-[60px] md:w-auto inline-block whitespace-nowrap overflow-hidden text-ellipsis')
                        if company:
                            print(company.text)
                        for skill in skills:
                            if unfamiliar_skill.lower() not in skill.text.lower():
                                print(skill.text)
                        more_info = job.find('a', class_='absolute left-0 right-0 top-0 bottom-0 z-20')
                        if more_info:
                            print(f"More info: {more_info.get('href')}")
            print("-"*50)
            browser.close()
    except Exception as e:
        print(f"An error occurred while fetching the URL: {e}")


if __name__ == "__main__":
    fetch_jobs(url)
