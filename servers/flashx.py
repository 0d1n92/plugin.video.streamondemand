# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# streamondemand - XBMC Plugin
# Conector para flashx by cmos
# http://blog.tvalacarta.info/plugin-xbmc/pelisalacarta/
# ------------------------------------------------------------

import base64
import os
import re
import time
import urllib

from core import config
from core import jsunpack
from core import logger
from core import scrapertools


def test_video_exists(page_url):
    logger.info("streamondemand.servers.flashx test_video_exists(page_url='%s')" % page_url)

    data = scrapertools.downloadpageWithoutCookies(page_url.replace("playvid-", ""))

    if 'File Not Found' in data:
        return False, "[FlashX] Nessun file"
    elif 'Video is processing now' in data:
        return False, "[FlashX] File processato"

    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    logger.info("streamondemand.servers.flashx url=" + page_url)

    # Lo pide una vez
    data = scrapertools.downloadpageWithoutCookies(page_url)
    # Si salta aviso, se carga la pagina de comprobacion y luego la inicial
    if "You try to access this video with Kodi" in data:
        url_reload = scrapertools.find_single_match(data, 'try to reload the page.*?href="([^"]+)"')
        url_reload = "http://www.flashx.tv" + url_reload[1:]
        try:
            data = scrapertools.downloadpageWithoutCookies(url_reload)
            data = scrapertools.downloadpageWithoutCookies(page_url)
        except:
            pass

    matches = scrapertools.find_multiple_matches(data, "<script type='text/javascript'>(.*?)</script>")
    m = ""
    for n, m in enumerate(matches):
        if m.startswith("eval"):
            try:
                m = jsunpack.unpack(m)
                fake = (scrapertools.find_single_match(m, "(\w{40,})") == "")
                if fake:
                    m = ""
                else:
                    break
            except:
                m = ""
    match = m
    if "sources:[{file:" not in match:
        page_url = page_url.replace("playvid-", "")

        headers = {'Host': 'www.flashx.tv', 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.137 Safari/537.36',
                  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5',
                  'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1',
                  'Cookie': ''}
        data = scrapertools.downloadpage(page_url, headers=headers.items())
        flashx_id = scrapertools.find_single_match(data, 'name="id" value="([^"]+)"')
        fname = scrapertools.find_single_match(data, 'name="fname" value="([^"]+)"')
        hash_f = scrapertools.find_single_match(data, 'name="hash" value="([^"]+)"')
        post = 'op=download1&usr_login=&id=%s&fname=%s&referer=&hash=%s&imhuman=Proceed+to+video' % (flashx_id, urllib.quote(fname), hash_f)
        wait_time = scrapertools.find_single_match(data, "<span id='xxc2'>(\d+)")

        file_id = scrapertools.find_single_match(data, "'file_id', '([^']+)'")
        coding_url = 'https://files.fx.fastcontentdelivery.com/jquery2.js?fx=%s' % base64.encodestring(file_id)
        headers['Host'] = "files.fx.fastcontentdelivery.com"
        headers['Referer'] = "https://www.flashx.tv/"
        headers['Accept'] = "*/*"
        coding = scrapertools.downloadpage(coding_url, headers=headers.items())

        coding_url = 'https://www.flashx.tv/counter.cgi?fx=%s' % base64.encodestring(file_id)
        headers['Host'] = "www.flashx.tv"
        coding = scrapertools.downloadpage(coding_url, headers=headers.items())

        coding_url = 'https://www.flashx.tv/flashx.php?fxfx=3'
        headers['X-Requested-With'] = 'XMLHttpRequest'
        coding = scrapertools.downloadpage(coding_url, headers=headers.items())

        try:
           time.sleep(int(wait_time)+1)
        except:
           time.sleep(6)

        headers.pop('X-Requested-With')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = scrapertools.downloadpage('https://www.flashx.tv/dl?playthis', post=post, headers=headers.items())

        matches = scrapertools.find_multiple_matches(data, "(eval\(function\(p,a,c,k.*?)\s+</script>")
        for match in matches:
            if match.startswith("eval"):
                try:
                    match = jsunpack.unpack(match)
                    fake = (scrapertools.find_single_match(match, "(\w{40,})") == "")
                    if fake:
                        match = ""
                    else:
                        break
                except:
                    match = ""

        if not match:
            match = data

    # Extrae la URL
    # {file:"http://f11-play.flashx.tv/luq4gfc7gxixexzw6v4lhz4xqslgqmqku7gxjf4bk43u4qvwzsadrjsozxoa/video1.mp4"}
    video_urls = []
    media_urls = scrapertools.find_multiple_matches(match, '\{file\:"([^"]+)",label:"([^"]+)"')
    subtitle = ""
    for media_url, label in media_urls:
        if media_url.endswith(".srt") and label == "Italian":
            try:
                from core import filetools
                data = scrapertools.downloadpage(media_url)
                subtitle = os.path.join(config.get_data_path(), 'sub_flashx.srt')
                filetools.write(subtitle, data)
            except:
                import traceback
                logger.info("streamondemand.servers.flashx Error al descargar el subtítulo: "+traceback.format_exc())

    for media_url, label in media_urls:
        if not media_url.endswith("png") and not media_url.endswith(".srt"):
            video_urls.append(["." + media_url.rsplit('.', 1)[1] + " [flashx]", media_url, 0, subtitle])

    for video_url in video_urls:
        logger.info("streamondemand.servers.flashx %s - %s" % (video_url[0], video_url[1]))

    return video_urls


# Encuentra vídeos del servidor en el texto pasado
def find_videos(data):
    # Añade manualmente algunos erróneos para evitarlos
    encontrados = set()
    devuelve = []

    # http://flashx.tv/z3nnqbspjyne
    # http://www.flashx.tv/embed-li5ydvxhg514.html
    patronvideos = 'flashx.(?:tv|pw|to)/(?:embed.php\?c=|embed-|playvid-|)([A-z0-9]+)'
    logger.info("streamondemand.servers.flashx find_videos #" + patronvideos + "#")
    matches = re.compile(patronvideos, re.DOTALL).findall(data)

    for match in matches:
        titulo = "[flashx]"
        url = "https://www.flashx.tv/playvid-%s.html" % match
        if url not in encontrados:
            logger.info("  url=" + url)
            devuelve.append([titulo, url, 'flashx'])
            encontrados.add(url)
        else:
            logger.info("  url duplicada=" + url)

    return devuelve

