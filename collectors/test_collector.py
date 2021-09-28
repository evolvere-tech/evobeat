import random
import logging

logger = logging.getLogger(__name__)
# Collector must contain collect_data function.
# collect_data() must return a list of documents (dictionaries) to be posted to elastic.
def collect_data(config_data):
    docs = []
    inventory = config_data.get('inventory')
    for inv_item in inventory:
        device = inv_item['hostname']
        ip = inv_item['ip']
        score = random.randrange(10)
        docs.append({"beat": "test", "score": score, "hostname": device, "ip": ip})
    logger.info(f"docs: {docs}")
    return docs

if __name__ == '__main__':
    # Use this config_data when running directly
    config_data = { 'inventory': [{'hostname': 'static.evolvere-tech.com', 'ip': '1.1.1.1'}],
                    'env': 'dev',
                    'dc': 'lab'
    }
    docs = collect_data(config_data)
    print(docs)