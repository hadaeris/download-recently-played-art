import requests
import json
import urllib.request
import time
import base64
import os
import datetime

#lastfm
API_KEY = ''
USER_AGENT = ''
SECRET = ''
SESSION_KEY =''

#spotify
SPOTIFY_SECRET = ""
SPOTIFY_ID = ""

NUM_PHOTOS = 10
PULL_INTERVAL=6*60

TARGET_DIRECTORY = "/home/pi/MagicMirror/modules/MMM-BackgroundSlideshow/exampleImages/"

class AuthError(Exception):

	def __init__(self):
		super().__init__("Failed to get spotify token!")

class ConnectionError(Exception):

	def __init__(self, message="Connection error!"):
		super().__init__(message)

def main():
	last_pull_time = datetime.datetime(1970, 1, 1)
	# lastfm_token = get_lastfm({'method': 'auth.getToken'}).json()['token']
	downloaded = set()
	while(True): 
		current_pull_time = datetime.datetime.now()
		try:
			if ((current_pull_time - last_pull_time).total_seconds() / 60) > 55:
				spotify_token = get_token_spotify()
				print("refreshed new spotify access token")
				last_pull_time = current_pull_time
			print("begin pull at " + str(current_pull_time))
			photo_urls = get_photos(NUM_PHOTOS, spotify_token)
			downloaded = download_photos(photo_urls, downloaded)
		# except:
		except Exception as e: 
			print("probably connection error! skipping this cycle. check internet connection, or something went wrong at lastfm/spotify. too lazy to write exceptions to determine which, find out yourself!")
		print("done!")
		print("________________________")
		time.sleep(PULL_INTERVAL)
		print("\n\n")


def get_lastfm(payload):

	headers = {
		'user-agent': USER_AGENT
	}
	url = 'https://ws.audioscrobbler.com/2.0/'

	payload['api_key'] = API_KEY
	payload['format'] = 'json'

	return requests.get(url, headers=headers, params=payload)

# def get_sig(method, token):
# 	return hashlib.md5(("api_key"+API_KEY+"method"+method+"token"+token+SECRET).encode('UTF-8')).hexdigest()



def get_top_artists():
	top_artists_JSON = get_lastfm({'method': 'user.getTopArtists', 'user': USER_AGENT, 'limit': '5', 'period': '7day', 'api_key': API_KEY}).json()
	return [artist['name'] for artist in top_artists_JSON['topartists']['artist']]

def get_top_albums():
	top_albums_JSON = get_lastfm({'method': 'user.getTopAlbums', 'user': USER_AGENT, 'limit': '5', 'period': '7day', 'api_key': API_KEY}).json()
	return [album['name'] for album in top_albums_JSON['topalbums']['album']]

def get_recent_tracks(number):
	recent_tracks_JSON = get_lastfm({'method': 'user.getRecentTracks', 'limit': number, 'user': USER_AGENT}).json()
	return recent_tracks_JSON



def get_token_spotify():
	headers = {
		"Authorization": "Basic " + base64.b64encode("{}:{}".format(SPOTIFY_ID, SPOTIFY_SECRET).encode('UTF-8')).decode('ascii'),
		"Content-Type": "application/x-www-form-urlencoded"
	}

	payload = {
		"grant_type": "client_credentials"
	}

	url = "https://accounts.spotify.com/api/token/"
	try:
		return requests.post(url, headers=headers, params=payload).json()['access_token']
	except KeyError:
		raise AuthError()
	except ConnectionError:
		raise ConnectionError("Connection failed when trying to get spotify token!")

def search_spotify(token, keyword, query_type):
	headers = {
		"Authorization": "Bearer " + token,
		"Content-Type": "application/json"
	}

	payload = {
		"q": keyword,
		"type": query_type
	}
	url = "https://api.spotify.com/v1/search/"

	return requests.get(url, headers=headers, params=payload)

def get_artist_by_spotify_id(artist_id, spotify_token):
	headers = {
		"Authorization": "Bearer " + spotify_token,
		"Content-Type": "application/json"
	}

	url = "https://api.spotify.com/v1/artists/" + artist_id

	return requests.get(url, headers=headers)

def get_image_from_artist_search(artist_name, response):
	try:
		results = response["artists"]["items"]
		for artist in results:
			if artist["name"] == artist_name:
				return artist["images"][0]["url"]
	except KeyError:
		print("key error in get_image_from_artist! response not in expected form!")
		print(json.dumps(response, indent=4))
	return None

# def get_image_from_artist(response):
# 	try:
# 		return response['images'][0]["url"]
# 	except:
# 		print("response not in expected form when getting image from single artist!")

def get_photos(number, spotify_token):
	current_urls = set()
	return_urls = dict()
	recent_tracks = get_recent_tracks(40)["recenttracks"]["track"]
	i = 0

	while len(current_urls) < number and i < 40:
		print("scanning " + str(i) + " track...")

		current_track = recent_tracks[i]
		track_images = current_track["image"]
		# album_art_url = track_images[len(track_images) - 1]['#text']
		
		artist_name = current_track["artist"]["#text"]
		track_name = current_track["name"] + " " + artist_name
		spotify_query = search_spotify(spotify_token, track_name, "track").json()
		try:
			album_art_url = spotify_query["tracks"]["items"][0]["album"]["images"][0]["url"]
		except (KeyError, IndexError) as e:
			print("response when querying for album art not of expected type!")
			print(json.dumps(spotify_query, indent=4))

		time.sleep(.4)
		if (str(album_art_url) not in current_urls):
			current_urls.add(str(album_art_url))
			print("found new album art: " + track_name)
			return_urls[track_name] = album_art_url
		else:
			try:
				time.sleep(.1)
				artist_id = spotify_query["tracks"]["items"][0]["artists"][0]["id"]
				artist_query = get_artist_by_spotify_id(artist_id, spotify_token).json()
				artist_art_url = artist_query["images"][0]["url"]
				if (artist_art_url is not None and str(artist_art_url) not in current_urls):
					print("found new artist image: " + artist_name)
					current_urls.add(str(artist_art_url))
					return_urls[artist_name] = str(artist_art_url)
				else:
					print("could not find new album art or artist art. skipping!")
			except KeyError:
				print("response when querying by artist id not of expected type!")
				print("queried for: " + artist_id)
				print(json.dumps(artist_query, indent=4))
		i+=1

	print("\n")
	return return_urls

def convert_to_filename(identifier):
	return str(base64.urlsafe_b64encode(identifier.encode('utf8'))).replace("'", "")
# print(json.dumps(recent_tracks, indent=2))

def download_photos(photo_urls, already_downloaded):
	downloaded = set()

	for identifier in photo_urls.keys():
		url = photo_urls[identifier]
		print("downloading '" + str(identifier) + "' from " + url)
		hashed_name = convert_to_filename(url)
		if hashed_name in already_downloaded:
			downloaded.add(hashed_name)
			print("'" + identifier + "' already downloaded!\n")
			continue
		attempts = 5
		while attempts > 0:
			try:
				urllib.request.urlretrieve(url, TARGET_DIRECTORY+hashed_name+".jpg")
				downloaded.add(hashed_name)
				print("successfully downloaded '" + identifier + "'")
			except:
				print("failed! attempts left: " + str(attempts))
				attempts -= 1
				continue
			else:
				break
		print("\n")

	print("\n")
	for file in already_downloaded:
		if file not in downloaded:
			full_target = TARGET_DIRECTORY + file + ".jpg"
			if (os.path.isfile(full_target)):
				print("removing " + file + ".jpg")
				os.remove(full_target)

	return downloaded

if __name__ == "__main__":
    main()