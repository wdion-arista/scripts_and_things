# Copyright (c) 2024 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the COPYING file.
#
# Script source: https://github.com/aristanetworks/cloudvision-python/tree/trunk/examples/resources/tag/v2
#
#

import argparse
import sys,os
import grpc
import json
import arista.tag.v2
from google.protobuf.json_format import Parse
import yaml
from google.protobuf.json_format import MessageToDict
import csv
import pprint

RPC_TIMEOUT = 30  # in seconds

def to_int_if_possible(value):
    """
    Attempts to convert a value to an integer. If it fails,
    it returns the original value.
    """
    # Only try to convert if the value is a string
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            # Conversion failed, return the original string
            return value
    # If not a string, return it as is
    return value

def nest_hyphenated_keys(flat_dict, keys_to_convert):
    """
    Converts a dictionary with hyphenated keys into a nested dictionary.
    
    It only converts values to integers if the final key is in the 
    'keys_to_convert' set.
    """
    nested_dict = {}
    for key, value in flat_dict.items():
        if '-' in key:
            # Split the key into parts
            outer_key, inner_key = key.split('-', 1)
            
            sub_dict = nested_dict.setdefault(outer_key, {})
            
            # Conditionally convert based on the INNER key
            sub_dict[inner_key] = (
                to_int_if_possible(value) if inner_key in keys_to_convert else value
            )
        else:
            # Conditionally convert based on the main key
            nested_dict[key] = (
                to_int_if_possible(value) if key in keys_to_convert else value
            )
            
    return nested_dict


def organize_switch_data(tsv_data):
    organized_ports = {}
    for port_config in tsv_data:
        pod_dict = organized_ports.setdefault(port_config['Access-Pod'], {})
        switch_dict = pod_dict.setdefault(port_config['switch'], {
            'deviceId': port_config['deviceId'],
            'interfaces': []
        })
        interface_details = {
            'interface': port_config['interface'],
            'vlan': port_config['vlan'],
            'description': port_config['description'],
            'profile': port_config['profile']
        }
        switch_dict['interfaces'].append(interface_details)
    return organized_ports



#### Switch configs
#

def find_item_by_tag(data, target_query):
    """
    Recursively searches a nested dictionary/list structure to find an item
    with a specific 'query' tag.

    Args:
        data: The dictionary or list to search within.
        target_query (str): The 'query' value to find (e.g., 'Campus:Customer_rack1').

    Returns:
        The first dictionary that contains the matching tag, or None if not found.
    """
    # If the current item is a dictionary, check for the tag
    if isinstance(data, dict):
        # Check if this dictionary itself is the one we're looking for
        tags = data.get('tags', {})
        if isinstance(tags, dict) and tags.get('query') == target_query:
            return data  # Match found, return the entire dictionary

        # If not, recurse into its values
        for value in data.values():
            result = find_item_by_tag(value, target_query)
            if result:
                return result

    # If the current item is a list, recurse into its elements
    elif isinstance(data, list):
        for item in data:
            result = find_item_by_tag(item, target_query)
            if result:
                return result

    # If no match is found in the current branch, return None
    return None

def load_yaml_to_dict(filename):
    """
    Loads a YAML file and converts it into a Python dictionary.

    Args:
        filename (str): The path to the YAML file.

    Returns:
        dict: A dictionary representing the YAML file's content.
    """
    try:
        with open(filename, 'r') as file:
            # Use safe_load to parse the YAML file
            data = yaml.safe_load(file)
            return data
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None
    
def find_deviceid_concise(data_list, name_to_find):
    """A one-line version using a generator expression."""
    return next((item.get('deviceId') for item in data_list if item.get('name') == name_to_find), None)


def tsv_to_list_of_dicts(filename):
    """
    Loads a TSV file and converts it into a list of dictionaries.

    Args:
        filename (str): The path to the TSV file.

    Returns:
        list: A list of dictionaries, where each dictionary represents a row.
    """
    data = []
    try:
        with open(filename, mode='r', encoding='utf-8') as tsv_file:
            # Use DictReader, specifying the tab delimiter
            reader = csv.DictReader(tsv_file, delimiter='\t')
            
            data = [
                {key: (None if value == '' else value) for key, value in row.items()}
                for row in reader
            ]
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
    
    return data


