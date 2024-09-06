## Adding custom DNS Mappings 

BridgeCTL now supports adding custom domain mappings to the /etc/hosts file inside the bridge container so that the bridge agent can properly resolve a DNS entry to IP address. To use this feature,
simply populate the dns_mappings dictionary by editing the yaml file found at `bridgectl/config/bridge_settings.yml`.

Example:
```
dns_mappings:
  mysql.example.lan: 10.1.1.18
  postgresql.example.lan: 10.1.1.80
```

This is the same as using the [--add_hosts](https://www.cloudbees.com/blog/using-the-add-host-flag-for-dns-mapping-within-docker-containers) parameter of a docker run command. When the container is started, these values will be added to the /etc/hosts file within the container.

(This feature was released on Sept 5, 2024)
