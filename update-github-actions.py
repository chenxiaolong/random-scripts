#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Andrew Gunnerson
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import pathlib

import requests
import ruamel.yaml
import ruamel.yaml.comments


TAG_CACHE = {}


def get_latest_tag(repo_path: str) -> tuple[str, str]:
    global TAG_CACHE

    if repo_path not in TAG_CACHE:
        r = requests.get(f'https://api.github.com/repos/{repo_path}/releases/latest')
        r.raise_for_status()

        tag_name = r.json()['tag_name']

        r = requests.get(
            f'https://api.github.com/repos/{repo_path}/commits/refs/tags/{tag_name}',
            headers={'Accept': 'application/vnd.github.sha'},
        )

        commit = r.text

        TAG_CACHE[repo_path] = (tag_name, commit)

    return TAG_CACHE[repo_path]


def update_step(step: ruamel.yaml.comments.CommentedMap) -> bool:
    if 'uses' not in step:
        return False

    uses = step['uses']

    action_path, delim, _ = uses.partition('@')
    if not delim:
        # This is a path to a local action.
        return False

    # Everything after the second slash is a directory path.
    repo_path = '/'.join(action_path.split('/')[:2])

    tag, commit = get_latest_tag(repo_path)

    new_uses = f'{action_path}@{commit}'
    if new_uses == uses:
        return False

    print(f'- {uses} -> {new_uses} ({tag})')

    # Trailing newlines and comments are part of the "comment". Only discard the
    # data up until the first newline.
    suffix = ''
    if 'uses' in step.ca.items and step.ca.items['uses'][2]:
        comment = step.ca.items['uses'][2].value
        try:
            newline = comment.index('\n')
            suffix = comment[newline:]
        except ValueError:
            pass

    step['uses'] = new_uses
    step.yaml_add_eol_comment(tag + suffix, 'uses', column=0)

    return True


def update_yaml(path: pathlib.Path):
    print(f'Updating: {path}')

    yaml = ruamel.yaml.YAML(typ='rt')
    yaml.preserve_quotes = True

    with open(path, 'r+b') as f:
        data = yaml.load(f)

        changed = False

        if 'runs' in data:
            for step in data['runs']['steps']:
                changed = changed | update_step(step)
        elif 'jobs' in data:
            for (_, job_data) in data['jobs'].items():
                for step in job_data['steps']:
                    changed = changed | update_step(step)
        else:
            raise ValueError(f'Steps not found: {path}')

        if changed:
            f.seek(0)
            f.truncate(0)

            yaml.width = 2 ** 16
            yaml.indent(mapping=2, sequence=4, offset=2)
            yaml.dump(data, f)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='+', help='Github Actions YAML file')

    return parser.parse_args()


def main():
    args = parse_args()

    for file in args.file:
        update_yaml(file)


if __name__ == '__main__':
    main()
