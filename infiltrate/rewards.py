import collections
import functools
import typing as t

import numpy as np

import infiltrate.caches as caches
import infiltrate.models.card as card
import infiltrate.models.card_set as card_sets
import infiltrate.models.rarity as rarities

if t.TYPE_CHECKING:
    import infiltrate.card_evaluation as card_evaluation

DAYS_IN_WEEK = 7


class CardClass:
    """A pool of cards from which drops are chosen."""

    def __init__(
        self,
        rarity: rarities.Rarity,
        sets: t.Optional[t.List[card_sets.CardSet]] = None,
        is_premium=False,
    ):
        self.sets = sets
        if self.sets is None:
            self.sets = card_sets.get_main_sets()

        self.rarity = rarity

        self.is_premium = is_premium

    @property
    @functools.lru_cache(maxsize=1)
    def num_cards(self) -> int:  # todo cache this
        """The total number of cards in the pool."""
        session = card.db.session

        sets = self.sets

        set_nums = card_sets.get_set_nums_from_sets(sets)
        count = (
            session.query(card.Card)
            .filter(card.Card.set_num.in_(set_nums))
            .filter(card.Card.rarity == self.rarity.name)
            .count()
        )
        return count

    def __eq__(self, other):
        is_equal = (
            self.sets == other.sets
            and self.rarity == other.rarity
            and self.is_premium == other.is_premium
        )
        return is_equal

    def __hash__(self):
        sets = tuple(self.sets)
        hash_value = hash((sets, self.rarity, self.is_premium))
        return hash_value

    def get_value(self, card_data) -> float:
        set_values = [
            self._get_value_for_set(card_data, card_set) for card_set in self.sets
        ]

        avg_set_value = sum(set_values) / len(set_values)
        return avg_set_value

    def _get_value_for_set(self, card_data, card_set: card_sets.CardSet) -> float:
        return _get_value_for_set_and_rarity(card_data, card_set, self.rarity)

    def __str__(self):
        return f"{tuple(self.sets)} {self.rarity}, premium {self.is_premium}"


@functools.lru_cache(maxsize=200)
def _get_value_for_set_and_rarity(
    card_data: "card_evaluation.OwnValueFrame",
    card_set: card_sets.CardSet,
    rarity: rarities.Rarity,
) -> float:
    cards_in_set_and_rarity = card_data[
        np.logical_and(
            card_data["set_num"] == card_set.set_num, card_data["rarity"] == rarity,
        )
    ]

    value = get_value(cards_in_set_and_rarity)
    return value


def get_value(card_pool):  # called many times and slow
    is_owned = card_pool["is_owned"] == True
    unowned_cards = card_pool[~is_owned]
    findable_copies = unowned_cards.drop_duplicates(["set_num", "card_num"])
    unowned_value = sum(findable_copies["own_value"])

    fully_owned_cards = card_pool[
        np.logical_and(is_owned, card_pool["count_in_deck"] == 4)
    ]
    owned_value = sum(fully_owned_cards["resell_value"])

    try:
        average_value = (owned_value + unowned_value) / (len(card_pool) / 4)
        return average_value
    except ZeroDivisionError:
        return 0


class DraftPackCardClass(CardClass):
    """A pool of cards from from a draft pack, instead of a set."""

    def __init__(self, rarity: rarities.Rarity):
        super().__init__(rarity, None, False)
        self.sets = ["DRAFT"]

    @property
    @functools.lru_cache(maxsize=1)
    def num_cards(self) -> int:
        """The total number of cards in the pool."""
        session = card.db.session

        count = (
            session.query(card.Card)
            .filter(card.Card.is_in_draft_pack is True)
            .filter(card.Card.rarity == self.rarity)
            .count()
        )  # Check that the rarity equality is correct
        return count

    def __eq__(self, other):
        is_equal = (
            self.sets == other.sets
            and self.rarity == other.rarity
            and self.is_premium == other.is_premium
        )
        return is_equal

    def __hash__(self):
        hash_value = hash((self.sets, self.rarity, self.is_premium))
        return hash_value

    def get_value(self, card_data) -> float:
        cards_in_draft_pack_and_rarity = card_data[
            np.logical_and(
                card_data["is_in_draft_pack"] == True,
                card_data["rarity"] == self.rarity,
            )
        ]
        value = get_value(cards_in_draft_pack_and_rarity)
        return value


