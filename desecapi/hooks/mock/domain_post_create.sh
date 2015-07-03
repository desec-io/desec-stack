#!/bin/bash
echo Mockup hook for: $0 "$@"

# Send 1M zero bytes to stdout
# (large output of this script caused problems earlier)
dd if=/dev/zero bs=1M count=1 2>/dev/null