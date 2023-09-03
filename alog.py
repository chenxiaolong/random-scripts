#!/usr/bin/env python3

import argparse
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('adb_arg', nargs='*',
                        help='Argument to pass to adb')

    filter = parser.add_mutually_exclusive_group()

    filter.add_argument('-p', '--package', default=[], action='append',
                        help='Filter by package')
    filter.add_argument('-P', '--pid',
                        help='Filter by PID')

    return parser.parse_args()


def main():
    args = parse_args()

    uids = set()

    if args.package:
        packages_raw = subprocess.check_output([
            'adb',
            *args.adb_arg,
            'shell',
            'pm', 'list', 'packages', '-U',
        ])
        package_to_uid = {}

        for line in packages_raw.splitlines():
            package, delim, uid = line.decode('ascii').partition(' ')
            if not delim:
                raise ValueError(f'Bad line: {line!r}')

            package_to_uid[package.removeprefix('package:')] = \
                uid.removeprefix('uid:')

        for package in args.package:
            if package in package_to_uid:
                uids.add(package_to_uid[package])
            else:
                raise ValueError(f'Invalid package: {package}')

    subprocess.check_call([
        'adb',
        *args.adb_arg,
        'logcat',
        '-v', 'color',
        '-v', 'printable',
        '-v', 'time',
        '-v', 'usec',
        '-v', 'year',
        '-v', 'zone',
        *(('--uid', ','.join(uids)) if uids else ()),
        *(('--pid', args.pid) if args.pid else ()),
    ])


if __name__ == '__main__':
    main()
