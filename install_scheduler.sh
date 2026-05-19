#!/bin/bash
# Install LaunchAgents so NSE data fetches run automatically:
#   - 7 PM weekdays: full EOD fetch (includes delivery screener)
#   - 9 AM weekdays: quick morning fetch (FII/DII, indices, gainers)
#
# Run once: bash install_scheduler.sh

LAUNCH_DIR="$HOME/Library/LaunchAgents"
SCHEDULER_DIR="$(cd "$(dirname "$0")/scheduler" && pwd)"

mkdir -p "$LAUNCH_DIR"

for plist in com.nse.eod.fetch.plist com.nse.morning.fetch.plist; do
    src="$SCHEDULER_DIR/$plist"
    dst="$LAUNCH_DIR/$plist"
    cp "$src" "$dst"
    launchctl unload "$dst" 2>/dev/null
    launchctl load "$dst"
    echo "✅ Installed: $plist"
done

echo ""
echo "Scheduled jobs installed:"
echo "  • 7:00 PM daily  → EOD fetch (VIX, sectors, FII/DII, deals, delivery screener)"
echo "  • 9:00 AM daily  → Morning fetch (FII/DII, indices, gainers/losers)"
echo ""
echo "To uninstall: launchctl unload ~/Library/LaunchAgents/com.nse.eod.fetch.plist"
echo "              launchctl unload ~/Library/LaunchAgents/com.nse.morning.fetch.plist"
