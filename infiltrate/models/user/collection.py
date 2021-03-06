"""The cards a user owns"""

import typing as t
import pandas as pd

import infiltrate.browsers as browsers
import infiltrate.card_collections as card_collections
import infiltrate.models.card as card


if t.TYPE_CHECKING:
    from infiltrate.models.user import User


def get_collection_from_ew(user: "User") -> t.Dict[card.CardId, int]:
    if not user.is_authenticated:
        return {}
    url = f"https://api.eternalwarcry.com/v1/useraccounts/collection?key={user.ew_key}"
    response = browsers.get_json_from_url(url)
    cards = response["cards"]
    collection = card_collections.make_collection_from_ew_export(cards)
    return collection


def dataframe_for_user(user: "User") -> pd.DataFrame:  # todo, consider just using dict.
    collection_dict = get_collection_from_ew(user)
    rows = [
        (card_id.set_num, card_id.card_num, count)
        for card_id, count in collection_dict.items()
    ]
    frame = pd.DataFrame(rows, columns=["set_num", "card_num", "count"])
    return frame


def create_is_owned_series(
    card_details: pd.DataFrame, ownership: pd.DataFrame
) -> pd.Series:
    """Makes a series matching the card copies in card_details for if that many copies
    are owned."""
    full_ownership = pd.concat(
        [ownership.assign(count_in_deck=i) for i in range(1, 5)], axis=0
    ).set_index(["set_num", "card_num", "count_in_deck"])

    details_with_total_owned = card_details.join(full_ownership)

    ownership_frame = details_with_total_owned[
        ["set_num", "card_num", "count_in_deck"]
    ].copy()

    # noinspection PyTypeChecker
    is_owned = (
        details_with_total_owned["count_in_deck"] <= details_with_total_owned["count"]
    )
    ownership_frame.loc[:, "is_owned"] = is_owned
    return ownership_frame
