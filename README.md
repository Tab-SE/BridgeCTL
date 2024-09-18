
# Tableau BridgeCTL
BridgeCTL is a local command-line utility for Tableau Bridge. It solves many of the pain points faced by Bridge administrators.

[![Community Supported](https://img.shields.io/badge/Support%20Level-Community%20Supported-457387.svg)](https://www.tableau.com/support-levels-it-and-developer-tools)
[![GitHub](https://img.shields.io/badge/license-MIT-brightgreen.svg)](https://raw.githubusercontent.com/Tableau/TabPy/master/LICENSE)

### Introduction
BridgeCTL will help you build your Tableau Bridge Linux container images including downloading and 
installing the right database drivers and bridge rpm installer. Then it will help you easily configure and 
run your bridge containers in Docker or Kubernetes with the correct connection settings. It has a convenient 
log viewer for bridge container logs in docker, kubernetes. It will also monitor the status and configuration of your 
running bridge agents and can send you an alert if one of your agents becomes disconnected. 
BridgeCTL can be installed on Linux, Windows or Mac.

### Setup
BridgeCTL is easy to install. Just download and run the bridgectl_setup.py script using the following two commands:

```
curl -OL https://github.com/tab-se/bridgectl/releases/download/setup/bridgectl_setup.py
python bridgectl_setup.py
```

### Requirements
- Python >= 3.10
- Docker Desktop
- BridgeCTL works on Windows, Linux or Mac

Note python 3.10 or greater is required. Please use the appropriate python command on your machine to run the setup script, for example instead of "python" you may need to use "python3" or "python3.11". 
The BridgeCTL setup script will create a folder "bridgectl" in the current directory and a python virtual environment named "tabenv". It will then create a shortcut function `bridgectl` so that you can conveniently use that global command from the terminal.

Detailed setup instructions for [Linux](https://github.com/Tab-SE/BridgeCTL/blob/main/docs/setup_on_linux.md)

### Quickstart Demo
![Home](assets/bridgectl_quickstart2.gif)


### Features
- Build Tableau Bridge docker container images
  - Download and install the bridge rpm and selected database drivers in the image.
  - Follow best practices for building containers.
- Run bridge containers in Docker
- Reports
  - Display Jobs Report
  - Display Bridge Agent Status
- Analyze bridge logs
  - Log viewer with ability to filter and sort logs
  - Analyze logs from local docker containers, local disk or from kubernetes containers (pods)
- Run bridge containers in Kubernetes
  - After importing your kubeconfig file, you can spin up bridge agent containers in a Kubernetes cluster
- Manage bridge containers in Docker or Kubernetes
  - View configuration settings of bridge containers or delete bridge containers
  - View current bridge agent activity (standard output logs)
  - Show snapshot metrics about resource utilization

### Terms of Use
This repo contains utilities and source code example files for creating and running Tableau bridge Linux containers. These scripts may be useful but are unsupported. Please get help from other users on the Tableau Community Forums.

### Documentation for Tableau Bridge
See [official Tableau documentation](https://help.tableau.com/current/online/en-us/to_bridge_linux_install.htm) for creating bridge containers on Linux


### Release Notes
[Release Notes](RELEASE_NOTES.md)

<br><br><br>
### User interface screenshots
Home

![Home](assets/home4.png)

Command-line Interface

![CLI](assets/cli2.png)__

Build Bridge Container Images
![Build](assets/build.png)

Analyze Logs
![BridgeCTL Logs](assets/logs.png)

Monitor Bridge Agent Health
![Monitor Bridge](assets/monitor_screenshot2.png)

Autoscale Bridge Pods in Kubernetes
![Monitor Bridge](assets/autoscale.png)

Example Dockerfile Scripts
![Example Scripts](assets/examples3.png)
