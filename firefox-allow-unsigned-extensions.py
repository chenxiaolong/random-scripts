#!/usr/bin/env python3

import argparse
import contextlib
import os
import re
import shutil
import tempfile
import zipfile


@contextlib.contextmanager
def open_output_file(path):
    directory = os.path.dirname(path)

    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as f:
        try:
            yield f
            os.rename(f.name, path)
        except BaseException:
            os.unlink(f.name)
            raise


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Path to omni.ja')
    parser.add_argument('-o', '--output', help='Path to patched omni.ja')

    args = parser.parse_args()

    if args.output is None:
        args.output = args.input

    return args


def main():
    args = parse_args()
    found_app_constants = True

    with (
        zipfile.ZipFile(args.input, 'r') as z_in,
        open_output_file(args.output) as fz_out,
        zipfile.ZipFile(fz_out, 'w') as z_out,
    ):
        for info in z_in.infolist():
            with (
                z_in.open(info, 'r') as f_in,
                z_out.open(info, 'w') as f_out,
            ):
                if os.path.basename(info.filename).startswith('AppConstants.'):
                    found_app_constants = True
                    data = f_in.read()

                    new_data = re.sub(
                        b'(MOZ_REQUIRE_SIGNING:\\s*)true',
                        b'\\1false',
                        data,
                    )

                    if new_data == data:
                        raise ValueError('MOZ_REQUIRE_SIGNING did not change')

                    f_out.write(new_data)

                else:
                    shutil.copyfileobj(f_in, f_out)

    if not found_app_constants:
        raise ValueError('AppConstants file not found')


if __name__ == '__main__':
    main()
