#!/usr/bin/env python3

# https://github.com/rhboot/shim/blob/main/SBAT.md

import argparse
import dataclasses
import subprocess
import tempfile


@dataclasses.dataclass
class SbatEntry:
    component_name: str
    component_generation: int
    vendor_name: str
    vendor_package_name: str
    vendor_version: str
    vendor_url: str

    def __str__(self):
        return ','.join((
            self.component_name,
            str(self.component_generation),
            self.vendor_name,
            self.vendor_package_name,
            self.vendor_version,
            self.vendor_url,
        )) + '\n'


SBAT_SELF_ENTRY = SbatEntry(
    'sbat',
    1,
    'SBAT Version',
    'sbat',
    '1',
    'https://github.com/rhboot/shim/blob/main/SBAT.md',
)


def positive_int(arg):
    value = int(arg)
    if value <= 0:
        raise ValueError('Value must be positive')

    return value


def ensure_ascii(arg):
    arg.encode('ascii')
    return arg


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--component-name',
        type=ensure_ascii,
        default='bootloader',
        help='SBAT component name',
    )
    parser.add_argument(
        '--component-generation',
        type=positive_int,
        default=1,
        help='SBAT component generation',
    )
    parser.add_argument(
        '--vendor-name',
        type=ensure_ascii,
        default='add-sbat.py',
        help='SBAT vendor name',
    )
    parser.add_argument(
        '--vendor-package-name',
        type=ensure_ascii,
        default='bootloader',
        help='SBAT vendor package name',
    )
    parser.add_argument(
        '--vendor-version',
        type=ensure_ascii,
        default='1',
        help='SBAT vendor version',
    )
    parser.add_argument(
        '--vendor-url',
        type=ensure_ascii,
        default='https://github.com/chenxiaolong/random-scripts',
        help='SBAT vendor URL',
    )
    parser.add_argument(
        'input',
        help='Input file',
    )
    parser.add_argument(
        'output',
        nargs='?',
        help='Output file',
    )

    return parser.parse_args()


def main():
    args = parse_args()
    in_out_args = [args.input]
    if args.output is not None:
        in_out_args.append(args.output)

    sbat_entry = SbatEntry(
        args.component_name,
        args.component_generation,
        args.vendor_name,
        args.vendor_package_name,
        args.vendor_version,
        args.vendor_url,
    )

    with tempfile.NamedTemporaryFile('w', encoding='ascii') as f:
        f.write(str(SBAT_SELF_ENTRY))
        f.write(str(sbat_entry))
        f.flush()

        subprocess.check_call([
            'objcopy',
            '--set-section-alignment',
            '.sbat=512',
            '--add-section',
            f'.sbat={f.name}',
            *in_out_args,
        ])


if __name__ == '__main__':
    main()
