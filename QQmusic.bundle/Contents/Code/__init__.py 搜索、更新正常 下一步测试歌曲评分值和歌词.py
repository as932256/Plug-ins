# coding=utf-8
# Rewrite (use JSON API, other matching tweaks) by ToMM

import time
import os
import json

ARTIST_SEARCH_URL_WANGYI = 'http://music.163.com/api/search/get/web?csrf_token=hlpretag=&hlposttag=&s='
ARTIST_ALBUM_SEARCH_URL_WANGYI = 'http://music.163.com/api/artist/albums/'
ALBUM_INFO_URL_WANGYI = 'http://music.163.com/api/album/'
SERACH_TYPE = '&type=100'

ARTIST_URL_WANGYI = 'http://music.163.com/api/v1/artist/'
# Last.fm API
API_KEY = 'd5310352469c2631e5976d0f4a599773'
BASE_URL = 'http://lastfm-z.plexapp.com/2.0/'  # HTTPS doesn't work

ARTIST_SEARCH_URL = BASE_URL + '?method=artist.search&artist=%s&page=%d&limit=%d&format=json&api_key=' + API_KEY
ARTIST_ALBUM_SEARCH_URL = BASE_URL + '?method=artist.gettopalbums&artist=%s&page=%s&limit=%s&format=json&api_key=' + API_KEY
ARTIST_INFO_URL = BASE_URL + '?method=artist.getInfo&artist=%s&autocorrect=1&lang=%s&format=json&api_key=' + API_KEY
ARTIST_TOP_TRACKS_URL = BASE_URL + "?method=artist.getTopTracks&artist=%s&lang=%s&page=%d&limit=100&format=json&api_key=" + API_KEY
ARTIST_SIMILAR_ARTISTS_URL = BASE_URL + "?method=artist.getSimilar&artist=%s&lang=%s&format=json&limit=20&api_key=" + API_KEY

ALBUM_SEARCH_URL = BASE_URL + '?method=album.search&album=%s&limit=%s&format=json&api_key=' + API_KEY
ALBUM_INFO_URL = BASE_URL + '?method=album.getInfo&artist=%s&album=%s&autocorrect=1&lang=%s&format=json&api_key=' + API_KEY

# Concert information from SongKick
SONGKICK_BASE_URL = "http://127.0.0.1:32400/services/songkick?uri=%s"
SONGKICK_ARTIST_EVENTS_URL_MBID = "/artists/mbid:%s/calendar.json"
SONGKICK_ARTIST_EVENTS_URL_SONGKICKID = "/artists/%s/calendar.json"
SONGKICK_ARTIST_SEARCH_URL = "/search/artists.json?query=%s"

# MusicBrainz mbid lookup
MB_ARTIST_URL = 'https://musicbrainz.plex.tv/ws/2/artist/%s'
MB_NS = {'a': 'http://musicbrainz.org/ns/mmd-2.0#'}
MB_HEADERS = {'User-Agent':'Plex Music Agent/1.0 (http://plex.tv)'}

ARTWORK_SIZE_RANKING = { 'mega':0 , 'extralarge':1 , 'large':2 } # Don't even try to add 'medium' or 'small' artwork.
VARIOUS_ARTISTS_POSTER = 'https://music.plex.tv/pixogs/various_artists_poster.jpg'

# Tunables.
ARTIST_MATCH_LIMIT = 9 # Max number of artists to fetch for matching purposes.
ARTIST_MATCH_MIN_SCORE = 75 # Minimum score required to add to custom search results.
ARTIST_MANUAL_MATCH_LIMIT = 120 # Number of artists to fetch when trying harder for manual searches.  Multiple API hits.
ARTIST_SEARCH_PAGE_SIZE = 30 # Number of artists in a search result page.  Asking for more has no effect.
ARTIST_ALBUMS_MATCH_LIMIT = 3 # Max number of artist matches to try for album bonus.  Each one incurs an additional API request.
ARTIST_ALBUMS_LIMIT = 50 # Number of albums by artist to grab for artist matching bonus and quick album match.
ARTIST_MIN_LISTENER_THRESHOLD = 250 # Minimum number of listeners for an artist to be considered credible.
ARTIST_MATCH_GOOD_SCORE = 90 # Include artists with this score or higher regardless of listener count.
ALBUM_MATCH_LIMIT = 8 # Max number of results returned from standalone album searches with no artist info (e.g. Various Artists).
ALBUM_MATCH_MIN_SCORE = 75 # Minimum score required to add to custom search results.
ALBUM_MATCH_GOOD_SCORE = 92 # Minimum score required to rely on only Albums by Artist and not search.
ALBUM_TRACK_BONUS_MATCH_LIMIT = 5 # Max number of albums to try for track bonus.  Each one incurs at most one API request per album.
QUERY_SLEEP_TIME = 0.1 # How long to sleep before firing off each API request.

