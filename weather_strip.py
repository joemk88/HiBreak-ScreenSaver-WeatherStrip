#!/usr/bin/env python3
"""
weather_strip.py
Stamps a monochrome weather band onto the top 1/5 of the Bigme screensaver
cover (/sdcard/Cover.jpg) and writes it back atomically.

Location-aware: uses termux-location (network provider) to follow you, with a
cached last-known fix and a hardcoded Sydney fallback, so scheduled runs
with the screen off still produce a sensible band. Place name is reverse-
geocoded (keyless) and cached so a stationary phone skips that call.

Data: Open-Meteo (no API key). Icons: solid black silhouettes (crisp on e-ink).
On any weather-fetch error the cover is left untouched.
"""

import os
import sys
import json
import math
import subprocess
import time
import base64
import io
from functools import lru_cache
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont

# ---- config -----------------------------------------------------------------
# Location comes from Tasker (LAT/LON via env or argv). If absent, we pin to
# these defaults -- no termux-location, no Termux:API.
DEFAULT_LAT, DEFAULT_LON, DEFAULT_LABEL = -33.869, 151.209, "Sydney"
UA = os.environ.get("UA", "bigme-weather-strip/1.0 (github.com/joemk88)")

COVER = os.environ.get("COVER", "/sdcard/cover.jpg")   # MUST match coverprogress + com.xrz.standby (lowercase)
COVER2 = os.environ.get("COVER2", "/data/data/com.termux/files/home/.weather/cover2.jpg")   # weather-stamped intermediate copy
TIMEOUT = 15                # http timeout (s)


# FONT (env): a /system/fonts filename ("Roboto-Bold.ttf") or a full path.
# Blank -> Droid Sans Mono. See the README for common Bigme fonts.
def _resolve_font(choice):
    choice = (choice or "").strip()
    if not choice:
        return None
    if "/" in choice:
        return choice
    if not choice.lower().endswith((".ttf", ".otf")):
        choice += ".ttf"
    return "/system/fonts/" + choice

_FONT_CHOICE = _resolve_font(os.environ.get("FONT"))
FONT_CANDIDATES = ([_FONT_CHOICE] if _FONT_CHOICE else []) + [
    "/system/fonts/DroidSansMono.ttf",
    "/system/fonts/RobotoMono-Regular.ttf",
    "/system/fonts/DroidSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# ICONS (env): "colour"/"color" -> Glyphs Poly colour icons; else mono (Carbon).
ICON_STYLE = "colour" if os.environ.get("ICONS", "").strip().lower() in ("colour", "color") else "mono"


# ---- location (from Tasker GPS; else pinned default) ------------------------
def get_location():
    """(lat, lon, label). Tasker passes LAT/LON via env or as argv[1] argv[2].
    PLACE (env) optionally overrides the label; otherwise the default is used."""
    lat = os.environ.get("LAT")
    lon = os.environ.get("LON")
    if (not lat or not lon) and len(sys.argv) >= 3:
        lat, lon = sys.argv[1], sys.argv[2]
    if lat and lon:
        try:
            return float(lat), float(lon), os.environ.get("PLACE")
        except ValueError:
            print("bad LAT/LON supplied, using default", file=sys.stderr)
    return DEFAULT_LAT, DEFAULT_LON, os.environ.get("PLACE") or DEFAULT_LABEL


# ---- weather (Open-Meteo; free, keyless) ------------------------------------
def get_weather(lat, lon):
    """Return (metrics_dict, place_name=None). DEMO skips the network.
    Rain is precipitation PROBABILITY (%) for the current hour."""
    if os.environ.get("DEMO"):
        return {"temp": 21, "feels": 22, "rain": 10, "clouds": 0, "humidity": 39}, None
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,apparent_temperature,cloud_cover,relative_humidity_2m"
           "&hourly=precipitation_probability&forecast_days=1&timezone=auto")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.load(r)
    c = data["current"]
    # pick the precipitation probability for the current hour
    rain = 0
    try:
        hours = data["hourly"]["time"]
        probs = data["hourly"]["precipitation_probability"]
        now = c["time"][:13]                      # 'YYYY-MM-DDTHH'
        idx = next((i for i, t in enumerate(hours) if t[:13] == now), 0)
        rain = probs[idx] if probs[idx] is not None else 0
    except Exception:
        pass
    return {
        "temp":     c["temperature_2m"],
        "feels":    c["apparent_temperature"],
        "rain":     rain,
        "clouds":   c["cloud_cover"],
        "humidity": c["relative_humidity_2m"],
    }, None


