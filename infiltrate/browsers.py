"""Selenium web scraping utilities"""
import json
import typing as t
import urllib.error
import urllib.request

import bs4
from mechanicalsoup import Browser


def get_texts_from_url_and_selector(url: str, selector: str) -> t.List[str]:
    """Get the texts of the elements found at the url and selector"""
    elements = get_elements_from_url_and_selector(url=url, selector=selector)
    texts = [element.text for element in elements]
    return texts


def get_elements_from_url_and_selector(
    url: str, selector: str
) -> t.List[bs4.element.Tag]:
    """Get a list of elements found at the url and selector."""
    soup = get_soup_from_url(url)
    elements = list(soup.select(selector))
    return elements


def get_first_element_from_url_and_selector(url: str, selector: str) -> bs4.element.Tag:
    soup = get_soup_from_url(url)
    element = soup.select_one(selector)
    return element


def get_first_text_from_url_and_selector(url: str, selector: str) -> str:
    """Get the text from an element specified by the url and selector."""
    element = get_first_element_from_url_and_selector(url, selector)
    result = element.text
    return result


def get_soup_from_url(url: str) -> bs4.BeautifulSoup:
    with Browser() as browser:
        response = browser.get(url)
    return response.soup


def get_json_from_url(url: str):
    """Returns the page at the given url as JSON"""
    request = urllib.request.Request(
        url,
        data=None,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/35.0.1916.47 Safari/537.36 "
        },
    )

    try:
        page = urllib.request.urlopen(request)
        page_string = page.read().decode("utf-8")
        page_json = json.loads(page_string)
    except urllib.error.URLError:
        page_json = None

    # page_json could be None if page loads as empty
    if page_json is None:
        raise ConnectionError(f"Got no content from {url}")
    return page_json