# Advanced tunables.
NAME_DISTANCE_THRESHOLD = 2 # How close do album/track names need to be to match for bonuses?
ARTIST_INITIAL_SCORE = 90 # Starting point for artists before bonus/deductions.
ARTIST_ALBUM_BONUS_INCREMENT = 3 # How much to boost the bonus for a each good artist/album match.
ARTIST_ALBUM_MAX_BONUS = 15 # Maximum number of bonus points to give artists with good album matches.
ARTIST_MAX_DIST_PENALTY = 40 # Maxiumum amount to penalize for Lev ratio difference in artist names.
ALBUM_INITIAL_SCORE = 92 # Starting point for albums before bonus/deductions.
ALBUM_NAME_DIST_COEFFICIENT = 5 # Multiply album Lev. distance to give it a bit more weight.
ALBUM_TRACK_BONUS_INCREMENT = 3 # How much to boost the bonus for a each good album/track match.
ALBUM_TRACK_MAX_BONUS = 20 # Maximum number of bonus points to give to albums with good track name matches.
ALBUM_TRACK_BONUS_MAX_ARTIST_DSIT = 2 # How similar do the parent artist and album search result artist need to be to ask for info?
ALBUM_NUM_TRACKS_BONUS = 1 # How much to boost the bonus if the total number of tracks match.

RE_STRIP_PARENS = Regex('\([^)]*\)')


def Start():
  HTTP.CacheTime = CACHE_1WEEK

@expose
def ArtistMbidLookup(lastfm_artist):
  artist_mbid = None
  if lastfm_artist and 'mbid' in lastfm_artist and len(lastfm_artist['mbid']) == 36:  # Sanity check.
    artist_mbid = lastfm_artist['mbid']

    # See if there's an updated MBID.
    try: artist_mbid = XML.ElementFromURL(MB_ARTIST_URL % artist_mbid, headers=MB_HEADERS).xpath('//a:artist/@id', namespaces=MB_NS)[0]
    except: pass

  if artist_mbid is not None:
    Log('Found MBID: %s' % artist_mbid)
  else:
    Log('Couldn\'t find MBID.')

  return artist_mbid

@expose
def GetMusicBrainzId(artist, album=None):
  if album:
    dict = GetAlbum(String.Quote(artist), String.Quote(album))
  else:
    dict = GetArtist(String.Quote(artist))

  if 'mbid' in dict:
    return dict['mbid']
  return None


@expose
def ArtistSearch(artist, albums=[], lang='en'):
  if artist == '[Unknown Artist]' or artist == 'Various Artists' or artist == 'OST':
    return
  artist_results = []
  artists = SearchArtists(artist, ARTIST_MATCH_LIMIT)
  
  # Extra shot if there's an & in there.
  if '&' in artist:
    artists += SearchArtists(artist.replace('&', 'and'), ARTIST_MATCH_LIMIT)
  
  score_artists(artists, artist, albums, lang, artist_results)
  if len(artist_results) > 0 and artist_results[0].score >= 85:
    return GetArtist(artist_results[0].id)

@expose
def AlbumSearch(artist, album, year, lang):
  id = String.Quote(artist.decode('utf-8').encode('utf-8')).replace(' ','+')
  
  # Try by top albums.
  albums = GetAlbumsByArtist(id, albums=[])
  for a in albums:
    if LevenshteinRatio(a['name'], album) > 0.95:
      album_id = String.Quote(a['name'].decode('utf-8').encode('utf-8')).replace(' ','+')
      return GetAlbum(id, album_id, lang)

  # Try looking up album directly.
  albums = SearchAlbums(album, limit=50, legacy=False)
  for a in albums:
    artist_id = String.Quote(a['artist'].decode('utf-8').encode('utf-8')).replace(' ','+')
    if LevenshteinRatio(a['name'], album) > 0.95 and artist_id == id:
      album_id = String.Quote(a['name'].decode('utf-8').encode('utf-8')).replace(' ','+')
      return GetAlbum(artist_id, album_id, lang)

  return None

@expose
def ArtistTopTracks(artist, lang='en'):
  id = String.Quote(artist.decode('utf-8').encode('utf-8')).replace(' ','+')
  return GetArtistTopTracks(id, lang)


@expose
def ArtistGetSimilar(artist, lang='en'):
  id = String.Quote(artist.decode('utf-8').encode('utf-8')).replace(' ','+')
  return GetArtistSimilar(id, lang)


@expose
def ArtistGetEvents(lastfm_artist):
  artist_mbid = ArtistMbidLookup(lastfm_artist)
  artist_songkickid = None

  if artist_mbid is None:
    artist_songkickid = GetArtistSongkickId(lastfm_artist['name'])

  return GetArtistEventsFromSongkickById(artist_mbid=artist_mbid, artist_songkickid=artist_songkickid)

# Change pinyin
def multi_get_letter(str_input): 
  if isinstance(str_input, unicode): 
    unicode_str = str_input 
  else: 
    try: 
      unicode_str = str_input.decode('utf8') 
    except: 
      try: 
        unicode_str = str_input.decode('gbk') 
      except: 
        print 'unknown coding'
        return
  return_list = [] 
  #for one_unicode in unicode_str: 
   # return_list.append(single_get_first(one_unicode)) 
  #return return_list
  return single_get_first(unicode_str)

