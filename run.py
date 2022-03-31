import requests
import json
import urllib.request
import time
import base64
import os
import datetime
import logging

# spotify
SPOTIFY_SECRET = ""
SPOTIFY_ID = ""
SPOTIFY_REFRESH_TOKEN = ""  # scope: user-recently-played

NUM_PHOTOS = 10
PULL_INTERVAL = 6 * 60

TARGET_DIRECTORY = "/home/pi/MagicMirror/modules/MMM-BackgroundSlideshow/exampleImages/"

logger = logging.getLogger()
handler = logging.FileHandler("errorlog.log")
logger.addHandler(handler)


class AuthError(Exception):

    def __init__(self):
        super().__init__("Failed to get spotify token!")


def main():
    last_pull_time = datetime.datetime(1970, 1, 1)
    # lastfm_token = get_lastfm({'method': 'auth.getToken'}).json()['token']
    downloaded = set()
    photo_urls = dict()

    # delete any photos in download directory
    print("cleaning target folder... expecting only images")
    for filename in os.listdir(TARGET_DIRECTORY):
        path = os.path.join(TARGET_DIRECTORY, filename)
        try:
            os.unlink(path)
        except OSError:
            print("what did you put in this folder")
    print("done! \n\n")

    attempts = 0
    while True:
        current_pull_time = datetime.datetime.now()

        # for backup
        old_photo_urls = photo_urls.copy()
        old_downloaded = downloaded.copy()

        try:
            if ((current_pull_time - last_pull_time).total_seconds() / 60) > 55:
                spotify_token = get_token_spotify(SPOTIFY_REFRESH_TOKEN)
                print("refreshed new spotify access token: " + spotify_token)
                last_pull_time = current_pull_time
            print("begin pull at " + str(current_pull_time))

            photo_urls = get_photos(NUM_PHOTOS, spotify_token)
            downloaded = download_photos(photo_urls, downloaded)
        except Exception as e:
            print(
                "probably connection error! skipping this cycle. check internet connection, or something went wrong "
                "at lastfm/spotify. too lazy to write exceptions to determine which, find out yourself!")
            logger.exception("connection related error at: " + str(current_pull_time))
            if attempts < 3:
                photo_urls = old_photo_urls
                downloaded = old_downloaded
                print("trying again! " + "attempt: " + str(attempts) + "\n")
                attempts += 1
                time.sleep(3)
                continue
            else:
                print("failed too many times... trying again at next interval")

        attempts = 0
        print("done!")
        print("________________________")
        time.sleep(PULL_INTERVAL)
        print("\n\n")


def get_token_spotify(refresh_token=None):
    url = "https://accounts.spotify.com/api/token/"
    headers = {
        "Authorization": "Basic " + base64.b64encode("{}:{}".format(SPOTIFY_ID, SPOTIFY_SECRET).encode('UTF-8')).decode(
            'ascii'),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    if not refresh_token:

        payload = {
            "grant_type": "client_credentials"
        }
        try:
            return requests.post(url, headers=headers, params=payload).json()['access_token']
        except KeyError:
            raise AuthError()
        except ConnectionError:
            raise ConnectionError("Connection failed when trying to get spotify token!")
    else:
        print("using refresh token for user access...")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        try:
            return requests.post(url, headers=headers, params=payload).json()['access_token']
        except KeyError:
            raise AuthError()
        except ConnectionError:
            raise ConnectionError("Connection failed when trying to get spotify token using refresh token!")


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


def get_recent_tracks_spotify(count, spotify_token):
    url = "https://api.spotify.com/v1/me/player/recently-played"

    headers = {
        "Authorization": "Bearer " + spotify_token
    }

    payload = {
        "limit": count,
    }
    return requests.get(url, headers=headers, params=payload)


def get_photos(number, spotify_token):
    current_urls = set()
    return_urls = dict()
    recent_tracks = get_recent_tracks_spotify(40, spotify_token).json()["items"]
    i = 0

    while len(current_urls) < number and i < 40:
        print("scanning " + str(i) + " track...")

        current_track = recent_tracks[i]
        track_images = current_track["track"]["album"]["images"]  # get url of largest image
        album_art_url = track_images[0]['url']

        artist_name = current_track["track"]["artists"][0]["name"]
        track_name = current_track["track"]["name"] + " " + artist_name

        if str(album_art_url) not in current_urls:
            current_urls.add(str(album_art_url))
            print("found new album art: " + track_name)
            return_urls[track_name] = album_art_url
        else:
            try:
                time.sleep(.2)
                artist_id = current_track["track"]["artists"][0]["id"]
                artist_query = get_artist_by_spotify_id(artist_id, spotify_token).json()
                artist_art_url = artist_query["images"][0]["url"]
                if artist_art_url is not None and str(artist_art_url) not in current_urls:
                    print("found new artist image: " + artist_name)
                    current_urls.add(str(artist_art_url))
                    return_urls[artist_name] = str(artist_art_url)
                else:
                    print("could not find new album art or artist art. skipping!")
            except KeyError:
                print("response when querying by artist id not of expected type!")
                print("queried for: " + artist_id)
                print(json.dumps(artist_query, indent=4))
        i += 1

    print("\n")
    return return_urls


def convert_to_filename(identifier):
    return str(base64.urlsafe_b64encode(identifier.encode('utf8'))).replace("'", "")


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
                urllib.request.urlretrieve(url, TARGET_DIRECTORY + hashed_name + ".jpg")
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
            if os.path.isfile(full_target):
                print("removing " + file + ".jpg")
                os.remove(full_target)

    return downloaded


if __name__ == "__main__":
    main()
