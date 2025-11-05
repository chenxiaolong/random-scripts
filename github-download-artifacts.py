#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Andrew Gunnerson
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import dataclasses
import functools
import hashlib
import os
import pathlib
import typing

import requests


@dataclasses.dataclass
class Artifact:
    name: str
    url: str
    digest_type: str
    digest: bytes


def list_artifacts(
    session: requests.Session,
    repo: str,
    number: int,
) -> list[Artifact]:
    url = f'https://api.github.com/repos/{repo}/actions/runs/{number}/artifacts?per_page=1' # TODO
    artifacts = []

    while url:
        r = session.get(url)
        r.raise_for_status()

        for artifact in r.json()['artifacts']:
            digest_type, delim, digest = artifact['digest'].partition(':')
            if not delim:
                raise ValueError(f'Invalid digest field: {artifact['digest']}')

            artifacts.append(Artifact(
                name=artifact['name'],
                url=artifact['archive_download_url'],
                digest_type=digest_type,
                digest=bytes.fromhex(digest),
            ))

        url = r.links.get('next', {}).get('url')

    return artifacts


def download_artifact(
    session: requests.Session,
    artifact: Artifact,
    dir: pathlib.Path,
):
    if pathlib.Path(artifact.name).name != artifact.name \
            or artifact.name in ('', '.', '..'):
        raise ValueError(f'Unsafe filename: {artifact.name!r}')

    with session.get(artifact.url, stream=True) as r:
        r.raise_for_status()

        with open(dir / f'{artifact.name}.zip', 'wb') as f:
            match artifact.digest_type:
                case 'sha256':
                    hasher = hashlib.sha256()
                case t:
                    raise ValueError(f'Unsupported digest type: {t!r}')

            for chunk in r.iter_content(None):
                hasher.update(chunk)
                f.write(chunk)

            digest = hasher.digest()

            if digest != artifact.digest:
                raise ValueError(f'Expected {artifact.digest_type} {artifact.digest.hex()}, but have {digest.hex()}')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-r', '--repo',
        required=True,
        help='GitHub repo slug',
    )
    parser.add_argument(
        '-n', '--number',
        required=True,
        type=int,
        help='Github Actions build number',
    )
    parser.add_argument(
        '-d', '--directory',
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help='Output directory',
    )

    token_group = parser.add_mutually_exclusive_group(required=True)
    token_group.add_argument(
        '-t', '--token-file',
        help='File containing Github token',
    )
    token_group.add_argument(
        '-T', '--token-env',
        help='Environment variable containing Github token',
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.token_file:
        with open(args.token_file, 'r') as f:
            token = f.read().strip()
    elif args.token_env:
        token = os.environ[args.token_env].strip()
    else:
        assert False

    session = requests.Session()
    session.headers['Authorization'] = f'Bearer {token}'

    artifacts = list_artifacts(session, args.repo, args.number)

    for artifact in artifacts:
        print('Downloading:', artifact.name)
        download_artifact(session, artifact, args.directory)


if __name__ == '__main__':
    main()