def single_get_first(unicode1): 
  str1 = unicode1.encode('gbk') 
  try:     
    ord(str1) 
    return str1 
  except: 
    asc = ord(str1[0]) * 256 + ord(str1[1]) - 65536
    if asc >= -20319 and asc <= -20284: 
      return 'a'
    if asc >= -20283 and asc <= -19776: 
      return 'b'
    if asc >= -19775 and asc <= -19219: 
      return 'c'
    if asc >= -19218 and asc <= -18711: 
      return 'd'
    if asc >= -18710 and asc <= -18527: 
      return 'e'
    if asc >= -18526 and asc <= -18240: 
      return 'f'
    if asc >= -18239 and asc <= -17923: 
      return 'g'
    if asc >= -17922 and asc <= -17418: 
      return 'h'
    if asc >= -17417 and asc <= -16475: 
      return 'j'
    if asc >= -16474 and asc <= -16213: 
      return 'k'
    if asc >= -16212 and asc <= -15641: 
      return 'l'
    if asc >= -15640 and asc <= -15166: 
      return 'm'
    if asc >= -15165 and asc <= -14923: 
      return 'n'
    if asc >= -14922 and asc <= -14915: 
      return 'o'
    if asc >= -14914 and asc <= -14631: 
      return 'p'
    if asc >= -14630 and asc <= -14150: 
      return 'q'
    if asc >= -14149 and asc <= -14091: 
      return 'r'
    if asc >= -14090 and asc <= -13119: 
      return 's'
    if asc >= -13118 and asc <= -12839: 
      return 't'
    if asc >= -12838 and asc <= -12557: 
      return 'w'
    if asc >= -12556 and asc <= -11848: 
      return 'x'
    if asc >= -11847 and asc <= -11056: 
      return 'y'
    if asc >= -11055 and asc <= -10247: 
      return 'z'
    return ''

def pinyin(str_input): 
  b = ''
  if isinstance(str_input, unicode): 
    unicode_str = str_input 
  else: 
    try: 
      unicode_str = str_input.decode('utf8')
    except: 
      try: 
        unicode_str = str_input.decode('gbk')
      except: 
        #print 'unknown coding'
        return  
  for i in range(len(unicode_str)):
    b=b+single_get_first(unicode_str[i])
  return b.upper()
  

# Score lists of artist results.  Permutes artist_results list.
def score_artists(artists, media_artist, media_albums, lang, artist_results):
  
  for i, artist in enumerate(artists):

    # Need to coerce this into a utf-8 string so String.Quote() escapes the right characters.
    #id = String.Quote(artist['name'].decode('utf-8').encode('utf-8')).replace(' ','+')
    Log("第i个搜索结果")
    Log(i)
    id = str(artist['id'])
    Log("歌手ID:")
    Log(id)
    # Search returns ordered results, but no numeric score, so we approximate one with Levenshtein ratio.
    Log("搜索内容")
    Log(media_artist.lower())
    dist = int(ARTIST_MAX_DIST_PENALTY - ARTIST_MAX_DIST_PENALTY * LevenshteinRatio(artist['name'].lower(), media_artist.lower()))
    Log("搜索结果")
    Log(artist['name'])
    Log("中文差异")
    Log(dist)
    dist_en = int(ARTIST_MAX_DIST_PENALTY - ARTIST_MAX_DIST_PENALTY * LevenshteinRatio(','.join(artist['alias']), media_artist.lower()))
    Log("英文名")
    Log(','.join(artist['alias']))
    Log("英文差异")
    Log(dist_en)
    if dist_en < dist :
      dist = dist_en
    # If the match is exact, bonus.
    Log("最终dist")
    Log(dist)
    if artist['name'].lower() == media_artist.lower():
      dist = dist - 1
    # Fetching albums in order to apply bonus is expensive, so only do it for the top N artist matches.
    if i < ARTIST_ALBUMS_MATCH_LIMIT:
      bonus = get_album_bonus(media_albums, artist_id=id)
      Log("专辑得分")
      Log(bonus)
    else:
      bonus = 0
    

    Log("最终得分")
    # Adjust the score.
    score = ARTIST_INITIAL_SCORE + bonus - dist
    
    Log(score)
    # Finally, apply some heuristics based on listener count. If there's only a single result, it will not include the 'listeners' key.
    # Single results tend to be a good matches. Distrust artists with fewer than N listeners if it was not a really good match.
    #
    #if len(artists) > 1 and artist.has_key('listeners') and int(artist['listeners']) < ARTIST_MIN_LISTENER_THRESHOLD and score < ARTIST_MATCH_GOOD_SCORE:
    #  Log('Skipping %s with only %s listeners and score of %s.' % (artist['name'], artist['listeners'], score))
    #  continue
    
    name = artist['name']
    #listeners = artist['listeners'] if artist.has_key('listeners') else '(no listeners data)'
    #Log('Artist result: ' + name + ' dist: ' + str(dist) + ' album bonus: ' + str(bonus) + ' listeners: ' + str(listeners) + ' score: ' + str(score))
    
    # Skip matches that don't meet the minimum score.  There many be many, especially if this was a manual search.
    if score >= ARTIST_MATCH_MIN_SCORE:
      artist_results.append(MetadataSearchResult(id=id, name=name, lang=lang, score=score))
    else:
      Log('Skipping artist, didn\'t meet minimum score of ' + str(ARTIST_MATCH_MIN_SCORE))
      
    # Sort the resulting artists.
    artist_results.sort(key=lambda r: r.score, reverse=True)    

