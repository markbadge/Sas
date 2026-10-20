"""Replay equivalence: ssengine.Game must match moderator14 (the oracle) on identical random play."""
import pytest

from oracle import play_seed


@pytest.mark.parametrize('seed', list(range(1, 41)))
def test_matches_moderator14(seed):
    play_seed(seed)


@pytest.mark.parametrize('seed', list(range(100, 112)))
def test_bot_text_matches_moderator_files(seed):
    """Bot prompts are the moderator's act/result/talk templates (modulo the private Call outcomes we add)."""
    play_seed(seed, texts=True)
