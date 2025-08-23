#!/bin/bash
set -o errexit; set -o nounset

echo "{\"$TOKEN_NAME\":\"$TOKEN_VALUE\"}" > tokenFile.json
export TOKEN_VALUE=""
set -o xtrace

if [ -n "${UNC_PATH_MAPPINGS:-}" ]; then
  current_dir=$(pwd)
  echo "$UNC_PATH_MAPPINGS" > "$current_dir/tableau_bridge_unc_map.txt"
  export TABLEAU_BRIDGE_UNC_MAP_OVERRIDE="$current_dir/tableau_bridge_unc_map.txt"
  echo -e "tableau_bridge_unc_map.txt: $UNC_PATH_MAPPINGS"
fi

/opt/tableau/tableau_bridge/bin/TabBridgeClientCmd setServiceConnection --service="$TC_SERVER_URL"
/opt/tableau/tableau_bridge/bin/run-bridge.sh -e \
   --client="${AGENT_NAME}" \
   --site="${SITE_NAME}" \
   --userEmail="${USER_EMAIL}" \
   --patTokenId="${TOKEN_NAME}" \
   --patTokenFile=tokenFile.json \
   --poolId="${POOL_ID}"