# Get albums by artist and boost artist match score accordingly.  Returns bonus (int) of 0 - ARTIST_ALBUM_MAX_BONUS.
def get_album_bonus(media_albums, artist_id):
  
  Log('匹配子专辑数据')
  bonus = 0
  albums = GetAlbumsByArtist(artist_id, albums=[], limit=ARTIST_ALBUMS_LIMIT)
  
  try:
    for a in media_albums:    
      media_album = a.lower()
      Log("文件子专辑名")
      Log(media_album)
      for album in albums:

        # If the album title is close enough to the media title, boost the score.
        Log("搜索专辑名")
        Log(album['name'].lower())
        Log("差异：")
        Log(Util.LevenshteinDistance(media_album,album['name'].lower()))
        if Util.LevenshteinDistance(media_album,album['name'].lower()) <= NAME_DISTANCE_THRESHOLD:
          bonus += ARTIST_ALBUM_BONUS_INCREMENT
        
        # This is a cheap comparison, so let's try again with the contents of parentheses removed, e.g. "(limited edition)"
        elif Util.LevenshteinDistance(media_album,RE_STRIP_PARENS.sub('',album['name'].lower())) <= NAME_DISTANCE_THRESHOLD:
          bonus += ARTIST_ALBUM_BONUS_INCREMENT
        
        # Stop trying once we hit the max bonus.
        if bonus >= ARTIST_ALBUM_MAX_BONUS:
          break
  
  except Exception, e:
    Log('Error applying album bonus: ' + str(e))
  if bonus > 0:
    Log('Applying album bonus of: ' + str(bonus))
  return bonus


class LastFmAgent(Agent.Artist):
  name = 'WangYiYun'
  languages = [Locale.Language.Chinese]

  def search(self, results, media, lang, manual):

    # Handle a couple of edge cases where artist search will give bad results.
    if media.artist == '[Unknown Artist]': 
      return
    if media.artist == 'Various Artists':
      results.Append(MetadataSearchResult(id = 'Various%20Artists', name= 'Various Artists', thumb = VARIOUS_ARTISTS_POSTER, lang  = lang, score = 100))
      return

    # Search for artist.
    Log('开始搜索: ' + media.artist)
    if manual:
      Log('Running custom search...')
    artist_results = []

    artists = SearchArtists(media.artist, ARTIST_MATCH_LIMIT)
    media_albums = [a.title for a in media.children]
    Log("子专辑列表")
    Log(media_albums)

    # Score the first N results.
    score_artists(artists, media.artist, media_albums, lang, artist_results)


    
    #search_str = String.Quote(media.artist)
    #m = JSON.ObjectFromURL(ARTIST_SEARCH_URL_WANGYI + search_str +SERACH_TYPE)
    #media_albums = [a.title for a in media.children]
    #Log(str(media_albums))
    #for artist in m['result']['artists']:
    #  artist_name = artist['name']
    #  Log(artist_name)
    #  artist_id = artist['id']
    #  Log(artist_id)
    #  artist_thumb = artist['img1v1Url']
    #  Log(artist_thumb)
      #results.Append(MetadataSearchResult(id = int(artist_id), name= artist_name, thumb = artist_thumb, lang  = lang, score = 100))
    #  id = String.Quote(artist_name.decode('utf-8').encode('utf-8')).replace(' ','+')
    #  dist = int(ARTIST_MAX_DIST_PENALTY - ARTIST_MAX_DIST_PENALTY * LevenshteinRatio(artist['name'].lower(), media.artist.lower()))
    #  Log(dist)
    #  if artist_name.lower() == media.artist.lower():
    #    dist = dist - 1
    #  
    #  score = ARTIST_INITIAL_SCORE - dist
    #  
    #  results.Append(MetadataSearchResult(id = str(artist_id), name= artist_name, thumb = artist_thumb, lang  = lang, score = score))

    for artist in artist_results:
      results.Append(artist)

  def update(self, metadata, media, lang):
    artist = GetArtist(metadata.id, lang)
   
    # Name.
    metadata.title = artist['name']
    Log(metadata.title)
    metadata.title_sort = pinyin(metadata.title)
    # Bio.
    try:
      metadata.summary = artist['briefDesc'].strip()
      Log(metadata.summary )
    except:
      pass

    # Artwork.
    if artist['name'] == 'Various Artists':
      metadata.posters[VARIOUS_ARTISTS_POSTER] = Proxy.Media(HTTP.Request(VARIOUS_ARTISTS_POSTER))
    else:
      try: 
          metadata.posters[artist['picUrl']] = Proxy.Media(HTTP.Request(artist['picUrl']))
      except:
        Log('Couldn\'t add artwork for artist.')

  
