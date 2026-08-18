#!/data/data/com.termux/files/usr/bin/sh
# Called by Tasker (Termux:Tasker). Arguments, in order:
#   $1 latitude   $2 longitude   $3 cover image path
#   $4 font       (optional; e.g. Roboto-Bold — blank = Droid Sans Mono)
#   $5 icons      (optional; "colour" for Glyphs Poly — blank = mono)
PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
export PATH="$PREFIX/bin:$PATH"
cd "$HOME" || exit 1

echo "----- $(date '+%Y-%m-%d %H:%M:%S') args:[$*] -----" >> "$HOME/weather.log"

export COVER="$3"
export FONT="$4"
export ICONS="$5"

"$PREFIX/bin/python" "$HOME/weather_strip.py" "$1" "$2" >> "$HOME/weather.log" 2>&1
