#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025-2026 Andrew Gunnerson
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import dataclasses
import hashlib
import os
import pathlib
import urllib.parse

import requests


def parse_url(url: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme != 'https' or parsed.netloc != 'github.com':
        raise ValueError(f'Not a GitHub URL: {url}')

    pieces = parsed.path.split('/')

    if len(pieces) < 6 or pieces[0] or pieces[3] != 'actions' or pieces[4] != 'runs':
        raise ValueError(f'Not a GitHub Actions run: {url}')

    return f'{pieces[1]}/{pieces[2]}', int(pieces[5])


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
        help='GitHub repo slug',
    )
    parser.add_argument(
        '-n', '--number',
        type=int,
        help='GitHub Actions build number',
    )
    parser.add_argument(
        '-u', '--url',
        help='GitHub Actions run URL',
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

    args = parser.parse_args()

    has_repo = args.repo is not None
    has_number = args.number is not None
    has_url = args.url is not None

    if not (has_repo and has_number) and not has_url:
        parser.error('Either -u or -r + -n is required')
    elif (has_repo and has_number) == has_url:
        parser.error('-u and -r + -n are mutually exclusive')
    elif has_repo != has_number:
        parser.error('-r and -n must be used together')

    return args


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

    if args.url is not None:
        repo, number = parse_url(args.url)
    else:
        repo = args.repo
        number = args.number

    artifacts = list_artifacts(session, repo, number)

    for artifact in artifacts:
        print('Downloading:', artifact.name)
        download_artifact(session, artifact, args.directory)


if __name__ == '__main__':
    main()
