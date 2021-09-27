import random
import logging

logger = logging.getLogger(__name__)
# The inventory() function is optional. If not present, static inventory must be provided in the config.yaml file.
# Any valid python object may be returned. It is passed to collector function as config_data["inventory"].

def inventory(config_data):
    dynamic_inventory = [{"hostname": "dynamic.evolvere-tech.com",
                          "ip": "1.1.1.2"}]
    return dynamic_inventory

# Collector must contain collect_data function.
# collect_data() must return a list of documents (dictionaries) to be posted to elastic.
def collect_data(config_data):
    test_inventory = config_data["inventory"]
    score = random.randrange(10)
    test_docs = [{"beat": "test", "score": score}]
    logger.info(f"inventory: {test_inventory} docs: {test_docs}")
    return test_docs
