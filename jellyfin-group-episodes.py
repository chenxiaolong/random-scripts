#!/usr/bin/env python3

import argparse
import requests


class JellyfinClient:
    def __init__(self, base_url, username, api_key):
        self.base_url = base_url
        self.username = username
        self.api_key = api_key

        self.user_id = self.get_user_by_name(self.username)['Id']

    def _request(self, method, path, *args, **kwargs):
        kwargs.setdefault('headers', {}) \
            .setdefault('Authorization',
                        f'MediaBrowser Token="{self.api_key}"')

        return requests.request(method, self.base_url + path, *args, **kwargs)

    def _get(self, path, *args, **kwargs):
        return self._request('get', path, *args, **kwargs)

    def _post(self, path, *args, **kwargs):
        return self._request('post', path, *args, **kwargs)

    def get_user_by_name(self, name):
        r = self._get('/Users')
        r.raise_for_status()

        data = r.json()
        for user in data:
            if user['Name'] == name:
                return user

        raise ValueError(f'User {name} not found')

    def get_series(self):
        r = self._get(
            f'/Users/{self.user_id}/Items',
            params={
                'IncludeItemTypes': 'Series',
                'Recursive': 'true',
            },
        )
        r.raise_for_status()

        data = r.json()
        return data['Items']

    def get_seasons(self, series_id):
        r = self._get(
            f'/Shows/{series_id}/Seasons',
            params={
                'userId': self.user_id,
            },
        )
        r.raise_for_status()

        data = r.json()
        return data['Items']

    def get_episodes(self, series_id, season_id):
        r = self._get(
            f'/Shows/{series_id}/Episodes',
            params={
                'seasonId': season_id,
                'userId': self.user_id,
                'fields': 'ProviderIds',
            },
        )
        r.raise_for_status()

        data = r.json()
        return data['Items']

    def merge_episodes(self, episode_ids):
        r = self._post(
            '/Videos/MergeVersions',
            params={
                'Ids': ','.join(episode_ids),
            },
        )
        r.raise_for_status()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--base-url', required=True,
                        help='Jellyfin base URL')
    parser.add_argument('-u', '--username', required=True,
                        help='Jellyfin username')
    parser.add_argument('-k', '--api-key', required=True,
                        help='Jellyfin API key')

    return parser.parse_args()


def main():
    args = parse_args()

    client = JellyfinClient(args.base_url, args.username, args.api_key)

    for series in client.get_series():
        for season in client.get_seasons(series['Id']):
            groups = {}

            for episode in client.get_episodes(series['Id'], season['Id']):
                group_key = (
                    episode['SeriesName'],
                    episode['SeasonName'],
                    episode['Name'],
                    *tuple(sorted(episode['ProviderIds'].items())),
                )

                groups.setdefault(group_key, []).append(episode['Id'])

            for group_key, episode_ids in groups.items():
                if len(episode_ids) > 1:
                    print('Merging:', group_key, '->', episode_ids)
                    client.merge_episodes(episode_ids)


if __name__ == '__main__':
    main()