class CardClassWithAmount:
    """The number of card drops from the Card Class per reward."""

    def __init__(self, card_class: CardClass, amount: float = 1):
        self.card_class: CardClass = card_class
        self.amount: float = amount

    def get_value(self, card_data) -> float:
        value_for_card_class = self.card_class.get_value(card_data)
        value_for_card_class *= self.amount
        return value_for_card_class

    def __str__(self):
        return f"{self.amount}x {self.card_class}"


class CardClassWithAmountPerWeek:
    """The number of card drops from the Card Class found per week
     on average."""

    def __init__(self, card_class: CardClass, amount_per_week: float):
        self.card_class = card_class
        self.amount_per_week = amount_per_week

    @property
    def chance_of_specific_card_drop_per_week(self) -> float:
        """The probability of a specific card from the pool being found
         in a week."""
        num_cards = self.card_class.num_cards
        one_chance = 1 / num_cards

        chance_of_none = (1 - one_chance) ** self.amount_per_week
        chance_of_at_least_one = 1 - chance_of_none
        return chance_of_at_least_one


class PlayerRewards:  # TODO Make into model to persist
    def __init__(
        self,
        first_wins_per_week,
        drafts_per_week,
        ranked_wins_per_day,
        unranked_wins_per_day,
    ):
        self.first_wins_per_week = first_wins_per_week
        self.drafts_per_week = drafts_per_week
        self.ranked_wins_per_day = ranked_wins_per_day
        self.unranked_wins_per_day = unranked_wins_per_day

        self.rewards_with_rates = self.get_rewards_per_week()

        # This could be its own object PlayerDrops
        self.card_classes_with_amounts_per_week = (
            self.get_card_classes_with_amounts_per_week()
        )

    def get_rewards_per_week(self):
        """Get the rewards the player will find in a week on avg."""
        rewards_with_rates = [
            RewardsPerWeek(FIRST_WIN_OF_THE_DAY, self.first_wins_per_week)
        ]

        ranked_silvers = min(3, self.ranked_wins_per_day // 3) * DAYS_IN_WEEK

        ranked_bronzes = (self.ranked_wins_per_day * DAYS_IN_WEEK) - ranked_silvers
        unranked_bronzes = self.unranked_wins_per_day * DAYS_IN_WEEK

        rewards_with_rates.append(
            RewardsPerWeek(BRONZE_CHEST, ranked_bronzes + unranked_bronzes)
        )
        rewards_with_rates.append(RewardsPerWeek(SILVER_CHEST, ranked_silvers))

        # TODO add draft info
        # Draft pack pools can be found here
        #   https://eternalwarcry.com/cards/download

        # TODO Get avg chests from quests
        # TODO Get base chest drops, and reroll chest drops

        return rewards_with_rates

    def get_card_classes_with_amounts_per_week(
        self,
    ) -> t.List[CardClassWithAmountPerWeek]:
        card_classes_with_amounts_per_week_dict = collections.defaultdict(int)
        for reward_with_rate in self.rewards_with_rates:
            drops_per_week = reward_with_rate.drops_per_week

            card_classes_with_amounts = reward_with_rate.reward.card_class_amounts

            for card_class_with_amount in card_classes_with_amounts:
                card_class = card_class_with_amount.card_class
                amount = card_class_with_amount.amount
                card_classes_with_amounts_per_week_dict[card_class] += (
                    amount * drops_per_week
                )
        card_classes_with_amounts_per_week = [
            CardClassWithAmountPerWeek(
                card_class=key,
                amount_per_week=card_classes_with_amounts_per_week_dict[key],
            )
            for key in card_classes_with_amounts_per_week_dict.keys()
        ]

        return card_classes_with_amounts_per_week

    @caches.mem_cache.cache(f"player_rewards_findabilities", expires=120)
    def get_chance_of_specific_card_drop_in_a_week(
        self, rarity: rarities.Rarity, card_set: card_sets.CardSet
    ):
        chances = []
        for card_class_with_amount in self.card_classes_with_amounts_per_week:
            rarity_match = rarity == card_class_with_amount.card_class.rarity

            set_nums = card_sets.get_set_nums_from_sets(
                card_class_with_amount.card_class.sets
            )

            set_match = card_set.set_num in set_nums
            if rarity_match and set_match:
                chance = card_class_with_amount.chance_of_specific_card_drop_per_week
                chances.append(chance)
        chance_of_at_least_one = get_chance_of_at_least_one(chances)
        return chance_of_at_least_one


def get_chance_of_at_least_one(probabilities):
    chance_of_none = 1
    for prob in probabilities:
        inverse = 1 - prob
        chance_of_none *= inverse
    chance_of_at_least_one = 1 - chance_of_none
    return chance_of_at_least_one


class Reward:
    """Something a player can be given in response to a purchase,
    such as league results."""

    def __init__(
        self,
        card_classes: t.Optional[
            t.List[t.Union[CardClassWithAmount, CardClass]]
        ] = None,
        gold: int = 0,
        shiftstone: int = 0,
    ):
        self.card_class_amounts = card_classes
        if self.card_class_amounts is None:
            self.card_class_amounts = []
        self.change_card_classes_to_card_classes_with_amounts()

        self.gold = gold
        self.shiftstone = shiftstone

    def change_card_classes_to_card_classes_with_amounts(self):
        new_card_classes_with_amounts = []
        for card_class in self.card_class_amounts:
            if type(card_class) is CardClass:
                card_class = CardClassWithAmount(card_class)
            new_card_classes_with_amounts.append(card_class)
        self.card_class_amounts = new_card_classes_with_amounts

    def __eq__(self, other):
        is_equal = (
            self.card_class_amounts == other.card_class_amounts
            and self.gold == other.gold
            and self.shiftstone == other.shiftstone
        )
        return is_equal

    def get_value(self, card_data) -> float:
        total_value = 0
        # todo use shiftstone
        # todo make alternative value using gold as well. Don't use it for default
        #  purchases because it would lead to "buy this so that you can spend
        #  the gold on something better" situations
        for card_class_with_amount in self.card_class_amounts:
            value_for_card_class = card_class_with_amount.get_value(card_data)

            total_value += value_for_card_class

        return total_value


def get_pack_contents_for_sets(sets: t.List[card_sets.CardSet]):
    card_classes_with_amounts = [
        CardClassWithAmount(
            card_class=CardClass(rarity=rarity, sets=sets), amount=rarity.num_in_pack
        )
        for rarity in rarities.RARITIES
    ]
    return card_classes_with_amounts


def get_draft_pack_contents():
    contents = [
        CardClassWithAmount(card_class=DraftPackCardClass(rarity=rarity))
        for rarity in rarities.RARITIES
    ]
    return contents


class RewardsPerWeek:
    """A reward with a frequency of deliveries per week."""

    def __init__(self, reward: Reward, drops_per_week: float):
        self.reward = reward
        self.drops_per_week = drops_per_week


WOOD_CHEST = Reward(gold=24)
BRONZE_CHEST = Reward(
    gold=40,
    card_classes=[CardClassWithAmount(card_class=CardClass(rarity=rarities.COMMON))],
)
SILVER_CHEST = Reward(
    gold=225,
    card_classes=[CardClassWithAmount(card_class=CardClass(rarity=rarities.UNCOMMON))],
)
GOLD_CHEST = Reward(
    gold=495, card_classes=get_pack_contents_for_sets(card_sets.get_old_main_sets()),
)

DIAMOND_CHEST = Reward(
    gold=1850,
    card_classes=(
        get_pack_contents_for_sets(card_sets.get_old_main_sets())
        + [CardClassWithAmount(CardClass(rarity=rarities.UNCOMMON, is_premium=True))]
    ),
)

CARD_PACKS = {
    card_set: Reward(card_classes=get_pack_contents_for_sets([card_set]))
    for card_set in card_sets.get_main_sets()
}

DRAFT_PACK = Reward(card_classes=get_draft_pack_contents())

FIRST_WIN_OF_THE_DAY = Reward(
    card_classes=get_pack_contents_for_sets([card_sets.get_newest_main_set()])
)

DEFAULT_PLAYER_REWARD_RATE = PlayerRewards(
    first_wins_per_week=6.3,
    drafts_per_week=0.3,
    ranked_wins_per_day=3.5,
    unranked_wins_per_day=0,
)