def date_label(t=None):
    t = t or time.localtime()
    wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][t.tm_wday]
    mo = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec"][t.tm_mon - 1]
    return f"{wd}, {mo} {t.tm_mday}"


# ---- metric icons (Carbon iconset, Apache-2.0; rasterised + base64-embedded) -
# Clean glyphs pasted and tinted at runtime, so no SVG deps on the Termux side.
ICON_B64 = {
    "temp": (
        "iVBORw0KGgoAAAANSUhEUgAAAOEAAADhCAYAAAA+s9J6AAANOElEQVR4nO3deYxeVRnH8e+8nbK2tEJLQbYWSgtUgYpL0WICJKhU"
        "NlM3VKJFURE1BFwSE2I0NSBBqQY1qCBLWAxCJIBKAI0roFAsYjdoQQJWS2VpO1VoZ/zjzMRxBJl5n+ec5y6/T3L+m3vnOec9z3vv"
        "e+455/ZQf3sD84HDgYOAGcA0YDKw/eDf/At4BlgHrAVWAA8AvwaeKBirSCP0AEcBS4BVwICxrAS+Drxp8Nwi8hJ2BT4HrMGeeC9V"
        "HgY+Q7qKisigVwDnAxvJl3wjy3PAVwb/t0hrjQM+AWygXPKNLE8BZwKdzHUVqZyDgXuIS76R5XfA7Kw1FqmQDwGbiU+8kWUTcFrG"
        "eouE6wUuIT7ZXq4sId0qizTKjsDNxCfYaMtN/OcZpEjt7QDcTnxijbX8FCWiNEAv9boCjiw3oltTqblvEZ9I1nKxd6OIlHI68Qnk"
        "VT7g3DYi2R0C9BGfPF5lEzDLtYVEMhoH3Et84niX36KZNVITZxGfMLnKxx3bSVqi9NKdXUkrFXJMjH4GuA24k7RWcC3w9LD/Ox2Y"
        "CxwLHA9MyhDDBmDmYCxtMRAdQM0VXz53Af5XnxWkqW47jCGOHYFF+KxHHFkWjyGOJoi++6h7KWpXfJcjbQbOJj1r7NZ44Bx8B4me"
        "pV3rEaM7cd1LUZ91DHwVaYTVyxxgtWN85zjGVnXRnbjupZge4BGnoO8DpmSIcSpwv1OMK2nPVhnRnbjupZj5TgGvIk8CDpmK3xVx"
        "XsY4qyS6E9e9FHuutdDhHH3AyaTV7rmsB04Btjicy6POIm48RiHPLhjvuQ7xLi8Yb6ToK0ndSxH7OgS6Atso6FiNx+eLY8+CMUeJ"
        "7sR1L0VuR490OMf5wFaH84zWC4P/08qj7tJwJZJwrvH4Z4HrPQIZo2tJWx9aWOsuLVAiCa27lN2Cz0DJWG0BbjWe42CPQKTZSiTh"
        "DOPxd7lE0Z2fG4+f7hGENFuJJNzDePwDHkF0aanxeGvdpQVKJOEk4/FrXaLozqPG4yc7xCANV2JqVb/x/4wbPEeEXtJIabf6af5G"
        "UMWedTVUT4kktH5I0XMw6x6/VJy2YxAJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQU"
        "CaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAmmJBQJ1hsdgNRe"
        "018Smv39kroSigRTEooEUxKKBFMSigRTEooEUxKKBFMSigRTEooEUxKKBFMSigRTEooEUxKKBFMSigRTEooEUxKKBNN6QrHKvt6u"
        "6XQlFAmmJBQJpiQUCaYkFAmmJBQJpiQUCaYkFAlWh+eETd/XUlpOV0KRYEpCkWBKQpFgSkKRYEpCkWBKQpFgSkKRYEpCkWBKQpFg"
        "SkKRYEpCkWBKQpFgSkKRYEpCkWBKQpFgdVhPGL2vpdYzSla6EooEUxKKBFMSigRTEooEUxKKBFMSigRTEooEq8NzQqk2PUe16dGV"
        "UCSYklAkmJJQJJiSUCSYklAkmJJQJJiSUCSYklAkmJJQJFjOJNwB+EbG89fFxaS2ECnqQOAB0pQma4nmUYf7gZmlAy/Eo33aXLJY"
        "ADxT9SDHwKseTwNvKxx7CdGduO7F3dnAtqoHOUaeddkKfKps+NlFd+K6FzcdYEnVg+xSjjpdRPwucl6iO3Hdi4te4KqqB2mQq16X"
        "A+MK1iOX6E5c92LWC1xX9SCNctbtapqRiBKkQ94rYBuScIB0RWzKrakUlus3YNuScID0G1FkTM4lf8dcB5xRqkL/xxmkWHLX99Ol"
        "KiT1dxL+jyGGlz5gMTCxVIVGYSIppj7y1XsrzXyOKM4OAp4lTyfsB64B9ilWm7HbB7iWfIn4NM2dWSMOdgKWkafzrQGOLVcVs+OA"
        "teRpi6Vorqm8hO+Qp9NdBkwoWA8vE4ErydMmmvgu/2MB/h2tDzitZCUyWQRswbdt+klXWxEAJgFP4NvJngReV7ISmc3DfwT1Mao1"
        "OCWBvo1v51oJTC9ZgUL2B1aj21JxdgS+jyMeBHYvWoOy9gSW49deW4G5RWsgldID/Aa/DrUCmFa0BjH2xPeK+Iui0UulLMSvIz0J"
        "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"
    ),
    "feels": (
        "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"
        "eX0olFbr4jVKq7R/EvG7gGWxI/q6CP4EdfriB7EFlIg+fe3voPa0Qvv3B6bGFlEyJiJ79n4Cf4I61Tg/toAScl5RPxT7Hazsv6+l"
        "A1iIzbvVWuCXwNHA8CIbEZgRwGeRg33XYeOreRT0wIwdoGX/fS2HYBNwrwETCtYeg/2QRdsWPjuwd+XexXV6Y7GGcSayo8J0g7pS"
        "52WkrbMM6trE956gTm8OUJZfh8yQWWSgJRfeR5aTrVfW409Qp1/2UJa/j3I8OXvzEnC/so5NfO8J6vRGu/r/bhMVeXKvsvwmvm/F"
        "76Bl/30t69Dt9jgCOR27jIxGTutultXAFj3/wRO09X5f+9uabSPXE3kxcgJ00vw17KJXr9a7uE5PtDcX32dZd4PdpKwnqOMkjCeo"
        "4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo"
        "4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo"
        "4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIwnqOMkjCeo4ySMJ6jjJIx1gnrC63EfOhuxDIY24D8N6ysrNyG+dBxTrgK6DExL7r/fBUwx"
        "0NEssf2XO0n67+sGwlJJkNi/X7GvGmhphtj+y53k/HcssN5AWCoJEvv3K7YOONpAT6PE9l/uJOW/8cAHBqJSSpDYv9/TFgPjDDQ1"
        "Qmz/5U4y/hsETDMQlFqCxP793vY8MNBAV1H6y04y/rvBQExvW2+gK7aDLLv7FfuJga56ie2/3EnCf8cAnQZietpHwMkG2mI76GSk"
        "LZa+2QAcZaCtHjYYa88twWO2fZ1FA4YB7xgLWwIcaSHOQIsFf4e0ydJHc4ChRvpqYT2m4Alavy20aIB11/ZdYIKFsG5SCZB9gbkG"
        "enraNYb6+uIFY82eoPXbs1rxB2D7jjUH+1HKlAJkPPC2gaaKrcP2ZlaN2wz1xvZ/M8Rs+01a8X8wFPNXYKxWUBVSC5BdkF6Cld+e"
        "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"
    ),
    "rain": (
        "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"
    ),
    "clouds": (
        "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"
    ),
    "humidity": (
        "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"
        "Th7mbDgAAAAASUVORK5CYII="
    ),
}


