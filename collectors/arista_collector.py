import requests
import urllib3
import json
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecurePlatformWarning)
urllib3.disable_warnings(urllib3.exceptions.SNIMissingWarning)

logger = logging.getLogger(__name__)
# Collector must contain collect_data function.
# collect_data() must return a list of documents (dictionaries) to be posted to elastic.
def collect_data(config_data):
    network_inventory = config_data.get('inventory')
    username = config_data.get('network_username')
    password = config_data.get('network_password')

    authdata = {'username': username, 'password': password }
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    docs = []
    for inv_item in network_inventory:
        # initialise counters
        connected = 0
        notconnected = 0
        disabled = 0
        err_disabled = 0
        device = inv_item['hostname']
        ip = inv_item['ip']
        url_login = f'https://{ip}/login'
        # Initialise dictionary
        doc = {'hostname': device}
        device_session = requests.Session()
        # POST authentication data to login
        try:
            response = device_session.post(url_login, data=json.dumps(authdata),
                                                      headers=headers,
                                                      verify=False,
                                                      timeout=3)
        except Exception as e:
            logging.error(str(e))
            device_session.close()
            continue
        # Set HTTPS payload
        payload = {
                    "jsonrpc": "2.0",
                    "method": "runCmds",
                    "params": {
                    "version": 1,
                    "cmds": [ "show interfaces status" ],
                    "format": "json"
                    },
                    "id": "1"
                }
        url_command = f'https://{ip}/command-api'
        response = device_session.post(url_command, data=json.dumps(payload),
                                                    headers=headers,
                                                    verify=False,
                                                    timeout=5)
        device_session.close()

        if response.status_code == 200:
            for interface,intf_info in  response.json()['result'][0]['interfaceStatuses'].items():
                if intf_info['linkStatus'] == 'connected':
                    connected += 1
                elif intf_info['linkStatus'] == 'notconnect':
                    notconnected += 1
                elif intf_info['linkStatus'] == 'disabled':
                    disabled += 1
                elif 'err' in intf_info['linkStatus']:
                    err_disabled += 1
            doc['up'] = connected
            doc['down'] = notconnected
            doc['disabled'] = disabled
            doc['err-disabled'] = err_disabled
            # append to list of docs
            docs.append(doc)
        else:
            logger.error(f'Connection to {device} failed, status code {response.status_code}.')
    return docs

if __name__ == '__main__':
    config_data = {'inventory': [{'hostname': 'evo-eos01', 'ip': '192.168.10.160'}],
                   'network_username': 'admin',
                   'network_password': 'admin'}
    result = collect_data(config_data)
    print(result)