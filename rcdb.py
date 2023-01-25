from bs4 import BeautifulSoup
import requests
import re
import logging
from datetime import datetime
from requests.exceptions import RequestException
from coaster import Coaster, Track
from dataclasses import asdict
from ratelimit import sleep_and_retry, limits
from concurrent.futures import ThreadPoolExecutor
import Levenshtein
from mongo import load_coaster, store_coaster
from toomanyresults import TooManyResultsError

BASE_URL = 'https://rcdb.com'
SEARCH_URL = f'https://rcdb.com/iqs.json'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_search_results(query: str) -> list[str]:
    """Returns the IDs for 
    Uses the rcdb search bar to find roller coasters starting with query, 
    and returns the page ID for each result 
    """
    # q is the actual query, the other keys do not matter in this context
    # but they need to be included to avoid errors
    payload = {'q': query, 's': 0, 'w': 0, 'h': 0, 'r': 0}

    try:
        response_json = requests.post(SEARCH_URL, files=payload).json()
    except RequestException:
        logger.exception()
        return []

    results = response_json['results']
    page_ids = [result['l'] for result in results]
    if page_ids and 'qs' in page_ids[0]:
        raise TooManyResultsError()
    # sometimes search results are actually pages of other search results and not real results :)
    ids = [page_id[1:-4] for page_id in page_ids if 'qs' not in page_id]
    return ids


def convert_date(date: str) -> str:
    """Converts from multiple possible formats to one format"""

    if re.match('\d+-\d+-\d+', date):
        return datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d/%y')
    elif re.match('\d+-\d+', date):
        return datetime.strptime(date, '%Y-%m').strftime('%m/%Y')
    elif re.match('\d+', date):
        return date
    else:
        return ''


@sleep_and_retry
@limits(calls=100, period=30)
def fetch_page(url: str) -> str | None:
    """Gets the http text response of the page at the specified url

    - Only 100 pages can be fetched per 30 seconds
    - Returns None if there was an issue fetching the page
    """
    try:
        logger.info(f"sending request to {url}")
        return requests.get(url).text
    except RequestException:
        logger.exception()
        return None


def num_of_tracks(soup: BeautifulSoup) -> int:
    """Returns number of tracks a page for a coaster """
    track_columns = soup.select(
        'body > section:nth-child(3) > table > tbody > tr:first-of-type > td')
    return len(track_columns) if track_columns else 0


def build_coaster(_id: str) -> Coaster | None:
    """Builds a coaster object with the specified _id
    - If the coaster is in the database it will fetch the info from the database
    - If the coaster isn't in the database it will construct it from url
     """
    if coaster := load_coaster(_id):
        return coaster
    elif coaster := build_coaster_from_url(_id):
        if coaster.name != 'unknown':
            store_coaster(coaster)
        return coaster
    else:
        return None


def build_coaster_from_url(_id: str) -> Coaster | None:
    """Constructs a coaster object based on the given page id"""
    url = f'{BASE_URL}/{_id}.htm'
    page = fetch_page(url)

    soup = BeautifulSoup(page, 'lxml')

    if not is_page_a_coaster(soup):
        logger.warning(
            f'Bad URL passed: {url} was not an rcdb page for a roller coaster')
        return None

    coaster = Coaster()

    coaster._id = _id
    coaster.name = soup.find('h1').text

    manufacturer_tag = soup.select_one(
        '.scroll > p:first-child > a:first-child')
    coaster.manufacturer = manufacturer_tag.text if manufacturer_tag else None

    park_tag = soup.select_one('#feature > div:first-child > a:first-of-type')
    coaster.park = park_tag.text if park_tag else None

    country_tag = soup.select_one(
        '#feature > div:first-child > a:last-of-type')
    coaster.country = country_tag.text if country_tag else None

    image_tag = soup.select_one('#opfAnchor')
    coaster.image_url = f"{BASE_URL}{image_tag['data-url']}" if image_tag else None

    date_tag = soup.select_one('time:first-of-type')
    if date_tag:
        datetime_attr = date_tag['datetime']
        parent_tag = date_tag.parent
        if 'SBNO' in parent_tag.text:
            coaster.sbno_date = convert_date(
                datetime_attr) if datetime_attr else None
            former_status_tag = soup.find('a', string='Operated')
            coaster.opening_date = convert_date(former_status_tag.find_next('time')[
                                                'datetime']) if former_status_tag else None
        elif 'Operated' in parent_tag.text:
            coaster.closing_date = convert_date(
                soup.select_one('time:last-of-type')['datetime'])
            coaster.opening_date = convert_date(
                datetime_attr) if datetime_attr else None
        elif 'Operating' in parent_tag.text:
            coaster.opening_date = convert_date(
                datetime_attr) if datetime_attr else None

    coaster.tracks = parse_tracks(soup)

    return coaster


def is_page_a_coaster(soup: BeautifulSoup) -> bool:
    """Checks if the title for the page fits the format used for coasters"""
    roller_coaster_link = soup.select_one(
        '#feature > ul:first-of-type > li > a')
    return roller_coaster_link is not None and 'Coaster' in roller_coaster_link.text


def parse_tracks(soup: BeautifulSoup) -> list[Track]:
    tracks = []
    num_tracks = num_of_tracks(soup)
    for i in range(num_tracks):
        tracks.append(init_track(soup, i))

    if len(tracks) > 1 and tracks[0].name is None:
        for i, track in enumerate(tracks, start=1):
            track.name = f'Track {i}'

    return tracks


def init_track(soup: BeautifulSoup, track_num: int) -> Track | None:
    """Initializes a track object using info from the stats table provided"""
    track = Track()
    track_fields = track.__dict__

    stats_headers = soup.select('body > section:nth-child(3) > table th')
    if stats_headers is None:
        return None

    # All the table headers in the table that match the fields we're looking for
    headers = [th for th in stats_headers if th.text.lower() in track_fields]

    for th in headers:
        field_name = th.text.lower()
        if field_name == 'name':
            # For the name we want the entire value of the td
            setattr(track, field_name, th.find_next_siblings(
                'td')[track_num].text)
        else:
            setattr(track, field_name, th.find_next_siblings(
                'td')[track_num].text.split(' ')[0])
    return track


def safe_build_coaster(url: str) -> Coaster | None:
    try:
        return build_coaster(url)
    except Exception:
        logger.exception(f'Something went wrong with fetching data from {url}')


def get_coasters(name: str, park: str) -> list[Coaster]:
    """Returns a list of Coasters that have names starting with name"""
    urls = get_search_results(name)

    with ThreadPoolExecutor(100) as p:
        coasters = p.map(safe_build_coaster, urls)

    coasters = [c for c in coasters if c]
    if park:
        coasters = [c for c in coasters if _name_is_similar(c, park)]
    return coasters


def _name_is_similar(query, park_name):
    distance = Levenshtein.distance(
        query, park_name, processor=lambda x: x.lower())
    return query.lower() in park_name.lower() or distance < 5


if __name__ == '__main__':
    scrape_it_all()
