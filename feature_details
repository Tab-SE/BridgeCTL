
## Adding custom DNS Mappings 

BridgeCTL now supports adding custom domain mappings to the /etc/hosts file inside the bridge container so that the bridge agent can properly resolve a DNS entry to IP address. To use this feature,
simply populate the dns_mappings dictionary in config/bridge_settings.yml.

Example:

dns_mappings:
  mysql.example.lan: 10.1.1.18
  postgresql.example.lan: 10.1.1.80

This is the same as using the --add_hosts parameter of a docker run command. When the container is started, these values will be added to the /etc/hosts file within the container.

(This feature was released on Sept 5, 2024)
