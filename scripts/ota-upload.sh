#!/usr/bin/env bash
# Upload a firmware image to the device's /update endpoint.
#   ota-upload.sh <firmware.bin> [host]      (host defaults to "smalltv")
# Set OTA_PASS in the environment if the image on the device was built with one.
# On WSL, uses Windows' curl.exe: WSL2 often can't resolve LAN hostnames.
set -euo pipefail
bin="$1"
host="${2:-smalltv}"
auth=()
[ -n "${OTA_PASS:-}" ] && auth=(--anyauth -u "admin:${OTA_PASS}")

curl_cmd=(curl)
if grep -qi microsoft /proc/version 2>/dev/null && [ -x /mnt/c/Windows/System32/curl.exe ]; then
  curl_cmd=(/mnt/c/Windows/System32/curl.exe)
  bin="$(wslpath -w "$bin")"
fi

echo "Uploading $bin to http://$host/update"
# -H "Expect:": curl otherwise sends "Expect: 100-continue" for a large body,
# and the ESP8266 web server stalls on it until the request times out.
# Uploads are slow (a ~430 KB image takes ~2 min), hence the long max-time.
resp="$("${curl_cmd[@]}" -sS --fail-with-body --max-time 600 -H "Expect:" "${auth[@]}" \
  -F "firmware=@${bin};type=application/octet-stream" "http://$host/update")"
echo "$resp"
case "$resp" in
  *OK*|*Success*|*success*) echo "Upload done; the device is rebooting." ;;
  *) echo "Upload may have failed." >&2; exit 1 ;;
esac
