# README #

Elastic search data collector for infrastructure.

### Overview ###
* evobeat provides common methods to collect data from devices and POST documents to elastic-search.

### Deployment ###
#### Dependencies
* Python 3.6
* Python Virtualenv
#### Clone and install
    git clone repository
    create virtualenv:
    ```
    python3 -m venv ./venv
    source ./venv/bin/activate
    pip install -r requirements.txt
    ```
#### Collector modules
As infrastructure has bespoke APIs (or no API at all), evobeat requires collector modules to retrieve data.
Collector modules must be stored in the ```collectors``` directory.
A collector module must contain a ```collect_data()``` function which return a list of elastic documents. An elastic document is a Python dictionary.

A sample ```test_collector``` is provided.

#### YAML configuration files.
Confguration files are used to provide configuration data to evobeat. They must be stored in the ```configs``` directory.
A sample configuration file ```test_collector.yaml``` is provided.

### Test with the test_collector
```
./evobeat.py test --name test_collector
```

### Running evobeat
Test that the YAML configuration is valid:
```
./evobeat.py test --name <config>
```

where config is name of YAML file without the .yaml suffix.

Run an evobeat collector:
```
./evobeat.py run --name <config>