# Glyphs Poly (by Goran Spasojevic) — full-colour weather icons, used when ICONS=colour
ICON_COLOUR_B64 = {
    "temp": (
        "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"
        "rkJggg=="
    ),
    "feels": (
        "iVBORw0KGgoAAAANSUhEUgAAALMAAACzCAYAAADCFC3zAAAbpklEQVR4nO2de3wU5bnHf+/M7G6ym2STwCYhEBLuAYFwUfCGYqvn"
        "6FGqiHDwwk0Bq0awPW1Pr7paz2l76mn70Wo9oFVPi6cVEa9oW6mAoKICCReBEHIlyW5um2TvuzPznj/QFimX7OzMvDPJfD8f/iLz"
        "PL+Z/e2777yX5yWwUMy999YXRWC7Ns5zlyV5blyc54YnebgThDiTPLFRUC7BER4A7DKVCIhsk+WkTaYRu0R6HJLcapPkGockf5Dh"
        "dG95+rHsdtb3ZGYIawFmYvk9rXPiNrIiZOMv77GT0qCDs1OVYhMK5CTkuDshN2Un6Q4XyG/XP174gUrhBwWWmc8BBSXLK1vv7BP4"
        "u7ucQkWvndj1zJ8TlxNDY1JVTkx6+oXfDH9Oz9xmxDLzGVh1b9NF3Tb7z/wu4fKgndhY6wGA7DhNFkXEHdki/53nnvTsZa3HiFhm"
        "PoUV97fe3e4QftTi4oZTYsxHQyjFsLB8whMVH/7fJ4ufYa3HSBjzE9OZpZW+ta1O3tvh5HJZa0mFgggNFIbkB3//VMGvWWsxAoPa"
        "zEvv88/3ObHe7xKGsNaSDkURqaM4Jq967vGi11hrYcmgNPPqta0j23n+zYZsYQodIE+AUIqykFQ1Kpy44ZdPl7Sw1sOCAfJR9p8l"
        "lb5Ha92270Zs4Flr0QJXkkqjg9Kjv3+80Mtai94MGjOvXOsv9NvI+01Z/DjWWvSgNCgdGZKQrnjuiWEdrLXoBcdagB4sq2xdUOPi"
        "mwaLkQGgMZsvP54lNN9Z6fsaay16MeDNfPv9/scO5tlf1nvCwwj0OjjH/nzbq7euafsZay16MKC7Gbc84PtTrdv2TwPlJU8phAJj"
        "e8W3X/5V4b+w1qIlA/JjnuulQk6fv6oxx3YBay1GYlSfWD3tFwUzvCAyay1aMODM7PVS+6fBjsPN2fxo1lqMSElIOhbK8kza5iUi"
        "ay1qM6DMPNdLhaxgx1HLyOemJCQdy2z0TNy4kUistajJgHoBdPe177OMfH6as/hxiRHtA26x0oAx8y3f8L3bkCNMZq3DLDS4hakL"
        "Hmh7h7UONRkQZr5jjf8XtTm2r7LWYTaOu+3/fOt9bY+x1qEWpu8zL7+nbeGBobaXRN70t8IEQaKY1CMt+N0Tha+w1pIupnZAZWVT"
        "cVW2syHoMMYCerOSk6CJiZFQ2bpflbWx1pIOpu5mNDgy3reMnD59dmJvETJ3sdaRLqY185L7235tjVyox4ksYdRta9p+w1pHOpiy"
        "m7Hi/o4rD+Ry7yV5c+o3KjYZdGpn/NrfPlX8Z9ZalGA6MyxfTjOaCjvbuzK5bNZaBiJDYnKkvI8WPvVUQYi1llQxXTejL8//nmVk"
        "7ejK4JxtDvoX1jqUYCozL7vft6Yux3Yxax0DnXq3cPGSyrbvsNaRKqbpZtx1b/vYw3nckbCNDMjtTkYjU6TyuO7E5N89VXyYtZb+"
        "YoqWmYKSFifet4ysH1GBcB1ZwnYvqCk8ApjEzIvX+v7YlsUXsdYx2Ghz8p7P1vr+wFpHfzG8mVes8d14zG1fyFrHYKXWbVt4V2Wb"
        "KZ6/ofvMyx+oz23IdLUFHHwGay2DGXdcjpd3JUesW1fcyVrLuTB0yxzgMndZRmZPr4Nz+LL5bax1nA/DmnnZfb4fN2bbJrHWYXGS"
        "xmzhgsVr2n7OWse5MGQ3Y9ma1pmHc2yfxAXOkPoGKw6R0qm94qXPPFH0EWstZ8JwLfNcLxXaMmx/sYxsPOICIQ1O/h2vlxqyBonh"
        "zOzp8b/td3J5rHVYnJmOTM59sMf/JmsdZ8JQZl56X9uyWrdwNWsdFuem1i1cs6zSv5q1jtMxzE95ZWVTcXW2s6HPWmxvClxJKpbF"
        "EmNf/O/iRtZavsAwLXO9w7HLMrJ5CNuIECDCTtY6TsUQZr51jW/9iWyhjLUOi9RozeJH3LrWt461ji9g3s1Yem/HVZ8N4bZau0bM"
        "iSBRTOlKXPf8U8XMa3AwNdBqb6uzNmbzd2VwWSx1WKSHUXanMO1mdPRw2ywjm5+uDM7Z6pC3stbBzMwr7m37Vn2u7SJW+S3UpSHH"
        "Nuv2Nb4fsNTApJuxurKzfL8bh6I2YogXUAt1yBAhT2yPTHt+XckBFvl1N5MXlGvOpO9ZRh54xARwbbmOrax2p+ie9LM1/pdbXZy1"
        "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"
        "AABJRU5ErkJggg=="
    ),
    "rain": (
        "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"
        "AElFTkSuQmCC"
    ),
    "clouds": (
        "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"
    ),
    "humidity": (
        "iVBORw0KGgoAAAANSUhEUgAAALMAAACzCAYAAADCFC3zAAAUEElEQVR4nO2de5gcVZmH31Pdc00yydxCLpALSUgyZG5MgGVVBEUN"
        "KwIKia54YXlURBdUFC+QSyVIVGSDGxaUlQf3UVc0iCviA6vrJaBrloeETCb3BBJCCITMdM8wEyYz01119o+JGsNMZrr69DlV3ef9"
        "N6nv+1Wd33x1+tS5CCxKaXG7a9KkLgfeDMwFMXHwX+QRYJdA/qGvuPixXbdWJAzKzEuEaQH5wjnukdkezgoQS4DiEf77gISHJLFV"
        "W90J+3ToKwSsmbNGisaVnV9E+itBlGR4cR9w2xa36m4QMhfqCglr5iw425XFcZLfB96fXST5w0qq/2m9K9JKhBUojmkB0UWKGInv"
        "kbWRAcSHkiQfyD5OYWPNHJCGlcmbBOKDquIJ+GiTm/yUqniFiO1mBKDBTZwuYDdQrjj0UQd/7ma39mXFcQsCW5kD4CBvRb2RAcb6"
        "xG7NQdyCwFbmDGle3VPrDwwcAMpylKI3TtH0TW5FR47i5y22MmeIHBj4NLkzMkB5mpTtOwfAVuYMuGDNwbLe7vIXgIk5TnXkNbqn"
        "v+DO7MtxnrzCVuYM6O0Z8xFyb2SAiRNExYc15MkrrJlHiysdpPxcxtcF/K4nJTeDtG/ODLBmHiUNdFwGzM34wuB2nNewsvOywFcX"
        "INbMo0TgfEF7Uul/XnvOCGNfY6Og2W1f6OM8EziAJPCTlo78u7blNU8Hzl1A2Mo8CnycW7IKkEXJEL74bFa5CwhbmUegye2cIfH3"
        "AnFDEjyf2Fl23vPI2Mo8AhL/c5gzMkBM4N1oMH9ksJX5FNR/ravS6fdeBMZmem0W3eSh6BE401rdyi51IfMPW5lPgRhIf5IARgbl"
        "VWKcFPJ6tSHzD1uZh6HlflmUfiW5DzjdtJbjvJymauZ2VwyYFhJWbGUeBu+VxDWEx8gAU2IkPmBaRJixZh4GSfiGxATiC/YT9/BY"
        "Mw9Bg5tYBDSa1jEE9Y1u8h2mRYQVa+ahCfNn5DBrM4p9ZZ1E/apkvePLLYT42Qic5la3stW0jrBhK/NJOD63EGIjA/j4nzWtIYyE"
        "utF00/jVjqmkxT5G3l7LNCkvzqxtS6sPmhYSJmxlPgGZFp8h/EYGKIql5adNiwgbtjIfp+XryfHpPvkiUGFayyjp6ivzp+3+Um2P"
        "aSFhwVbm46T7uIHoGBlgQukx5+OmRYQJW5mBGe7+0vFU7AcmZXShytlEwWK9lKZqlv3EPYitzMB4xl9LpkYGtaUgWKzTYyQ/olBF"
        "pCl4M7fcL4tAfsm0jqAIxJcWr5Mx0zrCQMGb+fiEohmmdQRHzt67s9NOQKLAzbx4nYxJROQ3KvSlvA1XFnRbQoGbefeOxDXAHNM6"
        "skXA/AbRqWDT82hTsGa+yJVxgbPMtA5lSLms0PvOBWvmTpIfATnbtA5VCJi/Z2dC2U7+UaQgx5mPH6yzm0j/8HsjAvl8bHL1/E3X"
        "i5RpLSYoyMocJ/EJ8szIABIxK3248zrTOkxRcJW54ZuHx4jXi54jyEeSaHCovKJ3zoabzzhmWohuCq4yi96im8lfIwNM7e0e8xnT"
        "IkxQUJX5+Hkke4HxprXkmK7+4qLZhXY+d0FVZn8gtYz8NzLAhOKB1FLTInRTMJW50W0/C5xtQJFpLZoY8GKxum3LJjxvWoguCqYy"
        "S2J3UjhGBiiOed6dpkXopCAqc8PKjrcLKX5jWocJBP7FrW7tetM6dJD3lfkiV8aFFHeb1mEKifOtQvnMnfdm7hKJ64F60zoM0rhn"
        "R2dBLK/K627GvNXd1SUDqT1AlWkthulIE5+73R2fNC0kl+R1ZS4ZSK3GGhmgpojUV02LyDV5W5kb3Y7zQGwgz/9gM8DzHf/8rctr"
        "N5kWkivysqEXr5MxgXMfeXp/AYk5vnNfPq9Iycsb27MjcYNEtpjWEULOaxCdeXucRN51M5rd9ik+zk6itaGLTrriRX7dpttqXzEt"
        "RDV5V5l9nLVYI5+KCV7KWWtaRC7Iq8rctLLjCinFz03riAJCyCtbV9Q8alqHSvLGzMc3PtwOTDWtJSIcipeKszd9ueo100JUkTfd"
        "jHSf/3WskTNhqtfnf820CJXkRWVudJNvBvkkefTHqQkfxFu3uFV/NC1EBZFv/NlrZQnI75IH92IAB+R3B59h9Im8AcYkk0uBeaZ1"
        "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"
        "us9VLTDoAAAAAElFTkSuQmCC"
    ),
}


