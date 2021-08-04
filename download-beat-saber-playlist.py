import argparse
import glob
import hashlib
import json
import os

import requests
from win32com.shell import shell, shellcon
import win32con
import win32event
import win32file


BEATSAVER_BASE_URL = 'https://beatsaver.com/api'


def get_beat_saber_path(playlist_path):
    playlist_dir = os.path.dirname(playlist_path)
    if os.path.basename(playlist_dir) != 'Playlists':
        raise ValueError(f"{playlist_path}: Playlist is not in Beat Saber's playlist directory")

    return os.path.dirname(playlist_dir)


def get_map_hash(song_dir):
    info_dat_path = os.path.join(song_dir, 'info.dat')
    hasher = hashlib.sha1()

    with open(info_dat_path, 'rb') as f:
        contents = f.read()
        hasher.update(contents)
        info_dat = json.loads(contents)

    for diff_set in info_dat['_difficultyBeatmapSets']:
        for d in diff_set['_difficultyBeatmaps']:
            with open(os.path.join(song_dir, d['_beatmapFilename']), 'rb') as f:
                hasher.update(f.read())

    return hasher.hexdigest()


def get_all_map_hashes(songs_dir):
    hashes = set()

    for info_dat_path in glob.iglob(os.path.join(songs_dir, '*', 'info.dat')):
        song_dir = os.path.dirname(info_dat_path)
        hashes.add(get_map_hash(song_dir))

    return hashes


def beatsaver_request(endpoint):
    assert endpoint.startswith('/')

    r = requests.get(f"{BEATSAVER_BASE_URL}{endpoint}",
                     headers={"user-agent": "ModAssistant"})
    r.raise_for_status()
    return r.json()


def shellexecute_and_wait(path):
    p = shell.ShellExecuteEx(
        nShow=win32con.SW_SHOW,
        fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
        lpFile=path,
    )

    try:
        win32event.WaitForSingleObject(p['hProcess'], win32event.INFINITE)
    finally:
        win32file.CloseHandle(p['hProcess'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='Path to playlist file')
    args = parser.parse_args()

    # Get Beat Saber path from playlist path
    beat_saber_path = get_beat_saber_path(os.path.abspath(args.path))
    songs_dir = os.path.join(beat_saber_path, 'Beat Saber_Data', 'CustomLevels')

    # Get a list of all song hashes
    hashes = get_all_map_hashes(songs_dir)

    # Parse playlist
    with open(args.path, 'r') as f:
        playlist_data = json.load(f)

    print(f"Playlist title: {playlist_data['playlistTitle']}")
    print(f"Playlist author: {playlist_data['playlistAuthor']}")
    print(f"Number of songs: {len(playlist_data['songs'])}")

    for song in playlist_data['songs']:
        song_hash = song['hash'].lower()
        if 'songName' in song:
            song_name = song['songName']
        else:
            song_name = song['name']

        print(f"{song_hash} ({song_name})")

        if song_hash in hashes:
            print('- Already exists')
            continue

        if 'key' in song:
            key = song['key']
        else:
            key = beatsaver_request(f'/maps/hash/{song_hash}')['key']

        beatsaver_uri = f'beatsaver://{key}/'
        print(f'- Invoking: {beatsaver_uri}')

        shellexecute_and_wait(beatsaver_uri)


if __name__ == '__main__':
    main()