class LastFmAlbumAgent(Agent.Album):
  name = 'WangYiYun'
  languages = [Locale.Language.Chinese]
  
  def search(self, results, media, lang, manual):

    # Handle a couple of edge cases where album search will give bad results.
    if media.parent_metadata.id is None:
      return
    if media.parent_metadata.id == '[Unknown Album]':
      return #eventually, we might be able to look at tracks to match the album

    # Search for album.
    if manual:
      # If this is a custom search, use the user-entered name instead of the scanner hint.
      Log("media.name:" + media.name)
      try:
        Log('手动搜索: ' + media.name)
        media.title = media.name
      except:
        pass
    else:
      Log('搜索专辑: ' + media.title)
    albums = []
    found_good_match = False

    # First try matching in the list of albums by artist for single-artist albums.
    if media.parent_metadata.id != 'Various%20Artists':

      # Start with the first N albums (ideally a single API request).
      if not manual:
        albums = self.score_albums(media, lang, GetAlbumsByArtist(media.parent_metadata.id, albums=[]))
        Log('自动结果')
        Log(albums)
        # Check for a good match within these reults.  If we find one, set the flag to stop looking.
        if albums and albums[0]['score'] >= ALBUM_MATCH_GOOD_SCORE:
          found_good_match = True
          Log('Good album match found (quick search) with score: ' + str(albums[0]['score']))

      # If we haven't found a good match yet, or we're running a custom search, get all albums by artist.  May be thousands
      # of albums and several API requests to complete this list, so we use it sparingly.
      if not found_good_match or manual:
        if manual:
          Log('Custom search terms specified, fetching all albums by artist.')
        else:
          Log('No good matches found in first ' + str(len(albums)) + ' albums, fetching all albums by artist.')
        albums = self.score_albums(media, lang, GetAlbumsByArtist(media.parent_metadata.id, albums=[]), manual=manual)
        Log('手动结果')
        Log(albums)
        # If we find a good match this way, set the flag to stop looking.
        if albums and albums[0]['score'] >= ALBUM_MATCH_GOOD_SCORE:
          Log('Good album match found with score: ' + str(albums[0]['score']))
          found_good_match = True
        else:
          Log('No good matches found in ' + str(len(albums)) + ' albums by artist.')

    # Either we're looking at Various Artists, or albums by artist search did not contain a good match.
    # Last.fm mysteriously omits certain (often popular) albums from albums-by-artist results, so it's
    # important to fall back even in the case of single-artist albums.

    #此区域待定
    if not found_good_match or albums:
    #if  found_good_match == False:
      Log('没有匹配到合适专辑 开始搜索专辑')
      albums = self.score_albums(media, lang, SearchAlbums(media.title.lower(), ALBUM_MATCH_LIMIT), manual=manual) + albums
      
      # If we find a good match for the exact search, stop looking.
      if albums and albums[0]['score'] >= ALBUM_MATCH_GOOD_SCORE:
        found_good_match = True
        Log('Found a good match for album search.')
      
      # If we still haven't found anything, try another match with parenthetical phrases stripped from
      # album title.  This helps where things like '(Limited Edition)' and '(disc 1)' may confuse search.
      if not albums or not found_good_match:
        stripped_title = RE_STRIP_PARENS.sub('',media.title).lower()
        if stripped_title != media.title.lower():
          Log('No good matches found in album search for %s, searching for %s.' % (media.title.lower(), stripped_title))
          # This time we extend the results  and re-sort so we consider the best-scoring matches from both searches.
          albums  = self.score_albums(media, lang, SearchAlbums(stripped_title), manual=manual) + albums
        if albums:
          albums = sorted(albums, key=lambda k: k['score'], reverse=True)

    # Dedupe albums.
    seen = {}
    deduped = []
    for album in albums:
      if album['id'] in seen:
        continue
      seen[album['id']] = True
      deduped.append(album)
    albums = deduped

    Log('Found ' + str(len(albums)) + ' albums...')

    # Limit to 10 albums.
    albums = albums[:10]
    Log(albums)
    for album in albums:
      if album['score'] > 0:
        Log(album['score'])
        Log(album['id'])
        Log(album['name'])
        Log(album['lang'])
        results.Append(MetadataSearchResult(id = str(album['id']), name = album['name'], lang = album['lang'], score = str(album['score'])))

  # Score a list of albums, return a fresh list of scored matches above the ALBUM_MATCH_MIN_SCORE threshold.
  def score_albums(self, media, lang, albums, manual=False):
    res = []
    matches = []
    for album in albums:
      try:
        name = album['name']
        Log("匹配专辑名：" + name)
        
        # Sanitize artist.  Last.fm sometimes returns a string, sometimes a list.
        if album.has_key('artist'):
          if not isinstance(album['artist'], basestring):
            artist = album['artist']['name']
          else:
            artist = album['artist']
        else:
          artist = ''
        Log("专辑艺术家：" + artist)
        #id = media.parent_metadata.id + '/' + String.Quote(album['name'].decode('utf-8').encode('utf-8')).replace(' ','+')
        id = media.parent_metadata.id + '/' + str(album['id'])
        Log("歌手+专辑 id组合" + id)
        dist = Util.LevenshteinDistance(name.lower(),media.title.lower()) * ALBUM_NAME_DIST_COEFFICIENT  #专辑名称差
        Log("专辑相似差：")
        Log(dist)
        # Freeform album searches will come back with wacky artists.  If they're not close, penalize heavily, skipping them.
        artist_dist = Util.LevenshteinDistance(artist.lower(),String.Unquote(media.parent_metadata.title).lower())      #艺术家差
        Log("艺术家差：")
        Log(artist_dist)
        if artist_dist > ALBUM_TRACK_BONUS_MAX_ARTIST_DSIT:
          artist_dist = 1000
          Log('艺术家匹配错误 ' + artist)
        
        # Apply album and artist penalties and append to temp results list.
        score = ALBUM_INITIAL_SCORE - dist - artist_dist
        Log("匹配分数：")
        Log(score)
        res.append({'id':id, 'name':name, 'lang':lang, 'score':score})
      
      except:
        Log('Error scoring album.')

    if res:
      res = sorted(res, key=lambda k: k['score'], reverse=True)
      Log(res)
      for i, result in enumerate(res):
        # Fetching albums to apply track bonus is expensive, so only do it for the top N results. 对排名前几的专辑进行歌曲验证
        if i < ALBUM_TRACK_BONUS_MATCH_LIMIT:
          Log("id=:"+ result['id'].split('/')[1])
          Log("验证专辑："+ result['name'])
          bonus = self.get_track_bonus(media, result['id'].split('/')[1], lang)
          Log(bonus)
          res[i]['score'] = res[i]['score'] + bonus
          Log(res[i]['score'])
        # Append albums that meet the minimum score, skip the rest.
        if res[i]['score'] >= ALBUM_MATCH_MIN_SCORE or manual:
          Log('Album result: ' + result['name'] + ' album bonus: ' + str(bonus) + ' score: ' + str(result['score']))
          matches.append(res[i])
        else:
          Log('Skipping %d album results that don\'t meet the minimum score of %d.' % (len(res) - i, ALBUM_MATCH_MIN_SCORE))
          break

    # Sort once more to account for track bonus and return.
    if matches:
      return sorted(matches, key=lambda k: k['score'], reverse=True)
    else:
      return matches
  
  # Get album info in order to compare track listings and apply bonus accordingly.  Return a bonus (int) of 0 - ALBUM_TRACK_MAX_BONUS.
  def get_track_bonus(self, media, album_id, lang):
    tracks = GetTracks(media.parent_metadata.id,str(album_id), lang)
    bonus = 0
    try:
      for i, t in enumerate(media.children):
        media_track = t.title.lower()
        Log("音轨文件名：" + media_track)
        for j, track in enumerate(tracks):

          # If the names are close enough, boost the score.
          Log("匹配文件名：" + track['name'] + "二者差：")
          Log(Util.LevenshteinDistance(track['name'].lower(), media_track))
          if Util.LevenshteinDistance(track['name'].lower(), media_track) <  NAME_DISTANCE_THRESHOLD:
            bonus += ALBUM_TRACK_BONUS_INCREMENT

      # If the albums have the same number of tracks, boost more.
      if len(media.children) == len(tracks):
        bonus += ALBUM_NUM_TRACKS_BONUS
      
      # Cap the bonus.
      if bonus >= ALBUM_TRACK_MAX_BONUS:
        bonus = ALBUM_TRACK_MAX_BONUS

    except:
      Log('Didn\'t find any usable tracks in search results, not applying track bonus.')

    if bonus > 0:
      Log('Applying track bonus of: ' + str(bonus))
    return bonus
 
  def update(self, metadata, media, lang):
    album = GetAlbum(metadata.id.split('/')[1], lang)
    if not album:
      return

    # Title.
    metadata.title = album['name']
    
    # Artwork.
    try:
      valid_keys = album['picUrl']
      metadata.posters[valid_keys] = Proxy.Media(HTTP.Request(valid_keys))
      metadata.posters.validate_keys(valid_keys)
    except:
      Log('Couldn\'t add artwork for album.')

    # Release Date.
    try:
      Log(Datetime.ParseDate(time.strftime("%Y-%m-%d", time.localtime(int(int(album['publishTime'])/1000)))))
      metadata.originally_available_at = Datetime.ParseDate(time.strftime("%Y-%m-%d", time.localtime(int(int(album['publishTime'])/1000))))
    except:
      Log('Couldn\'t add release date to album.')
      
    # 简介
    try:
      metadata.summary = album['description'].replace('\n',' ')
      Log(metadata.summary)
    except:
      Log("获取简介失败")
    # Genres.
    metadata.genres.clear()
    if Prefs['genres']:
      try:
        for genre in Listify(album['toptags']['tag']):
          metadata.genres.add(genre['name'].capitalize())
      except:
        Log('Couldn\'t add genre tags to album.')

    # Top tracks.
    most_popular_tracks = {}
    try:
      top_tracks = GetArtistTopTracks(metadata.id.split('/')[0], lang)
      #Log(top_tracks)
      for track in top_tracks:
        most_popular_tracks[track['name']] = int(track['pop'])
      Log("流行音轨：")
      Log(most_popular_tracks)
    except:
      pass

    for index in media.tracks:
      key = media.tracks[index].guid or int(index)
      Log("key:")
      Log(key)
      for popular_track in most_popular_tracks.keys():
        Log("popular_track:")
        Log(popular_track)
        Log("media.tracks[index].title :")
        Log(media.tracks[index].title)
        Log("音轨名与流行音轨相似度：")
        Log(LevenshteinRatio(popular_track, media.tracks[index].title))
        if popular_track and LevenshteinRatio(popular_track, media.tracks[index].title) > 0.95:
          t = metadata.tracks[key]
          Log("t :")
          Log(t)
          if Prefs['popular']:
            t.rating_count = most_popular_tracks[popular_track]
          else:
            t.rating_count = 0
          Log("t.rating_count:")
          Log(t.rating_count)

