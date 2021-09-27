#!/usr/bin/env python
import sys
import re
import requests
import json
import datetime
import urllib3
import yaml
import logging
from logging import StreamHandler
from pprint import pprint
from getpass import getpass

class Apic():
    # APIC login, connect and disconnect functions
    def __init__(self, **kwargs):
        self.version = '1.0.1'
        self.can_connect = ''
        self.fabric = []
        self.fabric_name = ''
        self.fabric_inventory = []
        self.apic_address = None
        self.cookie = None
        self.headers = {'content-type': "application/json", 'cache-control': "no-cache"}
        self.epg_names = []
        self.idict = {}
        self.epgs = {}
        self.username = ''
        self.password = ''
        self.site = ''
        self.session = requests.Session()
        self.refresh_time_epoch = 0
        if kwargs:
            self.fabrics = kwargs['fabrics']
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        urllib3.disable_warnings(urllib3.exceptions.InsecurePlatformWarning)
        urllib3.disable_warnings(urllib3.exceptions.SNIMissingWarning)

    def login(self, args):
        """Usage: login [FABRIC_NAME]"""
        msgs = []
        error_msgs = []
        if self.can_connect:
            try:
                self.disconnect()
            except:
                pass
        self.can_connect = ''
        if len(args) == 0:
            msg = "Usage: login [FABRIC_NAME]"
            msgs.append(msg)
            return {'rc': 1, 'info': msgs}
        else:
            parameter_values = args.split()
            fabric_name = parameter_values[0]
            if fabric_name in self.fabrics.keys():
                self.fabric = self.fabrics[fabric_name]
                self.fabric_name = fabric_name
                for apic_credentials in self.fabric:
                    if not self.username or not self.password:
                        if not apic_credentials['username'] or not apic_credentials['password']:
                            self.username = raw_input('Enter username: ')
                            self.password = getpass()
                        else:
                            self.username = apic_credentials['username']
                            self.password = apic_credentials['password']

                    address = apic_credentials['address']
                    if 'site' in apic_credentials:
                        self.site = apic_credentials['site']
                    else:
                        msg = '"site" missing from APIC credentials.'
                        error_msgs.append(msg)
                        return {'rc': 1, 'error': error_msgs}
                    connection_result = self.connect(address=address, username=self.username, password=self.password)
                    if connection_result['rc'] == 0:
                        self.can_connect = parameter_values[0]
                        msg = 'Established connection to APIC in fabric', self.can_connect
                        msgs.append(msg)
                        return {'rc': 0, 'info': msgs}

                if not self.can_connect:
                    msg = 'Cannot connect to APIC in fabric {}'.format(fabric_name)
                    error_msgs.append(msg)
                    return {'rc': 1, 'error': error_msgs}

            msg = 'ERROR: Missing connection parameters for FABRIC {0}'.format(fabric_name)
            error_msgs.append(msg)
            return {'rc': 1, 'error': error_msgs}

    def connect(self, **kwargs):
        if kwargs:
            error_msgs = []
            apic_user = kwargs['username']
            apic_password = kwargs['password']
            apic_address = kwargs['address']
            uri = "https://{0}/api/aaaLogin.json".format(apic_address)
            payload = {'aaaUser': {'attributes': {'name': apic_user, 'pwd': apic_password}}}
            try:
                response = self.session.post(uri, data=json.dumps(payload), headers=self.headers, verify=False,
                                             timeout=10)
                if response.status_code == 200:
                    self.cookie = {'APIC-cookie': response.cookies['APIC-cookie']}
                    self.apic_address = apic_address
                    self.refresh_time_epoch = int(datetime.datetime.now().strftime('%s'))
                    return {'rc': 0}
                else:
                    msg = 'ERROR: Failed to connect to APIC {0}, error code {1}'.format(apic_address,
                                                                                        response.status_code)
                    error_msgs.append(msg)
                    return {'rc': 1, 'error': error_msgs}
            except:
                msg = 'ERROR: Failed to connect to {}'.format(apic_address)
                error_msgs.append(msg)
                return {'rc': 1, 'error': error_msgs}
        else:
            pass

    def disconnect(self):
        try:
            self.session.close()
        except:
            pass

    def refresh_connection(self, timeout=90):
        error_msgs = []
        try:
            current_time_epoch = int(datetime.datetime.now().strftime('%s'))

            if current_time_epoch - self.refresh_time_epoch >= timeout:
                apic_user = self.username
                apic_password = self.password
                apic_address = self.apic_address
                uri = "https://{0}/api/aaaLogin.json".format(apic_address)
                payload = {'aaaUser': {'attributes': {'name': apic_user, 'pwd': apic_password}}}
                response = self.session.post(uri, data=json.dumps(payload), headers=self.headers, verify=False)
                if response.status_code == 200:
                    self.cookie = {'APIC-cookie': response.cookies['APIC-cookie']}
                    self.apic_address = apic_address
                    self.refresh_time_epoch = int(datetime.datetime.now().strftime('%s'))
                else:
                    msg = 'No connection to Fabric {0}'.format(self.can_connect)
                    error_msgs.append(msg)
                    self.can_connect = ''

        except Exception:
            msg = 'No connection to Fabric {0}'.format(self.can_connect)
            error_msgs.append(msg)
            self.can_connect = ''

        if error_msgs:
            return {'rc': 1, 'error': error_msgs}
        else:
            return {'rc': 0}
    #
    # ACI Fabric functions
    #
    def aci_get_class(self, class_name, sub_classes=[]):
        # Refreshing connection to ACI
        result = self.refresh_connection()
        if result['rc'] == 1:
            return {'rc': 1, 'error': result['error']}
        if sub_classes:
            class_filter = ','.join(sub_classes)
            options = '?rsp-subtree=children&rsp-subtree-class={}'.format(class_filter)
        else:
            options = ''
        try:
            uri = "https://{0}/api/class/{1}.json".format(self.apic_address, class_name)
            if options:
                uri += options
            response = self.session.get(uri, headers=self.headers, cookies=self.cookie, verify=False).json()
            if response['imdata']:
                return {'rc': 0, 'data': response['imdata']}
            else:
                return {'rc': 1, 'data': []}
        except Exception as error:
            return {'rc': 1, 'error': [str(error)]}

    def aci_get_mo(self, dn, subtree_class):
        # Refreshing connection to ACI
        result = self.refresh_connection()
        if result['rc'] == 1:
            return {'rc': 1, 'error': result['error']}
        try:
            uri = "https://{0}/api/mo/{1}.json".format(self.apic_address, dn)
            subtree = 'children'
            options = '?rsp-subtree={}&rsp-subtree-class={}'.format(subtree, subtree_class)
            uri += options
            response = self.session.get(uri, headers=self.headers, cookies=self.cookie, verify=False).json()
            if response['imdata']:
                return {'rc': 0, 'data': response['imdata']}
            else:
                return {'rc': 1, 'data': []}
        except Exception as error:
            return {'rc': 1, 'error': [str(error)]}

    def aci_get_fabric_inventory(self):
        try:
            elastic_docs = []
            result = self.aci_get_class('fabricNode')
            if result['rc'] == 0:
                inv_list = result['data']
                for item in inv_list:
                    item_dict = item['fabricNode']['attributes']
                    if item_dict['role'] == 'leaf' or item_dict['role'] == 'spine':
                        inv_dict = {}
                        inv_dict['device'] = item_dict['name']
                        inv_dict['serial'] = item_dict['serial']
                        inv_dict['model'] = item_dict['model']
                        inv_dict['dn'] = item_dict['dn']
                        inv_dict['ip'] = item_dict['address']
                        inv_dict['sw_version'] = item_dict['version']
                        self.fabric_inventory.append(inv_dict)
                        elastic_docs.append({'device': inv_dict['device'],
                                            'site': self.site,
                                            'fabric': self.fabric_name,
                                            'sw_version': inv_dict['sw_version'],
                                            'model': inv_dict['model'],
                                            'serial': inv_dict['serial']})

                if self.fabric_inventory and elastic_docs:
                    return {'rc': 0 , 'data': elastic_docs }
            else:
                return {'rc': 1, 'error': result['error'] }

        except Exception as error:
            return {'rc': 1, 'error': [str(error)]}

    def aci_get_ports_capacity(self):
        if self.fabric_inventory:
            result = self.refresh_connection()
            if result['rc'] == 1:
                return {'rc': 1, 'error': result['error']}
            try:
                elastic_docs = []
                for device in self.fabric_inventory:

                    ports_up = ports_down = ports_disabled = ports_total = 0

                    dn = device['dn']
                    pod = dn.split('/')[1].replace('pod-', '').strip()
                    node = dn.split('/')[2].replace('node-', '').strip()
                    uri = "https://{0}/api/node/class/topology/pod-{1}/node-{2}/l1PhysIf.json?rsp-subtree=children" \
                              "&rsp-subtree-class=ethpmPhysIf".format(self.apic_address, pod, node)

                    response = self.session.get(uri, headers=self.headers, cookies=self.cookie, verify=False)
                    
                    if response.status_code == 200:
 
                        response_data = response.json()

                        if response_data['imdata']:

                            for item in response_data['imdata']:
                                ports_total += 1
                                port_info = item['l1PhysIf']['attributes']
                                adminSt = port_info['adminSt']
                                operSt = ''
                                if 'children' in item['l1PhysIf']:
                                    if 'ethpmPhysIf' in item['l1PhysIf']['children'][0]:
                                        operSt = item['l1PhysIf']['children'][0]['ethpmPhysIf']['attributes']['operSt']
                               
                                if operSt == 'down':
                                    if adminSt == 'down':
                                        ports_disabled += 1
                                    else:
                                        ports_down += 1
                                elif operSt == 'up':
                                    ports_up += 1


                            ports_free = ports_total - ports_up
                            ports_util_percent = 100*ports_up/ports_total

                            elastic_docs.append({'device': device['device'],
                                                 'site': self.site,
                                                 'fabric': self.fabric_name,
                                                 'ports_total': ports_total,
                                                 'ports_free': ports_free,
                                                 'ports_disabled': ports_disabled,
                                                 'ports_down': ports_down,
                                                 'ports_util_percent': round(ports_util_percent, ndigits=1),
                                                 'ports_up': ports_up})
                if elastic_docs:
                    return {'rc': 0, 'data': elastic_docs }

            except Exception as error:
                return {'rc': 1, 'error': [str(error)]}

        