def main(args):
    # Read the file containing a session token to authenticate with
    
    if args.token:
        cv_token = args.token
    elif args.token_file:
        cv_token = args.token_file.read().strip()
    else:
        exit('Please supply a token in text(--token) or file (--token-file)')

    # Create the header object for the token
    callCreds = grpc.access_token_call_credentials(cv_token)

    # If using a self-signed certificate (should be provided as arg)
    if args.cert_file:
        # Create the channel using the self-signed cert
        cert = args.cert_file.read()
        channelCreds = grpc.ssl_channel_credentials(root_certificates=cert)
    else:
        # Otherwise default to checking against CAs
        channelCreds = grpc.ssl_channel_credentials()

    connCreds = grpc.composite_channel_credentials(channelCreds, callCreds)

    # Construct the json_request based on provided arguments
    request_dict = {}
    if any([args.device_id, args.interface_id, args.tag_label, args.tag_value]):
        if args.tag_type:
            filter_dict = {"elementType": int(args.tag_type), "workspaceId": ""}
        else:
            filter_dict = {"elementType": 1, "workspaceId": ""}
        if args.tag_label:
            filter_dict["label"] = args.tag_label
        if args.tag_value:
            filter_dict["value"] = args.tag_value
        if args.device_id:
            filter_dict["deviceId"] = args.device_id
        if args.interface_id:
            filter_dict["interfaceId"] = args.interface_id
            filter_dict["elementType"] = 2

        request_dict["partialEqFilter"] = [{"key": filter_dict}]

    json_request = json.dumps(request_dict)

    req = Parse(json_request, arista.tag.v2.services.TagAssignmentStreamRequest(), False)

    # Initialize a connection to the server using our connection settings (auth + TLS)
    # with grpc.secure_channel(args.server, connCreds) as channel:
    #     tag_stub = arista.tag.v2.services.TagAssignmentServiceStub(channel)
    #     # print(list(tag_stub.GetAll(req, timeout=RPC_TIMEOUT)))

    with grpc.secure_channel(args.server, connCreds) as channel:
        tag_stub = arista.tag.v2.services.TagAssignmentServiceStub(channel)

        # 1. Get the response from the server
        response_iterator = tag_stub.GetAll(req, timeout=RPC_TIMEOUT)

        # 2. Convert the Protobuf objects to a list of dictionaries
        # This makes the data serializable for YAML
        results_list = [MessageToDict(item) for item in response_iterator]
    devices = []
    for device in results_list:
        dev = device['value']['key']
        if dev['elementType'] == 'ELEMENT_TYPE_DEVICE' and dev['label'] == 'hostname':
            # print(dev['value'], dev['deviceId'])
            devices.append({'name':dev['value'], 'deviceId': dev['deviceId']})

    sorted_devices = sorted(devices, key=lambda item: item['name'])
    inv_directory, inv_filename = os.path.split(f'{args.file_interface_studio_inputs}')
    output_filename = f'{inv_directory}/studio_device_tags.yaml'
    with open(output_filename, 'w') as yaml_file:
        yaml.dump(sorted_devices, yaml_file, indent=2)

    # Load list of ports to configure
    switch_port_data = tsv_to_list_of_dicts(args.file_interface_tsv)
    # Load current studios inputs YAML
    studio_input=load_yaml_to_dict(args.file_interface_studio_inputs)

    print(f'Finding Devcies: ------------------------')
    port_array_log={'print':[],'error':[]}
    for switchport in switch_port_data:
        print(switchport['switch'],switchport['interface'])
        deviceid = find_deviceid_concise(sorted_devices, switchport['switch'])
        interface_number = switchport['interface']
        found_campus_interface = find_item_by_tag(studio_input, f'interface:Ethernet{interface_number}@{deviceid}')
        
        if found_campus_interface is not None:
            # Update the Port
            keys_to_make_int = {'nativeVlan', 'phoneVlan', 'portChannelId'}
            switchport_nested_data = nest_hyphenated_keys(switchport,keys_to_make_int)
            
            if 'spineAdapterDetails' in found_campus_interface['inputs']:
                found_campus_interface['inputs']['spineAdapterDetails'] = found_campus_interface['inputs']['spineAdapterDetails'] | switchport_nested_data
                intf_update = found_campus_interface['inputs']['spineAdapterDetails']
            else:
                found_campus_interface['inputs']['adapterDetails'] = found_campus_interface['inputs']['adapterDetails'] | switchport_nested_data
                intf_update = found_campus_interface['inputs']['adapterDetails']

            
            intf_update.pop('switch', None)
            intf_update.pop('interface', None)
            intf_update['enabled'] = 'No' if switchport.get('enabled') is None else switchport['enabled']
        else:
            print("Add a dummy port so the port gets recognized in studios")

    with open(args.file_interface_studio_output, 'w') as yaml_file:
        yaml.dump(studio_input, yaml_file, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--server", required=True, help="CloudVision server to connect to in <host>:<port> format"
    )
    parser.add_argument(
        "--token-file", type=argparse.FileType("r"), help="file with access token"
    )
    parser.add_argument(
        "--token", help="access token text")    
    parser.add_argument(
        "--cert-file", type=argparse.FileType("rb"), help="certificate to use as root CA"
    )

    # New arguments
    parser.add_argument("--device-id", help="Device ID for the filter")
    parser.add_argument("--interface-id", help="Interface ID for the filter")
    parser.add_argument("--tag-label", help="Tag name (label) for the filter")
    parser.add_argument("--tag-value", help="Tag value for the filter")

    parser.add_argument("--file-interface-tsv", default='configs/studio-campus-ports.tsv', help="interface mapping for ports")
    parser.add_argument("--file-interface-studio-inputs", default='configs/studio-campus-access-interfaces-inputs.yaml', help="YAML file retrieved from Studios")
    parser.add_argument("--file-interface-studio-output", default='configs/studio-campus-access-interfaces-inputs-new.yaml', help="File to output to")
    
    parser.add_argument(
        "--tag-type",
        help="type of tag to filter on, 1 for device, 2 for interface",
        choices=["1", "2"],
    )
    args = parser.parse_args()
    
    if not os.path.exists(args.file_interface_tsv):
        sys.exit(f"Error: Missing {args.file_interface_tsv} file. Please create one.")
    if not os.path.exists(args.file_interface_studio_inputs):
        sys.exit(f"Error: Missing {args.file_interface_studio_inputs} file. Please create one.")

    main(args)