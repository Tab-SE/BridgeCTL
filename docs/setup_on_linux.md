# Setup BridgeCTL on Redhat Linux
BridgeCTL can be setup on Windows, Linux or Mac. You'll need to have Python >= 3.10 and Docker Desktop installed.
Follow these steps specific steps for Redhat9 Linux.


## Install Python
```
dnf install python3.11 -y
dnf install python3.11-pip -y
```

## Install Docker
```
dnf install -y docker
```

## Install BridgeCTL
```
curl -OL https://github.com/tab-se/bridgectl/releases/download/setup/bridgectl_setup.py
python3.11 bridgectl_setup.py
```

## Edit web UI server address
1) In a new terminal, enter the following command to start the BridgeCTL command-line:
```
bridgectl
```

2) From the bridgectl main menu, select "Edit App Settings" and then "Edit web UI server address"
Replace "localhost" with the machine hostname and press save. This will allow you to access the BridgeCTL web UI running on Redhat9 from another machine.

## Start the Web UI
From the main menu, select "Start Web UI". This will start the web UI.

## Access the Web UI
1) Open a browser on another machine and enter the following URL:
http://<redhat9_hostname>:8505

2) Follow the quickstart guide to build and run Tableau Bridge containers.

