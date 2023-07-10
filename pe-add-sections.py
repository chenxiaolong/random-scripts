#!/usr/bin/env python3

# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; If not, see <https://www.gnu.org/licenses/>.

# ------------------------------------------------------------------------------

# Unlike the rest of the repo, this script is licensed under the terms above
# since it contains code from systemd's ukify script (specifically, parts of
# pe_add_sections()).

# ------------------------------------------------------------------------------

# Usage:
#
# To add a new section containing data from a file `data.bin`:
#   ./pe-add-sections.py -s .foobar data.bin -i in.efi -o out.efi
#
# To add a new section with a NULL-terminator (eg. for .sbat):
#   ./pe-add-sections.py -s .sbat sbat.csv -z .sbat -i in.efi -o out.efi
#
# To add multiple sections, pass in `-s` multiple times. The order given on the
# command line is the order that the sections are added to the file. To modify
# a file in place, leave out `-o`.
#
# Modifying signed executables or executables that already contain the
# specified sections is not supported.

import argparse

import pefile


def align_to(value, page_size):
    if page_size.bit_count() != 1:
        raise ValueError(f'Page size is not a power of 2: {page_size}')

    return (value + page_size - 1) // page_size * page_size


# Mostly based on systemd's ukify logic
def pe_add_sections(input: str, output: str, sections: dict[str, bytes]):
    pe = pefile.PE(input, fast_load=True)

    for s in pe.sections:
        if (name := s.Name.rstrip(b"\x00").decode('ascii')) in sections.keys():
            raise ValueError(f'Section {name} already exists')

    security = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
        pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_SECURITY']]
    if security.VirtualAddress != 0:
        raise ValueError('Cannot modify signed file')

    # Try to make room for the new headers by eating into the existing padding
    pe.OPTIONAL_HEADER.SizeOfHeaders = align_to(
        pe.OPTIONAL_HEADER.SizeOfHeaders,
        pe.OPTIONAL_HEADER.FileAlignment,
    )
    pe = pefile.PE(data=pe.write(), fast_load=True)

    warnings = pe.get_warnings()
    if warnings:
        raise Exception(f'Warnings when adjusting size of headers: {warnings}')

    for name, data in sections.items():
        new_section = pefile.SectionStructure(
            pe.__IMAGE_SECTION_HEADER_format__, pe=pe)
        new_section.__unpack__(b'\0' * new_section.sizeof())

        offset = pe.sections[-1].get_file_offset() + pe.sections[-1].sizeof()
        if offset + new_section.sizeof() > pe.OPTIONAL_HEADER.SizeOfHeaders:
            raise Exception(f'Not enough header space for {name}')

        new_section.set_file_offset(offset)
        new_section.Name = name.encode('ascii')
        new_section.Misc_VirtualSize = len(data)
        # Start at previous EOF + padding for alignment
        new_section.PointerToRawData = align_to(
            len(pe.__data__),
            pe.OPTIONAL_HEADER.FileAlignment,
        )
        new_section.SizeOfRawData = align_to(
            len(data),
            pe.OPTIONAL_HEADER.FileAlignment,
        )
        new_section.VirtualAddress = align_to(
            pe.sections[-1].VirtualAddress + pe.sections[-1].Misc_VirtualSize,
            pe.OPTIONAL_HEADER.SectionAlignment,
        )

        new_section.IMAGE_SCN_MEM_READ = True
        new_section.IMAGE_SCN_CNT_INITIALIZED_DATA = True

        # Append:
        # - Padding from previous EOF to new aligned section
        # - New section data
        # - Padding from end of section to EOF
        pe.__data__ = pe.__data__[:] \
            + bytes(new_section.PointerToRawData - len(pe.__data__)) \
            + data \
            + bytes(new_section.SizeOfRawData - len(data))

        pe.FILE_HEADER.NumberOfSections += 1
        pe.OPTIONAL_HEADER.SizeOfInitializedData += \
            new_section.Misc_VirtualSize
        pe.__structures__.append(new_section)
        pe.sections.append(new_section)

    pe.OPTIONAL_HEADER.CheckSum = 0
    pe.OPTIONAL_HEADER.SizeOfImage = align_to(
        pe.sections[-1].VirtualAddress + pe.sections[-1].Misc_VirtualSize,
        pe.OPTIONAL_HEADER.SectionAlignment,
    )

    pe.write(output)


class UniqueKeyValuePairAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs != 2:
            raise ValueError('nargs must be 2')

        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        data = getattr(namespace, self.dest, None)
        if data is None:
            data = {}

        if values[0] in data:
            raise ValueError(f'Duplicate key: {values[0]}')

        data[values[0]] = values[1]
        setattr(namespace, self.dest, data)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s', '--section',
        nargs=2,
        metavar=('SECTION_NAME', 'FILENAME'),
        action=UniqueKeyValuePairAction,
        required=True,
        help='Add section',
    )
    parser.add_argument(
        '-z', '--null-terminate',
        metavar='SECTION_NAME',
        default=[],
        action='append',
        help='NULL-terminate the data for a specific section',
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input PE file',
    )
    parser.add_argument(
        '-o', '--output',
        help='Output PE file (same as input if unspecified)',
    )

    args = parser.parse_args()

    if args.output is None:
        args.output = args.input

    args.null_terminate = set(args.null_terminate)

    for name in args.section.keys() | args.null_terminate:
        try:
            name.encode('ascii')
        except UnicodeEncodeError:
            parser.error(f'Section name must be ASCII only: {name!r}')

    missing = args.null_terminate - args.section.keys()
    if missing:
        parser.error(f'Cannot NULL-terminate missing sections: {missing}')

    return args


def main():
    args = parse_args()

    sections = {}

    for name, path in args.section.items():
        with open(path, 'rb') as f:
            data = f.read()

        if name in args.null_terminate:
            data += b'\0'

        sections[name] = data

    pe_add_sections(
        args.input,
        args.input if args.output is None else args.output,
        sections,
    )


if __name__ == '__main__':
    main()