@lru_cache(maxsize=None)
def _icon_rgba(key, colour):
    table = ICON_COLOUR_B64 if colour else ICON_B64
    return Image.open(io.BytesIO(base64.b64decode(table[key]))).convert("RGBA")


def paste_icon(img, key, cx, cy, size, ink="black"):
    """Mono (Carbon): tinted to ink. Colour (Glyphs Poly): pasted as-is."""
    colour = ICON_STYLE == "colour"
    ic = _icon_rgba(key, colour).resize((size, size), Image.LANCZOS)
    box = (int(cx - size / 2), int(cy - size / 2))
    if colour:
        img.paste(ic, box, ic)                      # keep original colours
    else:
        fill = (255 if img.mode == "L" else (255, 255, 255)) if ink == "white" \
            else (0 if img.mode == "L" else (0, 0, 0))
        img.paste(Image.new(img.mode, (size, size), fill), box, ic.split()[3])


def decide_dark(img, sample_frac=0.22, dark_level=110, dark_ratio=0.5):
    """True if the cover's top is predominantly dark -> use a dark band.
    Mirrors coverprogress: fraction of dark pixels, not mean luminance."""
    env = os.environ.get("DARK")
    if env == "1":
        return True
    if env == "0":
        return False
    h = max(1, min(img.height, int(img.height * sample_frac)))
    g = img.crop((0, 0, img.width, h)).convert("L")
    g.thumbnail((120, 120))
    data = g.tobytes()            # 1 byte/pixel for mode "L"
    return (sum(1 for p in data if p < dark_level) / len(data)) > dark_ratio