def SearchArtists(artist, limit=10):
  artists = []

  if not artist:
    Log('Missing artist. Skipping match')
    return artists
  try:
    a = artist.lower().encode('utf-8')
  except:
    a = artist.lower()
  Log(a)
  url = ARTIST_SEARCH_URL_WANGYI + String.Quote(a) +SERACH_TYPE
  Log(url)
  try: 
    response = GetJSON(url)
    num = int(response['result']['artistCount'])
  except:
    Log('Error retrieving artist search results.')
    
  lim = min(limit,num)
  Log('搜索到的歌手数量：')
  Log(lim)
  for i in range(lim):
    try:
      artist_results = response['result']
      artists = artists + Listify(artist_results['artists'])
    except:
      Log('Error retrieving artist search results.')
  # Since LFM has lots of garbage artists that match garbage inputs, we'll only consider ones that have
  # either a MusicBrainz ID or artwork.
  #
  #valid_artists = [a for a in artists if a['mbid'] or (len(a.get('image', [])) > 0 and a['image'][0].get('#text', None))]
  #if len(artists) != len(valid_artists):
  #  Log('Skipping artist results because they lacked artwork or MBID: %s' % ', '.join({a['name'] for a in artists}.difference({a['name'] for a in valid_artists})))

  #return valid_artists
  return artists


