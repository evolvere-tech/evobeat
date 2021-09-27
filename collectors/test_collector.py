import random
import logging

logger = logging.getLogger(__name__)
# Collector must contain collect_data function.
# collect_data() must return a list of documents (dictionaries) to be posted to elastic.
def collect_data(config_data):
    score = random.randrange(10)
    test_docs = [{"beat": "test", "score": score}]
    logger.info(f"test_docs: {test_docs}")
    return test_docs
