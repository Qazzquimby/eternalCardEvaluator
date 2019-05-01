"""Content related to eternal decks"""
from __future__ import annotations

import itertools
import re
import typing
from dataclasses import dataclass

import progiter as progiter

from eternal_collection_guide import url_constants
from eternal_collection_guide.base_learner import DeckSearchLearner
from eternal_collection_guide.browser import Browser
from eternal_collection_guide.card import CardCollection
from eternal_collection_guide.deck_searches import DeckSearch
from eternal_collection_guide.field_hash_collection import FieldHashCollection


@dataclass
class Deck:
    """A deck from EternalWarcry.com"""
    deck_id: str
    card_playsets: typing.List[Playset]
    archetype: str
    last_updated: str
    is_tournament: bool
    success: str

    @classmethod
    def from_deck_url(cls, url: str, browser: Browser, card_collection: CardCollection) -> typing.Optional[Deck]:
        """Creates a Deck from an EternalWarcry URL.

        :param url: The Url for the deck.
        :param browser: Any browser object.
        :param card_collection: A populated CardCollection.
        :return: The Deck object created.
        """
        browser.get(url)
        card_playsets = _get_card_playsets(browser, card_collection)
        if len(card_playsets) == 0:
            return None
        archetype = _get_archetype(browser)
        last_updated = _get_last_updated(browser)

        deck_id = get_deck_id_from_url(url)
        is_tournament = _get_is_tournament_from_url(url)
        success = _get_success(browser)

        deck = cls(deck_id, card_playsets, archetype, last_updated, is_tournament, success)
        return deck


def get_deck_id_from_url(url: str) -> str:
    """Gets the ID EternalWarcry uses to identify a deck from the decks' url.

    Example:
        >>> assert get_deck_id_from_url("https://eternalwarcry.com/decks/details/rqvLRFH426s/chalice") == "rqvLRFH426s"
        >>> assert get_deck_id_from_url("https://eternalwarcry.com/decks/details/dafg4cdEBrY/hooru") == "dafg4cdEBrY"
    """
    id_deck_type_string = _get_id_deck_type_string_from_url(url)
    deck_id = id_deck_type_string.split("/")[0]
    return deck_id


class DeckCollection(FieldHashCollection):
    """A collection of EternalWarcry decks. May correspond to an EternalWarcry deck search.

    self.dict["deck_id"][<some deck id>] = list of decks with that id.
    self.dict[(<set_num>, <card_num>)][number of copies] = list of decks with at least that many copies of the card.
    """
    content_type = Deck

    def __init__(self):
        self.deck_search = None
        super().__init__()

    def _add_to_dict(self, entry: Deck):
        self.dict["deck_id"][entry.deck_id].append(entry)
        for playset in entry.card_playsets:
            for i in range(playset.num_copies):
                self.dict[(playset.set_num, playset.card_num)][i + 1].append(entry)

    @classmethod
    def json_entry_to_content(cls, json_entry: dict) -> Deck:
        """Constructs a Deck from a json_entry representing a deck.

        :param json_entry:
        :return:
        """
        playsets = [Playset(**playset_dict) for playset_dict in json_entry['card_playsets']]
        json_entry['card_playsets'] = playsets

        return Deck(**json_entry)


@dataclass
class Playset:
    """A quantity of a given card."""
    set_num: int
    card_num: int
    num_copies: int

    def __str__(self):
        return f"{self.num_copies}x {self.set_num}-{self.card_num}"

    @classmethod
    def from_export_text(cls, text) -> typing.Optional[Playset]:
        """Creates a playset from a row of a deck or collection export.

        :param text: A single row of the export.
        :return: A playset representing the card on that row.
        """
        numbers = [int(number) for number in re.findall(r'\d+', text)]
        if len(numbers) == 3:
            num_played = numbers[0]
            set_num = numbers[1]
            card_num = numbers[2]
            playset = Playset(set_num, card_num, num_played)
            return playset
        return None


