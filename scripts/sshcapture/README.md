# sshcapture

### Description
The easy way to capture remotely via ssh. This script builds a tunnel over ssh and captures it to a file. you cna then use wireshark locally to read the capture. you will need to refresh the wireshark stream to get new capture data.

## Caution! 🔴
**This will capture anything you are filtering so make sure you have enough bandwidth to handle the capture.**

### Installation

``` bash
wget sudo wget https://raw.githubusercontent.com/wdion-arista/scripts_and_things/refs/heads/main/scripts/sshcapture/sshcapture -O /usr/bin/sshcapture -O /usr/bin/sshcapture \
&& sudo chmod +x /usr/bin/sshcapture
```
``` bash
❯ sshcapture
No options were passed
Usage: {OPTIONS}  
OPTIONS
-d = device name / user@ip_address (Works better with keys copied first)
-i = device ethernet port to capure form (Default: any)
-p = ports 'port 5090 or port 5092' or 'portrange 5060-5091' (Default: all)
-s = use sngrep to view sip captures(needs sngrep isntalled)

Example:

sshcapture -d username@10.1.1.100 -i eth1 -p 'port 5060'
```
### Basic Example capture
- This will create in a folder called captures a file named captures/10.1.1.100_2025_05_30_10_02_AM.pcap  ({hostname}_{timestamp})
- -d user@hostname
- -i ethernet port
- -p port to capture
``` bash
# Copies key to remote host (only needed once)
ssh-copy-id username@10.1.1.100 
# This will create a file in a folder called captures with
sshcapture -d username@10.1.1.100 -i eth1 -p "port 5060"
```

### Arista switch capture
- on arista set a user with bash access via rsa key
- configure your capture ports in this example port 50
  ``` eos
  conf t
  ! 
  username pcapper shell /bin/bash secret sha512 $6$hNPJ7EFOvXXXXXXXXXXXXXXXXXXX
  !
  username pcapper ssh-key ssh-ed25519 AAAAC3NzaC1lZDXXXXXXXXXXXXXXXXXX user.man@computer.local
  !
  monitor session pcap source ethernet 50 both
  monitor session pcap destination cpu
  !
  ```
- Show mirror session
  ``` eos
  show monitor session
  sw100-arista(config)#sh monitor session
  
  Session pcap
  ------------------------
  
  Sources:
  
  Both Interfaces:        Et50
  
  Destination Ports:
  
      Cpu :  active (mirror0:)

  ```
- On local linux machine
  ``` bash
  sshcapture -d capper@10.1.1.10 mirror0
  ```
### Wireshark
- you will need to run wireshark from the host system
- from a new window
  ``` bash
  wireshark captures/10.1.1.100_2025_05_30_10_02_AM.pcap
  ```
- Refresh wireshark to update the stream


## Authors and acknowledgment

- Creator: Westley Dion
