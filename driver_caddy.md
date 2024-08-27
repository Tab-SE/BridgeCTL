

## Driver Caddy 
Driver Caddy makes it easy to install and test database drivers by defining a standard YAML Driver installation definition file that can be used to generate specific scripts for various target operating systems and container or virtual machine runtimes. 


Here is an example YAML file:

```
---
- driver: postgresql
  os: rhel8, rhel9,amazonlinux2023
  download_url: https://<download_site>/postgresql-42.3.4.jar
  type: jar

- driver: mysql
  os: rhel9,amazonlinux2023
  download_url: https://<download_site>/mysql80-community-release-el8-9.noarch.rpm
  type: rpm
  install: |
    yum -y localinstall /tmp/driver_caddy/$download_name
    yum -y install mysql-connector-odbc-8.0.33-1.el8
  test: |
    grep -n -F '[MySQL ODBC 8.0 ANSI Driver]' /etc/odbcinst.ini
    grep -n -F '[MySQL ODBC 8.0 Unicode Driver]' /etc/odbcinst.ini
    [ -f /usr/lib64/libmyodbc8a.so ]
    [ -f /usr/lib64/libmyodbc8w.so ]
```
