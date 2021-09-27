import logging
import netmiko
import json
import os
import sys
import time

# The inventory() function is optional. If not present, static inventory must be provided in the config.yaml file.
# Any valid python object may be returned. It is passed to collector function as config_data["inventory"]

def inventory(config_data):
    dynamic_inventory = [{"hostname": "dynamic.evolvere-tech.com",
    "ip": "1.1.1.2"}]

    return dynamic_inventory

# Collector must contain collect_data function
# collect_data() must return a list of documents (dictionaries) to be posted to elastic

class NetCollector():

    def __init__(self, **kwargs):
        f_name = sys._getframe().f_code.co_name
        self.connected = False
        self.device_shell = ""
        self.collected_docs = []
        if kwargs:
            try:
                self.username = kwargs["username"]
                self.password = kwargs["password"]
                self.device = kwargs["device"]
                self.ip = kwargs["ip"]
                self.site = kwargs["site"]
                self.netmiko_device_type = kwargs["netmiko_device_type"]
                self.op_list = kwargs["op_list"]
                self.logger = kwargs["logger"]
            
            except Exception:
                self.logger.error(f'Network Collector ({f_name}) - missing connection parameters.')
            else:
                if self.op_list:
                    self.ssh_connect()
                    if self.connected:
                        for op in self.op_list:
                            if self.netmiko_device_type == 'arista_eos':
                                pass
                            
                            elif self.netmiko_device_type == 'cisco_ios':
                                pass
                            
                            elif self.netmiko_device_type == 'cisco_nxos':
                                if op == 'port_capacity':
                                    self.nexus_port_capacity()
                                if op == 'device_inventory':
                                    self.nexus_inventory()
                        
                        self.ssh_disconnect()

                    else:
                        self.logger.error(f'Network Collector ({f_name}) - failed to connect to device {self.device}.')
                
                else:
                    self.logger.error(f'Network Collector ({f_name}) - operations list empty for device {self.device}'\
                        ', nothing to do.')
        else:
            self.logger.error(f'Network Collector ({f_name}) - missing connection parameters.')

    def ssh_connect(self):
        f_name = sys._getframe().f_code.co_name
        try:
            if self.netmiko_device_type == 'cisco_nxos':
                global_delay_factor = 3
            else:
                global_delay_factor = 1
            
            self.device_shell = netmiko.ConnectHandler(device_type='cisco_ios',
                                                       ip=self.ip,
                                                       username=self.username,
                                                       password=self.password,
                                                       global_delay_factor=global_delay_factor)

            self.prompt = self.device_shell.find_prompt()
            self.device_shell.disable_paging()
            self.connected = True

        except Exception as error:
            self.logger.error(f'Network Collector ({f_name}) - Failed to connect to device {self.device}.')
            self.logger.error(str(error))
        
        return

    def ssh_disconnect(self):
        f_name = sys._getframe().f_code.co_name
        """ Netmiko Disconnect from Device """
        try:
            self.device_shell
        
        except Exception as error:
            self.logger.error(f'Network Collector ({f_name}) - Failed to disconnect from device {self.device}.')
            self.logger.error(str(error))

        return

    
    def fixed_length_parser(self,output):
        output_lines = []
        for line in output.split('\n'):
            if line and not line.startswith('-'):
                output_lines.append(line)
        header = output_lines[0].split()
        header_line = output_lines[0]
        result_list = []
        for line in output_lines[1:]:
            result_line = ''
            idx_start = 0
            for item in header[1:]:
                idx_end = header_line.index(item)
                if idx_start != 0:
                    while line[idx_start -1] != ' ':
                        idx_start -= 1
                idx_end_temp = idx_end
                while line[idx_end_temp - 1] != ' ':
                    idx_end_temp -= 1
                result_line += line[idx_start:idx_end_temp].strip() + '|'
                if item == header[-1]:
                    result_line += line[idx_end:].strip()
                idx_start = idx_end
            result_list.append(result_line)

        return result_list

    def nexus_port_capacity(self):

        f_name = sys._getframe().f_code.co_name

        try:
            ports_total = ports_disabled = ports_up = ports_down = 0
            cmd = 'show interface status | json'
            output = self.device_shell.send_command_expect(cmd, expect_string=self.prompt)

            data = json.loads(output)

            if data:

                for port in data['TABLE_interface']['ROW_interface']:
                    if port['interface'].startswith('Eth'):
                        ports_total += 1
                        if port['state'] == 'disabled':
                            ports_disabled += 1
                        elif port['state'] == 'notconnect':
                            ports_down += 1
                        elif port['state'] == 'connected':
                            ports_up += 1

                ports_free = ports_total - ports_up
                ports_util_percent = 100*ports_up/ports_total

                self.collected_docs.append({'device': self.device,
                                            'site': self.site,
                                            'ports_total': ports_total,
                                            'ports_free': ports_free,
                                            'ports_disabled': ports_disabled,
                                            'ports_down': ports_down,
                                            'ports_util_percent': round(ports_util_percent, ndigits=1),
                                            'ports_up': ports_up})
                print(self.collected_docs)

        except Exception as error:
            self.logger.error(f'Network Collector ({f_name}) - failed to collect and parse data.')
            self.logger.error(str(error))

        return

    def nexus_inventory(self):

        f_name = sys._getframe().f_code.co_name

        try:
            cmd = 'show mod | json'
            output = self.device_shell.send_command_expect(cmd, expect_string=self.prompt)

            data = json.loads(output)

            if data:
                model = data['TABLE_modinfo']['ROW_modinfo']['model']
                sw_version = data['TABLE_modwwninfo']['ROW_modwwninfo']['sw']
                serial = data['TABLE_modmacinfo']['ROW_modmacinfo']['serialnum']
                self.collected_docs.append({'device': self.device,
                                            'site': self.site,
                                            'sw_version': sw_version,
                                            'serial': serial,
                                            'model': model})

        except Exception as error:
            self.logger.error(f'Network Collector ({f_name}) - failed to collect and parse data.')
            self.logger.error(str(error))

        return   
    
def collect_data(config_data):
    logger = logging.getLogger(config_data.get("args_name"))
    network_collector_docs = []
    network_inventory = config_data["inventory"]
    username = config_data["network_username"]
    password = config_data["network_password"]
    for inv_item in network_inventory:
        device = inv_item['hostname']
        netmiko_device_type = inv_item["netmiko_device_type"]
        ip = inv_item["ip"]
        site = inv_item["site"]
        op_list = inv_item["op"]
        logger.info(f'Network Collector - collecting telemetry from Device {device}.')
        collected_docs = NetCollector(device=device, netmiko_device_type=netmiko_device_type,
                                      ip=ip, username=username, password=password, site=site,
                                      op_list=op_list, logger=logger).collected_docs

        if collected_docs:
            network_collector_docs += collected_docs

    return network_collector_docs