def count_by_pod_node(apic, fabric_name, mo):
    mo_elastic_docs = []
    doc_counts = {}
    count_field = mo + '_count'
    result = apic.aci_get_class(mo)
    docs = result['data']
    # Set hlq-dn for each doc. hlq format is topology/pod/node
    for doc in docs:
        if doc.get(mo):
            dn_hlq = '/'.join(doc[mo]['attributes']['dn'].split('/')[0:3])
            if dn_hlq in doc_counts.keys():
                doc_counts[dn_hlq] += 1
            else:
                doc_counts[dn_hlq] = 1
    for doc_hlq, doc_count in doc_counts.items():
        pod = doc_hlq.split('/')[1]
        node = doc_hlq.split('/')[2]
        mo_elastic_doc = {}
        mo_elastic_doc['mo'] = mo
        mo_elastic_doc['hlq'] = fabric_name + '/' + doc_hlq
        mo_elastic_doc['pod'] = pod
        mo_elastic_doc['node'] = node
        mo_elastic_doc['site'] = apic.site
        mo_elastic_doc['fabric'] = fabric_name
        mo_elastic_doc[count_field] = doc_count
        mo_elastic_docs.append(mo_elastic_doc)
    return mo_elastic_docs

# evobeat calls this function with config_data
def collect_data(config_data):
    # Set Logger
    logger = logging.getLogger(config_data.get('args_name'))
    module = config_data.get('collector_module')
    if 'debug' in config_data:
        debug = True
    else:
        debug = False
    # Instantiate APIC
    apic = Apic(fabrics=config_data['inventory'])
    elastic_docs = []
    for fabric_name in config_data['inventory'].keys():
        login_result = apic.login(fabric_name)
        if login_result['rc'] != 0:
            for error in login_result['error']:
                logger.info(error)
                return []
        # Get filters (vzFilter) and entries (vzEntry)
        vzfilters = {}
        result = apic.aci_get_class('vzFilter', sub_classes=['vzEntry'])
        vzFilters = result['data']
        for vzFilter in vzFilters:
            filter_name = vzFilter['vzFilter']['attributes']['name']
            vzfilters[filter_name] = []
            for child in vzFilter['vzFilter']['children']:
                entry_name = child['vzEntry']['attributes']['name']
                entry_prot = child['vzEntry']['attributes']['prot']
                entry_from_port = child['vzEntry']['attributes']['sFromPort']
                entry_to_port = child['vzEntry']['attributes']['sToPort']
                entry = {'name': entry_name, 'prot': entry_prot, 'from_port': entry_from_port, 'to_port': entry_to_port}
                vzfilters[filter_name].append(entry)
        # Get contracts (vzBrCP) and subjects (vzSubj)
        contracts = {}
        result = apic.aci_get_class('vzBrCP', sub_classes=['vzSubj'])
        vzBrCPs = result['data']
        for vzBrCP in vzBrCPs:
            contract_name = vzBrCP['vzBrCP']['attributes']['name']
            contracts[contract_name] = []
            children = vzBrCP['vzBrCP'].get('children')
            if children:
                for child in children:
                    for vzSubj, attributes in child.items():
                        subject_name = attributes['attributes']['name']
                        contracts[contract_name].append(subject_name)
        # Get subjects (vzSubj) and filter attributes (vzRsSubjFiltAtt)
        subjects = {}
        result = apic.aci_get_class('vzSubj', sub_classes=['vzRsSubjFiltAtt'])
        vzSubjs = result['data']
        for vzSubj in vzSubjs:
            subject_name = vzSubj['vzSubj']['attributes']['name']
            children = vzSubj['vzSubj'].get('children')
            if children:
                for child in children:
                    filter_name = child['vzRsSubjFiltAtt']['attributes']['tRn'].replace('flt-', '')
                    subjects[subject_name] = filter_name
        # Get fvAEPgs and related contracts, provide (fvRsProv) and consume (fvRsCons)
        epgs = []
        result = apic.aci_get_class('fvAEPg', sub_classes=['fvRsProv', 'fvRsCons'])
        fvAEPgs = result['data']
        for fvAEPg in fvAEPgs:
            dn = fvAEPg['fvAEPg']['attributes']['dn']
            hlq = '/'.join(dn.split('/')[0:5])
            tenant_name = dn.split('/')[1].replace('tn-', '')
            app_name = dn.split('/')[2].replace('ap-', '')
            epg_name = dn.split('/')[3].replace('epg-', '')
            children = fvAEPg['fvAEPg'].get('children')
            if children:
                for child in children:
                    for contract_direction, attributes in child.items():
                        contract_name = attributes['attributes']['tRn'].replace('brc-', '')
                        subject_names = contracts.get(contract_name, [])
                        for subject_name in subject_names:
                            filter_name = subjects[subject_name]
                            for filter_entry in vzfilters[filter_name]:
                                doc = {}
                                doc['mo'] = 'fvAEPg'
                                doc['hlq'] = fabric_name + '/' + hlq
                                doc['tenant'] = tenant_name
                                doc['ap'] = app_name
                                doc['epg'] = epg_name
                                doc['site'] = apic.site
                                doc['fabric'] = fabric_name
                                doc['contract'] = contract_name
                                doc['contract_direction'] = contract_direction
                                doc['filter'] = filter_name
                                doc['entry_name'] = filter_entry['name']
                                doc['prot'] = filter_entry['prot']
                                doc['from_port'] = filter_entry['from_port']
                                doc['to_port'] = filter_entry['to_port']
                                elastic_docs.append(doc)
        # Get fvCEp and child fvIp objects
        result = apic.aci_get_class('fvCEp', sub_classes=['fvIp'])
        if result['rc'] != 0:
            for error in result['error']:
                logger.info(error)
                return []
        docs = result['data']
        for doc in docs:
            if doc.get('fvCEp'):
                dn = doc['fvCEp']['attributes']['dn']
                # Filter out non-epg endpoints
                # eg. uni/tn-common/ctx-e-eu1/cep-E8:98:6D:54:E0:12   
                if 'ctx-' not in dn:
                    hlq = '/'.join(dn.split('/')[0:5])
                    tenant = dn.split('/')[1].replace('tn-', '')
                    ap = dn.split('/')[2].replace('ap-', '')
                    epg = dn.split('/')[3].replace('epg-', '')
                    elastic_doc = {}
                    elastic_doc['mo'] = 'fvCEp'
                    elastic_doc['hlq'] = fabric_name + '/' + hlq
                    elastic_doc['tenant'] = tenant
                    elastic_doc['ap'] = ap
                    elastic_doc['epg'] = epg
                    elastic_doc['site'] = apic.site
                    elastic_doc['fabric'] = fabric_name
                    elastic_doc['encap'] = doc['fvCEp']['attributes']['encap']
                    elastic_doc['mac'] = doc['fvCEp']['attributes']['mac']
                    fvIps = doc['fvCEp'].get('children')
                    # May return NONE
                    if fvIps:
                        for fvIp in fvIps:
                            ip = fvIp['fvIp']['attributes'].get('addr')
                            elastic_doc['fvIp'] = ip
                            elastic_docs.append(elastic_doc)
                    else:
                        elastic_doc['fvIp'] = ''
                        elastic_docs.append(elastic_doc)
        # Get rpmEntity objects
        result = apic.aci_get_fabric_inventory()
        if result['rc'] != 0:
            for error in result['error']:
                logger.info(error)
                return []
        else:
            elastic_docs.extend(result['data'])
        # Get port capacity
        result = apic.aci_get_ports_capacity()
        if result['rc'] != 0:
            for error in result['error']:
                logger.info(error)
                return []
        else:
            elastic_docs.extend(result['data'])
        # Get rpmEntity objects
        result = apic.aci_get_class('rpmEntity')
        if result['rc'] != 0:
            for error in result['error']:
                logger.info(error)
                return []
        docs = result['data']
        for doc in docs:
            if doc.get('rpmEntity'):
                dn = doc['rpmEntity']['attributes']['dn']
                hlq = '/'.join(dn.split('/')[0:3])
                pod = dn.split('/')[1]
                node = dn.split('/')[2]
                elastic_doc = {}
                elastic_doc['mo'] = 'rpmEntity'
                elastic_doc['hlq'] = fabric_name + '/' + hlq
                elastic_doc['pod'] = pod
                elastic_doc['node'] = node
                elastic_doc['site'] = apic.site
                elastic_doc['fabric'] = fabric_name
                elastic_doc['shMemAllocFailCount'] = int(doc['rpmEntity']['attributes']['shMemAllocFailCount'])
                elastic_doc['shMemTotal'] = int(doc['rpmEntity']['attributes']['shMemTotal'])
                elastic_doc['shMemUsage'] = int(doc['rpmEntity']['attributes']['shMemUsage'])
                elastic_doc['shMemAlert'] = doc['rpmEntity']['attributes']['shMemAlert']
                elastic_docs.append(elastic_doc)
        # Get rtmapRule objects
        elastic_docs.extend(count_by_pod_node(apic, fabric_name, 'rtmapRule'))
        # Get rtmapEntry objects
        elastic_docs.extend(count_by_pod_node(apic, fabric_name, 'rtmapEntry'))
        # Get rtpfxEntry objects
        elastic_docs.extend(count_by_pod_node(apic, fabric_name, 'rtpfxEntry'))
        # # Get fvRtdEpP objects
        epg_counts = {}
        count_field = 'fvRtdEpP' + '_count'
        result = apic.aci_get_class('fvRtdEpP')
        ext_epgs = result['data']
        for ext_epg in ext_epgs:
            ext_epg_dn = ext_epg['fvRtdEpP']['attributes']['dn']
            l3out_dn = '/'.join(ext_epg_dn.split('[')[1].split('/')[:-1])
            result = apic.aci_get_mo(l3out_dn, 'l3extLNodeP')
            l3outs_with_children = result['data']
            for l3out_with_children in l3outs_with_children:
                if 'children' in l3out_with_children['l3extOut']:
                    node_profs = l3out_with_children['l3extOut']['children']
                    for node_prof in node_profs:
                        node_prof_rn = node_prof['l3extLNodeP']['attributes']['rn']
                        node_prof_dn = l3out_dn + '/' + node_prof_rn
                        result = apic.aci_get_mo(node_prof_dn, 'l3extRsNodeL3OutAtt')
                        node_profs_with_children = result['data']
                        for node_prof_with_children in node_profs_with_children:
                            l3outattrs = node_prof_with_children['l3extLNodeP']['children']
                            for l3outattr in l3outattrs:
                                hlq = l3outattr['l3extRsNodeL3OutAtt']['attributes']['tDn']
                                if hlq in epg_counts.keys():
                                    epg_counts[hlq] += 1
                                else:
                                    epg_counts[hlq] = 1
        for epg_hlq, epg_count in epg_counts.items():
            pod = epg_hlq.split('/')[1]
            node = epg_hlq.split('/')[2]
            elastic_doc = {}
            elastic_doc['mo'] = 'fvRtdEpP'
            elastic_doc['hlq'] = fabric_name + '/' + epg_hlq
            elastic_doc['pod'] = pod
            elastic_doc['node'] = node
            elastic_doc['site'] = apic.site
            elastic_doc['fabric'] = fabric_name
            elastic_doc[count_field] = epg_count
            elastic_docs.append(elastic_doc)
        # Get actrlPfxEntry objects
        elastic_docs.extend(count_by_pod_node(apic, fabric_name, 'actrlPfxEntry'))
        # Get actrlRule objects
        elastic_docs.extend(count_by_pod_node(apic, fabric_name, 'actrlRule'))
        # Get l3extInstP objects
        epg_counts = {}
        count_field = 'l3extInstP' + '_count'
        result = apic.aci_get_class('l3extInstP')
        ext_epgs = result['data']
    for ext_epg in ext_epgs:
        ext_epg_dn = ext_epg['l3extInstP']['attributes']['dn']
        l3out_dn = '/'.join(ext_epg_dn.split('/')[:-1])
        result = apic.aci_get_mo(l3out_dn, 'l3extLNodeP')
        l3outs_with_children = result['data']
        for l3out_with_children in l3outs_with_children:
            if 'children' in l3out_with_children['l3extOut']:
                node_profs = l3out_with_children['l3extOut']['children']
                for node_prof in node_profs:
                    node_prof_rn = node_prof['l3extLNodeP']['attributes']['rn']
                    node_prof_dn = l3out_dn + '/' + node_prof_rn
                    result = apic.aci_get_mo(node_prof_dn, 'l3extRsNodeL3OutAtt')
                    node_profs_with_children = result['data']
                    for node_prof_with_children in node_profs_with_children:
                        l3outattrs = node_prof_with_children['l3extLNodeP']['children']
                        for l3outattr in l3outattrs:
                            hlq = l3outattr['l3extRsNodeL3OutAtt']['attributes']['tDn']
                            if hlq in epg_counts.keys():
                                epg_counts[hlq] += 1
                            else:
                                epg_counts[hlq] = 1
        for epg_hlq, epg_count in epg_counts.items():
            pod = epg_hlq.split('/')[1]
            node = epg_hlq.split('/')[2]
            elastic_doc = {}
            elastic_doc['mo'] = 'l3extInstP'
            elastic_doc['hlq'] = fabric_name + '/' + epg_hlq
            elastic_doc['pod'] = pod
            elastic_doc['node'] = node
            elastic_doc['site'] = apic.site
            elastic_doc['fabric'] = fabric_name
            elastic_doc[count_field] = epg_count
            elastic_docs.append(elastic_doc)
        if debug:
            pprint(elastic_docs)
        apic.disconnect()
    # Add 'environment' and 'region_name' fields
    for elastic_doc in elastic_docs:
        elastic_doc['environment'] = config_data['environment']
        elastic_doc['region_name'] = config_data['region_name']
    return elastic_docs

if __name__ == "__main__":
    config_data = {'elastic_host': 'elastic.default.192.168.10.115.nip.io',
                   'elastic_index': 'aci-evobeat',
                   'elastic_username': 'evolvere',
                   'elastic_password': 'evolvere',
                   'interval': 30,
                   'inventory': {'UKGRNFAB1':
                                  [{
                                    'address': '192.168.104.10',
                                    'username': 'admin',
                                    'password': 'f00tba11',
                                    'site': 1}]},
                   'collector_module': 'aci_collector',
                   'log_file': 'stdout',
                   'environment': 'engineering',
                   'region_name': 'e-eu1'}
    docs = collect_data(config_data)
    pprint(docs)