# order matches the mockup, left to right; 2nd field is the Carbon icon key
METRICS = [
    ("Temp.",      "temp",     lambda w: (f"{round(w['temp'])}\u00b0", "")),
    ("Feels like", "feels",    lambda w: (f"{round(w['feels'])}\u00b0", "")),
    ("Rain",       "rain",     lambda w: (f"{round(w['rain'])}", "%")),
    ("Clouds",     "clouds",   lambda w: (f"{round(w['clouds'])}", "%")),
    ("Humidity",   "humidity", lambda w: (f"{round(w['humidity'])}", "%")),
]


# ---- font -------------------------------------------------------------------
def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def fit_font(draw, text, max_w, start_size):
    size = start_size
    while size > 8:
        f = load_font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return load_font(8)


# ---- main -------------------------------------------------------------------
def draw_dashboard(img, weather, place, date_str, ink="black"):
    W, H = img.size
    d = ImageDraw.Draw(img)

    # Sizes relative to WIDTH (stable across panels); band height derived from
    # content so it stays short and won't intrude on taller covers.
    side  = int(W * 0.065)
    hfs   = int(W * 0.030)
    ih    = int(W * 0.050)
    lfs   = int(W * 0.024)
    vfs   = int(W * 0.045)
    g_top = int(W * 0.016) + 25   # +5 earlier, +20 more -> strip sits lower
    g_hi  = int(W * 0.010)
    g_il  = int(W * 0.005)
    g_lv  = int(W * 0.003)
    g_bot = int(W * 0.012)

    y = g_top
    header_cy = y + hfs / 2
    y += hfs + g_hi
    icon_cy = y + ih / 2
    y += ih + g_il
    label_cy = y + lfs / 2
    y += lfs + g_lv
    value_base = y + int(vfs * 0.80)
    band_h = value_base + g_bot

    # Dark-mode: reverse to light-on-dark when the cover's top is dark, mirroring
    # coverprogress's dark-pixel-fraction approach. DARK=1/0 overrides auto.
    dark = decide_dark(img)
    ink = "white" if dark else "black"
    band_bg = (0, 0, 0) if dark and img.mode == "RGB" else (0 if dark else "white")
    d.rectangle([0, 0, W, band_h], fill=band_bg)

    hdr = f"{place}   {date_str}"
    hdr_f = fit_font(d, hdr, W - 2 * side, hfs)
    d.text((W / 2, header_cy), hdr, font=hdr_f, fill=ink, anchor="mm")

    n = len(METRICS)
    col_w = (W - 2 * side) / n
    for i, (name, icon_key, fmt) in enumerate(METRICS):
        cx = side + col_w * (i + 0.5)
        paste_icon(img, icon_key, cx, icon_cy, ih, ink=ink)

        lab_f = fit_font(d, name, col_w * 0.96, lfs)
        d.text((cx, label_cy), name, font=lab_f, fill=ink, anchor="mm")

        big, unit = fmt(weather)
        big_f = fit_font(d, big + unit, col_w * 0.96, vfs)
        unit_f = load_font(max(8, int(big_f.size * 0.5)))
        wb = d.textlength(big, font=big_f)
        wu = d.textlength(unit, font=unit_f) if unit else 0
        start = cx - (wb + wu) / 2
        d.text((start, value_base), big, font=big_f, fill=ink, anchor="ls")
        if unit:
            d.text((start + wb, value_base), unit, font=unit_f, fill=ink, anchor="ls")


