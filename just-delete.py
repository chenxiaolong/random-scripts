#!/usr/bin/env python3

# A tool that's like `rm`, except it chmod's the relevent path or parent path to
# allow things to be deleted when EPERM is encountered. It tries to make as few
# I/O syscalls as possible and aims to be as safe as possible in the face of
# external processes messing with the paths being deleted. Arbitrary non-UTF-8
# paths are supported.

import argparse
import dataclasses
import os
import stat
import sys


def log(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)


def printable_path(parent_name: bytes, child_name: bytes) -> str:
    return os.fsdecode(os.path.join(parent_name, child_name))


def log_error(
    message: str,
    parent_name: bytes,
    child_name: bytes,
    exception: Exception,
):
    path = printable_path(parent_name, child_name)
    # Using repr() for the path to avoid multiline output.
    log(f'{message}: {path!r}: {exception}')


# We don't do writes, so close() failures don't matter.
def close_quietly(fd: int):
    try:
        os.close(fd)
    except OSError:
        pass


@dataclasses.dataclass
class ParentContext:
    name: bytes
    fd: int
    # chmod is attempted if a child cannot be deleted.
    attempted_chmod: bool = False


@dataclasses.dataclass
class ChildContext:
    name: bytes
    is_dir: bool
    # chmod is attempted if this path is a directory that cannot be opened.
    attempted_chmod: bool = False


# Open the child, retrying after making it writable if needed. Returns the
# read-only file descriptor. This function is symlink-safe, but may chmod a
# different file than what is opened if another process meddles with the parent
# directory during execution. If chmod was already attempted once for the child,
# it will not be attempted again.
def open_with_chmod(parent: ParentContext, child: ChildContext) -> int:
    for _attempt in range(0, 2):
        try:
            dir_fd = os.open(child.name, os.O_RDONLY, dir_fd=parent.fd)
            break
        except PermissionError as e:
            if child.attempted_chmod:
                raise e
            child.attempted_chmod = True

            try:
                child_stat = os.lstat(child.name, dir_fd=parent.fd)
                child_mode = stat.S_IMODE(child_stat.st_mode) | stat.S_IWUSR
                os.chmod(child.name, child_mode, dir_fd=parent.fd)
            except OSError as chmod_e:
                log_error('Failed to make writable', parent.name, child.name, chmod_e)
                raise e

    return dir_fd  # pyright: ignore[reportPossiblyUnboundVariable]


# Delete a single path using unlink or rmdir depending on the child file type.
def delete_single(parent: ParentContext, child: ChildContext):
    if child.is_dir:
        os.rmdir(child.name, dir_fd=parent.fd)
    else:
        os.unlink(child.name, dir_fd=parent.fd)


# Delete the path if it exists, retrying after making the parent writable if
# needed. This function is safe in the face of another process meddling with
# the parent directory. If chmod was already attempted once for the parent, it
# will not be attempted again.
def delete_single_with_chmod(
    parent: ParentContext,
    child: ChildContext,
    force: bool,
    verbose: bool,
) -> None:
    for _attempt in range(0, 2):
        try:
            delete_single(parent, child)

            if verbose:
                log(printable_path(parent.name, child.name))

            break
        except FileNotFoundError as e:
            if force:
                break
            else:
                raise e
        except PermissionError as e:
            if parent.attempted_chmod:
                raise e
            parent.attempted_chmod = True

            # Try to make parent directory writable.
            try:
                parent_stat = os.fstat(parent.fd)
                parent_mode = stat.S_IMODE(parent_stat.st_mode) | stat.S_IWUSR
                os.fchmod(parent.fd, parent_mode)
            except OSError as chmod_e:
                log_error('Failed to make writable', parent.name, b'', chmod_e)
                raise e


# Delete a path, optionally recursively. Attempts to chmod if deletion or
# directory iteration is not permitted.
def delete_path(
    parent: ParentContext,
    child: ChildContext,
    force: bool,
    recursive: bool,
    verbose: bool,
) -> bool:
    try:
        delete_single_with_chmod(parent, child, force, verbose)
        return True
    except OSError as e:
        if not recursive or not child.is_dir:
            log_error('Failed to delete', parent.name, child.name, e)
            return False

    # We intentionally do not use os.fwalk() because there's no way to chmod and
    # retry when a directory cannot be opened.
    try:
        try:
            dir_fd = open_with_chmod(parent, child)
        except FileNotFoundError as e:
            if force:
                return True
            else:
                raise e
    except OSError as e:
        log_error('Failed to open', parent.name, child.name, e)
        return False

    success = True

    try:
        with os.scandir(dir_fd) as dir:
            dir_name = os.path.join(parent.name, child.name)

            # parent + child, as a pair, refers to the path that were deleting.
            # entry refers to children of *that*.
            for entry in dir:
                dir_context = ParentContext(
                    dir_name,
                    dir_fd,
                    child.attempted_chmod,
                )
                entry_is_dir = entry.is_dir(follow_symlinks=False)

                success &= delete_path(
                    dir_context,
                    ChildContext(os.fsencode(entry.name), entry_is_dir),
                    force,
                    entry_is_dir,
                    verbose,
                )

                child.attempted_chmod |= dir_context.attempted_chmod
    except OSError as e:
        log_error('Failed to read', parent.name, child.name, e)
        return False
    finally:
        close_quietly(dir_fd)

    # Try to delete, even if we couldn't delete the children. An external
    # process may have done it for us.
    try:
        delete_single_with_chmod(parent, child, force, verbose)
    except OSError as e:
        log_error('Failed to delete', parent.name, child.name, e)
        return False

    return success


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Ignore non-existent paths',
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Delete recursively',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print paths during deletion',
    )
    parser.add_argument(
        'path',
        # For non-UTF-8 paths.
        type=os.fsencode,
        nargs='+',
        help='Path to delete',
    )

    return parser.parse_args()


def main():
    args = parse_args()

    success = True

    for path in args.path:
        try:
            try:
                path = os.path.realpath(path, strict=True)

                parent_name, child_name = os.path.split(path)
                assert parent_name
                # To handle `/`, if the user insists on wrecking their system.
                child_name = child_name or b'.'

                parent_fd = os.open(parent_name, os.O_RDONLY)
            except FileNotFoundError as e:
                if args.force:
                    continue
                else:
                    raise e
        except OSError as e:
            log_error('Failed to find', path, b'', e)
            success = False
            continue

        try:
            try:
                child_stat = os.lstat(path=child_name, dir_fd=parent_fd)
                child_is_dir = stat.S_ISDIR(child_stat.st_mode)
            except OSError as e:
                log_error('Failed to stat', parent_name, child_name, e)
                success = False
                continue

            success &= delete_path(
                ParentContext(parent_name, parent_fd),
                ChildContext(child_name, child_is_dir),
                args.force,
                args.recursive,
                args.verbose,
            )
        finally:
            close_quietly(parent_fd)

    if not success:
        exit(1)


if __name__ == '__main__':
    main()
