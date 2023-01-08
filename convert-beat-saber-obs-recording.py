#!/usr/bin/env python3

import argparse
import os
import re
import subprocess

import requests


BEATSAVER_HEADERS = {
    'User-Agent': 'convert-beat-saber-obs-recording/0.0 (https://github.com/chenxiaolong/random-scripts/blob/master/convert-beat-saber-obs-recording.py)',
}

RE_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RE_HOUR = re.compile(r'^\d{2}$')
RE_BSR_ID = re.compile(r'^[0-9a-fA-F]+$')
RE_DIFFICULTY = re.compile(r'^(((90|360)°|Lawless|Lightshow|No Arrows|One Handed) )?(Easy|Normal|Hard|Expert\+?)$')
RE_RANK = re.compile(r'^([A-F]|S{1,3})$')
# Modifiers
# - Score-impacting modifiers:
#   - DA - Disappearing Arrows
#   - FS - Faster Song
#   - GN - Ghost Notes
#   - NA - No Arrows
#   - NB - No Bombs
#   - NW - No Walls
#   - SFS - Super Fast Song
#   - SS - Slower Song
# - Sometimes score-impacting modifiers
#   - NF - No Fail TODO
# - Non-score-impacting modifiers:
#   - 1L - 1 Life
#   - 4L - 4 Lives
#   - SA - Strict Angles
#   - SN - Small Notes
#   - PM - Pro Mode
#   - ZM - Zen Mode
# - Player settings:
#   - LH - Left Handed
#   - SL - Static Lights
RE_MODIFIER = re.compile(r'^([14]L|DA|FS|GN|LH|N[ABFW]|PM|S([ALNS]|FS)|ZM)$')
RE_OBS_FILENAME = re.compile(r'^(\d{4}-\d{2}-\d{2})\s*-?\s*(\d{2})')
RE_TRIMMABLE = re.compile(r'^(?:\(.*\)|\[.*\]|\{.*\}|【.*】)$')


def valid_on_win_fs(c):
    return c not in ('<', '>', ':', '"', '/', '\\', '|', '?', '*') \
        and ord(c) >= 32


def same_file(path1, path2):
    try:
        stat1 = os.stat(path1)
        stat2 = os.stat(path2)

        return stat1.st_dev == stat2.st_dev and stat1.st_ino == stat2.st_ino
    except FileNotFoundError:
        return False


def trim_name(s):
    if s:
        s = s.strip()

        while True:
            m = RE_TRIMMABLE.match(s)
            if m:
                s = s[1:-1].strip()
            else:
                break

    return s