def SearchAlbums(album, limit=10, legacy=False):
  albums = []

  if not album:
    Log('Missing album. Skipping match')
    return albums

  try:
    a = album.lower().encode('utf-8')
  except:
    a = album.lower()
  Log("专辑搜索内容" + a)
  url = ARTIST_SEARCH_URL_WANGYI + String.Quote(a) + "&type=10&offset=0&total=true&limit=100"
  try:
    response = GetJSON(url)
    if response.has_key('error'):
      Log('搜索结果错误: ' + response['message'])
      return albums
    else:
      album_results = response['result']
      albums = Listify(album_results['albums'])
  except:
    Log('Error retrieving album search results.')

  return albums


def GetAlbumsByArtist(artist_id, limit=ARTIST_ALBUMS_LIMIT*4,albums=[], legacy=True):
  Log("搜索歌手id" + artist_id)
  url = ARTIST_ALBUM_SEARCH_URL_WANGYI + artist_id + '?id=' + artist_id + '&offset=0&total=true&limit=' + str(limit)
  response = GetJSON(url)
  try:
    albums.extend(Listify(response['hotAlbums']))
  except:
    # Sometimes the API will lie and say there's an Nth page of results, but the last one will return garbage.
    pass
  return albums


def GetArtist(id, lang='en'):
  url = ARTIST_URL_WANGYI + id
  try:
    artist_results = GetJSON(url)
    if artist_results.has_key('error'):
      Log('Error retrieving artist metadata: ' + artist_results['message'])
      return {}
    return artist_results['artist']
  except:
    Log('Error retrieving artist metadata.')
    return {}


def GetAlbum(album_id, lang='en'):
  url = ALBUM_INFO_URL_WANGYI + album_id + '?ext=true&id='+ album_id +'&offset=0&total=true&limit=100'
  try:
    album_results = GetJSON(url)
    if album_results.has_key('error'):
      Log('Error retrieving album metadata: ' + album_results['message'])
      return {}
    return album_results['album']
  except:
    Log('Error retrieving album metadata.')
    return {}