def main():
    lat, lon, place = get_location()
    try:
        weather, _ = get_weather(lat, lon)
        place = place or DEFAULT_LABEL
    except (urllib.error.URLError, KeyError, IndexError, TypeError, ValueError, TimeoutError) as e:
        print(f"weather fetch failed, leaving cover untouched: {e}", file=sys.stderr)
        sys.exit(1)

    # Preserve the cover's colour (some e-ink panels are colour). Only normalise
    # exotic/alpha modes so we can draw and save as JPEG.
    img = Image.open(COVER)
    if ICON_STYLE == "colour" and img.mode != "RGB":
        img = img.convert("RGB")          # colour icons need an RGB canvas
    elif img.mode not in ("L", "RGB"):
        img = img.convert("RGB")

    draw_dashboard(img, weather, place, date_label(), ink="black")

    # First write the weather-stamped image to cover2.jpg. This leaves the
    # original cover.jpg untouched while the new image is being generated.
    d_dir = os.path.dirname(COVER2) or "."
    base = os.path.basename(COVER2)
    tmp = os.path.join(d_dir, "." + base + ".tmp")
    img.save(tmp, "JPEG", quality=92)
    os.replace(tmp, COVER2)

    # Now copy the completed cover2.jpg over the watched cover.jpg. Keeping
    # cover2.jpg as a complete, separate file avoids the screensaver seeing a
    # partially-written cover and gives the folder watcher a clean cover.jpg
    # replacement to notice.
    subprocess.run(["cp", COVER2, COVER], check=True)

    print(f"stamped: {place} {date_label()}  temp={weather['temp']} feels={weather['feels']} "
          f"rain={weather['rain']} clouds={weather['clouds']} rh={weather['humidity']} "
          f"cover2={COVER2} -> cover={COVER}")


if __name__ == "__main__":
    main()