def regex_arg(pattern):
    def validate(value):
        if not pattern.match(value):
            raise argparse.ArgumentTypeError(f'Does not match {pattern}')

        return value

    return validate


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('input',
                        help='Input file')
    parser.add_argument('-o', '--output',
                        help='Output file (default: autodetect)')
    parser.add_argument('--output-dir', default='.',
                        help='Output directory (default: .)')
    parser.add_argument('-s', '--start', required=True,
                        help='Starting timestamp')
    parser.add_argument('-e', '--end',
                        help='Ending timestamp')
    parser.add_argument('--date', type=regex_arg(RE_DATE),
                        help='Recording date (default: guess from filename)')
    parser.add_argument('--hour', type=regex_arg(RE_HOUR),
                        help='Recording hour (default: guess from filename)')
    parser.add_argument('-b', '--bsr-id', type=regex_arg(RE_BSR_ID),
                        help='BeatSaver ID'),
    parser.add_argument('--artist',
                        help='Song artist')
    parser.add_argument('--mapper',
                        help='Level mapper')
    parser.add_argument('--song',
                        help='Song name')
    parser.add_argument('-d', '--difficulty', type=regex_arg(RE_DIFFICULTY),
                        help='Level difficulty')
    parser.add_argument('-m', '--misses', type=int,
                        help='Number of misses')
    parser.add_argument('-n', '--no-fc', action='store_true',
                        help='No full combo (for when --misses 0)')
    parser.add_argument('-r', '--rank', type=regex_arg(RE_RANK),
                        help='Score rank')
    parser.add_argument('--modifier', type=regex_arg(RE_MODIFIER),
                        action='append',
                        help='Level modifier')
    parser.add_argument('-c', '--comment',
                        help='Arbitrary comment')

    args = parser.parse_args()

    conflict_with_output = [
        args.output_dir, # '.', not None
        args.date,
        args.hour,
        args.bsr_id,
        args.artist,
        args.mapper,
        args.song,
        args.difficulty,
        args.misses,
        args.no_fc, # False, not None
        args.rank,
        args.modifier,
        args.comment,
    ]

    mandatory_without_output = [
        args.difficulty,
        args.misses,
        args.rank,
    ]

    conflict_with_bsr_id = [
        args.artist,
        args.mapper,
        args.song,
    ]

    mandatory_without_bsr_id = [
        args.song,
    ]

    if args.output is not None:
        if any(a not in (None, False, '.') for a in conflict_with_output):
            parser.error('--output cannot be used with other filename arguments')
    else:
        if any(a is None for a in mandatory_without_output):
            parser.error('--difficulty, --misses, and --rank are required when --output is specified')

        if args.bsr_id is not None:
            if any(a is not None for a in conflict_with_bsr_id):
                parser.error('--bsr-id cannot be used with --artist, --mapper, or --song')
        else:
            if any(a is None for a in mandatory_without_bsr_id):
                parser.error('--song is required when --bsr-id is not specified')

        if args.no_fc and args.misses != 0:
            parser.error('--no-fc can only be used when --misses 0 is specified')

    return args


def main():
    args = parse_args()

    if args.output is None:
        base_name = os.path.basename(args.input)

        m = RE_OBS_FILENAME.match(base_name)
        if m:
            args.date = m.group(1)
            args.time = m.group(2)

        if args.date is None or args.time is None:
            raise Exception('Date or time not provided and could not be determined from input filename')

        if args.bsr_id:
            r = requests.get(f'https://beatsaver.com/api/maps/id/{args.bsr_id}',
                             headers=BEATSAVER_HEADERS)
            r.raise_for_status()

            data = r.json()

            args.song = trim_name(data['metadata']['songName'])
            sub_name = trim_name(data['metadata']['songSubName'])
            if sub_name:
                args.song += f' ({sub_name})'

            args.artist = trim_name(data['metadata']['songAuthorName'])
            args.mapper = trim_name(data['metadata']['levelAuthorName'])

        components = [args.date, args.time]

        artist_components = []
        if args.artist:
            artist_components.append(args.artist)
        if args.mapper:
            artist_components.append(f'[{args.mapper}]')
        if artist_components:
            components.append(' '.join(artist_components))

        components.append(args.song)
        components.append(args.difficulty)

        if args.modifier:
            components.append(', '.join(sorted(args.modifier)))

        if args.misses < 0:
            misses = 'Failed'
        elif args.misses == 0 and not args.no_fc:
            misses = 'Full Combo'
        elif args.misses == 1:
            misses = '1 miss'
        else:
            misses = f'{args.misses} misses'

        components.append(misses)
        components.append(args.rank)

        if args.comment:
            components.append(args.comment)

        filename = ' - '.join(components)
        args.output = ''.join(c if valid_on_win_fs(c) else '_' for c in filename) + '.mkv'

    if same_file(args.input, args.output):
        raise Exception('Input and output paths are the same')

    timestamp_args = ['-ss', args.start]
    if args.end is not None:
        timestamp_args.append('-to')
        timestamp_args.append(args.end)

    subprocess.check_call([
        'ffmpeg',
        *timestamp_args,
        '-i', args.input,
        '-c', 'copy',
        '-avoid_negative_ts', '1',
        args.output,
    ])


if __name__ == '__main__':
    main()