class DeckLearner(DeckSearchLearner):
    """Populates a DeckCollection from decks used in an EternalWarcry deck search."""

    def __init__(self, file_prefix: str, deck_search: DeckSearch, card_collection: CardCollection):
        self.deck_search = deck_search
        self.card_collection = card_collection
        super().__init__(file_prefix, f"{self.deck_search.name}/decks.json", DeckCollection, deck_search)

    def _update_collection(self):
        with Browser() as browser:
            deck_urls = self._get_deck_urls(browser)
            self._prune_outdated_decks(deck_urls)
            self._process_deck_urls(browser, self.card_collection, deck_urls)

    def _get_deck_urls(self, browser: Browser) -> typing.List[str]:
        pages_of_urls = [page_of_urls for page_of_urls in self._page_of_deck_urls_generator(browser)]
        urls = list(itertools.chain(pages_of_urls))
        return urls

    def _page_of_deck_urls_generator(self, browser: Browser):
        for page in itertools.count(start=1):
            items = self._get_deck_urls_on_page(browser, page)
            if items:
                yield from items
            else:
                return

    def _get_deck_urls_on_page(self, browser: Browser, page: int):
        url = f"{self.deck_search.url}&p={page}"
        browser.get(url)
        deck_links = browser.find_elements_by_xpath(
            '//*[@id="body-wrapper"]/div/form[2]/div[2]/table/tbody/tr[*]/td[2]/div[1]/div/a')
        deck_urls = [deck_link.get_attribute("href") for deck_link in deck_links]
        return deck_urls

    def _prune_outdated_decks(self, deck_urls: typing.List[str]):
        new_deck_ids = [get_deck_id_from_url(url) for url in deck_urls]

        pruned_collection = DeckCollection()
        for deck in self.collection.contents:
            if deck.deck_id in new_deck_ids:
                pruned_collection.append(deck)
        self.collection = pruned_collection

    def _process_deck_urls(self, browser: Browser, card_collection: CardCollection, deck_urls: typing.List[str]):
        for deck_url in progiter.ProgIter(deck_urls, desc=f"Adding new {self.deck_search.name} decks"):
            self._process_deck_url(deck_url, browser, card_collection)

    def _process_deck_url(self, deck_url: str,
                          browser: Browser,
                          card_collection: CardCollection):
        matching_decks = self.collection.dict['deck_id'][get_deck_id_from_url(deck_url)]
        if matching_decks:
            return

        deck_data = Deck.from_deck_url(deck_url, browser, card_collection)
        if deck_data:
            self.collection.append(deck_data)


def _get_card_playsets(browser: Browser, card_collection: CardCollection) -> typing.List[Playset]:
    deck_export = _get_deck_export(browser)
    playsets = _get_playsets_from_deck_export(deck_export, card_collection)
    return playsets


def _get_playsets_from_deck_export(deck_export: str, card_collection: CardCollection) -> typing.List[Playset]:
    deck_export_rows = [row for row in deck_export.split("\n") if row != "--------------MARKET---------------"]

    playsets = []
    for row in deck_export_rows:
        playset = _get_playset_from_deck_export_row(row, card_collection)
        if playset:
            _add_playset(playset, playsets)

    return playsets


def _get_playset_from_deck_export_row(row: str, card_collection: CardCollection) -> typing.Optional[Playset]:
    playset = Playset.from_export_text(row)

    matching_cards = card_collection.dict[playset.set_num][playset.card_num]
    if len(matching_cards) == 0:
        playset = None

    return playset


def _add_playset(playset, playsets):
    matching_playset = _get_existing_matching_playset(playset, playsets)
    if matching_playset is not None:
        matching_playset.num_copies += playset.num_copies
    else:
        playsets.append(playset)


def _get_deck_export(browser: Browser) -> str:
    assert browser.current_url.startswith(url_constants.DECK_DETAILS_BASE_URL)
    deck_export_text_area = browser.find_element_by_xpath('//*[@id="export-deck-text"]')
    deck_export = deck_export_text_area.get_attribute("value")
    return deck_export


def _get_archetype(browser: Browser) -> str:
    archetype = browser.find_element_by_xpath('//*[@id="deck-details"]/div[10]/div[2]').text
    return archetype


def _get_last_updated(browser: Browser) -> str:
    last_updated = browser.find_element_by_xpath('//*[@id="deck-details"]/div[11]/div[2]').text
    return last_updated


def _get_is_tournament_from_url(url: str) -> bool:
    id_deck_type_string = _get_id_deck_type_string_from_url(url)
    is_tournament_string = id_deck_type_string.split("/")[1]
    return is_tournament_string == "tournament-deck"


def _get_id_deck_type_string_from_url(url: str) -> str:
    base_url = url_constants.DECK_DETAILS_BASE_URL
    id_deck_type_string = url.replace(base_url, "")
    return id_deck_type_string


def _get_success(browser: Browser) -> str:
    # fixme add assert url
    success = browser.find_element_by_xpath('//*[@id="deck-information-wrapper"]/div[2]').text
    return success


def _get_existing_matching_playset(playset: Playset, playsets: typing.List[Playset]) -> typing.Optional[Playset]:
    for other_playset in playsets:
        sets_match = other_playset.set_num == playset.set_num
        card_nums_match = other_playset.card_num == playset.card_num
        if sets_match and card_nums_match:
            return other_playset
    return None
