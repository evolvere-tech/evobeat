# HOW TO WRITE A COLLECTOR #

Development guide for evobeat data collectors.

### Overview ###
* evobeat provides common methods to collect data from devices and POST documents to elastic-search.
* This guide shows how to write a data collector

### Clone and install evobeat
    git clone repository
    create virtualenv:
    ```
    python3 -m venv ./venv
    source ./venv/bin/activate
    pip install -r requirements.txt
    ```
### Test with the test_collector
Edit ```configs/test_collector.yaml``` and update elastic parameters to connect to elasticsearch.

Check that the test collector runs OK.
```
./evobeat.py test --name test_collector
```
### Create a new collector
Copy ```configs/test_collector.yaml``` to ```configs/new_collector.yaml```.
Copy ```collectors/test_collector.py``` to ```collectors/new_collector.py```.

### Edit new_collector.py
Set config_data dictionary to any parameters the collector may need (hostnames, ip addresses etc).
```
    config_data = { 'device': 'device_name'}
```
This is for testing only, collector will use yaml parameters when developed.

Put your code between ```def collect_data(config_data)``` and ```return```. 

```
def collect_data(config_data):
    docs = []                                # Initialise list to store elastic docs
    device = config_data.get('device_name')  # Retrieve arguments from config_data
    # Connect to device using API/SSH, issue commands and store responses
    # Return data as list of dictionaries. Usually best to include unique name values.
    doc = {'device_name': device, 'data': 'data_from_device'}
    docs.append(doc)
    return docs
```
Run the script from the command-line/IDE to verify data is collected and formatted.

### Edit new_collector.yaml
Remove any lines after ```# Collector Parameters```.
Set the config_data for your collector in YAML format after the ```# Collector Parameters```.
```
    # Collector Parameters
    device: device_name
```

### Run new_collector in test mode
Data will be displayed, but not posted to elastic.
```
./evobeat.py test --name new_collector
```

### Run new_collector
Check that ```elastic_index:``` is to the index you wish to post to. Note that evobeat will automatically add date suffix to the index name.
Check that interval is set to the time in seconds between each collection.
``
./evobeat.py run --name new_collector
```