def GetTracks(artist_id, album_id, lang='en'):
  url = ALBUM_INFO_URL_WANGYI + album_id + '?ext=true&id='+ album_id +'&offset=0&total=true&limit=100'
  try:
    tracks_result = GetJSON(url)
    return Listify(tracks_result['album']['songs'])
  except:
    Log('Error retrieving tracks.')
    return []


def GetArtistTopTracks(artist_id, lang='en'):
  result = []
  url = ARTIST_URL_WANGYI + artist_id.lower()
  Log(url)
  top_tracks_result = GetJSON(url)
  total_pages = 15
  if len(top_tracks_result['hotSongs']) <= 15 :
      total_pages = len(top_tracks_result['hotSongs'])
  try:
    page = 0
    Log("开始提取大于95的pop")
    #for songs in Listify(top_tracks_result['hotSongs']):
    for songs in top_tracks_result['hotSongs']:
      Log("音轨名：" +  songs['name'])
      Log("得分：")
      Log(songs['pop'])
      if int(songs['pop']) >= 95 :
        new_results = songs
        result.append(new_results)
      # Get out if we've exceeded the number of pages.
      #page += 1
      #if page > total_pages:
      #  break
  except:
    Log('Exception getting top tracks.')
  return result

def GetArtistSimilar(artist_id, lang='en'):
  url = ARTIST_SIMILAR_ARTISTS_URL % (artist_id.lower(), lang)
  try:
    similar_artists_result = GetJSON(url)
    if similar_artists_result.has_key('error'):
      Log('Error receiving similar artists: ' + similar_artists_result['message'])
      return []
    if isinstance(similar_artists_result['similarartists']['artist'], list) or isinstance(similar_artists_result['similarartists']['artist'], dict):
      return Listify(similar_artists_result['similarartists']['artist'])
  except:
    Log('Exception getting similar artists.')
    return []

@expose
def GetArtistEventsFromSongkickById(artist_mbid=None, artist_songkickid = None):
  url = None
  if artist_mbid:
    url = SONGKICK_ARTIST_EVENTS_URL_MBID % artist_mbid
  elif artist_songkickid:
    url = SONGKICK_ARTIST_EVENTS_URL_SONGKICKID % artist_songkickid
  else:
    return []
  
  try:
    events_result = GetSongkickJSON(url, cache_time=CACHE_1WEEK)
    status = events_result['resultsPage']['status']
    totalEntries = events_result['resultsPage']['totalEntries']
    if status == 'ok' and totalEntries > 0:
      return events_result['resultsPage']['results']['event']
  except:
    Log('Exception getting events.')

  return []


def GetArtistSongkickId(artist_name):
  artist_name_escaped = NormalizeArtist(artist_name)
  url = SONGKICK_ARTIST_SEARCH_URL % artist_name_escaped
  try:
    artist_search_result = GetSongkickJSON(url, cache_time=CACHE_1WEEK)
    status = artist_search_result['resultsPage']['status']
    totalEntries = artist_search_result['resultsPage']['totalEntries']
    if status == 'ok' and totalEntries > 0:
      first_artist_result = artist_search_result['resultsPage']['results']['artist'][0]
      artist_songkick_name = first_artist_result['displayName']
      if LevenshteinRatio(artist_name_escaped, NormalizeArtist(artist_songkick_name)) > 0.95:
        return first_artist_result['id']
  except:
    Log('Exception searching Songkick artist id.')
  
  return None


def GetJSON(url, sleep_time=QUERY_SLEEP_TIME, cache_time=CACHE_1MONTH):
  d = None
  try:
    d = JSON.ObjectFromURL(url, sleep=sleep_time, cacheTime=cache_time, headers={'Accept-Encoding':'gzip', 'X-PLEX-VERSION':'2.0'})
    if isinstance(d, dict):
      return d
  except:
    Log('Error fetching JSON.')
    return None


def GetSongkickJSON(url, sleep_time=QUERY_SLEEP_TIME, cache_time=CACHE_1MONTH):
  d = None
  try:
    d = JSON.ObjectFromURL(SONGKICK_BASE_URL % String.Quote(url, True), sleep=sleep_time, headers={'Accept': 'application/json'}, cacheTime=cache_time)
    if isinstance(d, dict):
      return d
  except:
    Log('Error fetching JSON.')
    return None


def LevenshteinRatio(first, second):
  return 1 - (Util.LevenshteinDistance(first, second) / float(max(len(first), len(second))))

def NormalizeArtist(name):
  return Core.messaging.call_external_function('com.plexapp.agents.plexmusic', 'MessageKit:NormalizeArtist', kwargs = dict(artist=name))

# Utility functions for sanitizing Last.fm API responses.
def Listify(obj):
  if isinstance(obj, list):
    return obj
  else:
    return [obj]

def Dictify(obj, key=''):
  if isinstance(obj, dict):
    return obj
  else:
    return {key:obj}
