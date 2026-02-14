#!/bin/bash

# https://reproducible-builds.org/docs/archives/
exec tar \
    --sort name \
    --mtime @0 \
    --owner 0 \
    --group 0 \
    --numeric-owner \
    --pax-option exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
    -c \
    "${@}"
