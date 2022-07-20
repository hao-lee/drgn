# Copyright (c) Meta Platforms, Inc. and affiliates.
# SPDX-License-Identifier: GPL-3.0-or-later

"""
BPF
---

The ``drgn.helpers.linux.bpf`` module provides helpers for working with BPF
interface in :linux:`include/linux/bpf.h`, :linux:`include/linux/bpf-cgroup.h`,
etc.
"""


import itertools
from typing import Iterator

from drgn import IntegerLike, Object, Program, cast
from drgn.helpers.linux.idr import idr_for_each
from drgn.helpers.linux.list import list_for_each_entry

__all__ = (
    "bpf_map_for_each",
    "bpf_prog_for_each",
    "cgroup_bpf_prog_for_each",
    "cgroup_bpf_prog_for_each_effective",
)


def bpf_map_for_each(prog: Program) -> Iterator[Object]:
    """
    Iterate over all BPF maps.

    This is only supported since Linux v4.13.

    :return: Iterator of ``struct bpf_map *`` objects.
    """
    type = prog.type("struct bpf_map *")
    # map_idr didn't exist before Linux kernel commit f3f1c054c288 ("bpf:
    # Introduce bpf_map ID") (in v4.13).
    for nr, entry in idr_for_each(prog["map_idr"]):
        yield cast(type, entry)


def bpf_prog_for_each(prog: Program) -> Iterator[Object]:
    """
    Iterate over all BPF programs.

    This is only supported since Linux v4.13.

    :return: Iterator of ``struct bpf_prog *`` objects.
    """
    type = prog.type("struct bpf_prog *")
    # prog_idr didn't exist before Linux kernel commit dc4bb0e23561 ("bpf:
    # Introduce bpf_prog ID") (in v4.13).
    for nr, entry in idr_for_each(prog["prog_idr"]):
        yield cast(type, entry)


def cgroup_bpf_prog_for_each(
    cgrp: Object, bpf_attach_type: IntegerLike
) -> Iterator[Object]:
    """
    Iterate over all cgroup BPF programs of the given attach type attached to
    the given cgroup.

    :param cgrp: ``struct cgroup *``
    :param bpf_attach_type: ``enum bpf_attach_type``
    :return: Iterator of ``struct bpf_prog *`` objects.
    """
    # Before Linux kernel commit 3007098494be ("cgroup: add support for eBPF
    # programs") (in v4.10), struct cgroup::bpf didn't exist because cgroup BPF
    # programs didn't exist.
    try:
        cgrp_bpf = cgrp.bpf
    except AttributeError:
        return
    # Since Linux kernel commit 324bda9e6c5a ("bpf: multi program support for
    # cgroup+bpf") (in v4.15), the attached programs are stored in an array of
    # lists, struct cgroup_bpf::progs. Before that, only one program of each
    # attach type could be attached to a cgroup, so the attached programs are
    # stored in an array of struct bpf_prog *, struct cgroup_bpf::prog.
    try:
        progs = cgrp_bpf.progs
    except AttributeError:
        # If the kernel was not configured with CONFIG_CGROUP_BPF, then struct
        # cgroup_bpf is an empty structure.
        try:
            prog = cgrp_bpf.prog[bpf_attach_type]
        except AttributeError:
            return
        if prog:
            yield prog
    else:
        for pl in list_for_each_entry(
            "struct bpf_prog_list", progs[bpf_attach_type].address_of_(), "node"
        ):
            yield pl.prog


def cgroup_bpf_prog_for_each_effective(
    cgrp: Object, bpf_attach_type: IntegerLike
) -> Iterator[Object]:
    """
    Iterate over all effective cgroup BPF programs of the given attach type for
    the given cgroup.

    :param cgrp: ``struct cgroup *``
    :param bpf_attach_type: ``enum bpf_attach_type``
    :return: Iterator of ``struct bpf_prog *`` objects.
    """
    # Before Linux kernel commit 3007098494be ("cgroup: add support for eBPF
    # programs") (in v4.10), struct cgroup::bpf didn't exist because cgroup BPF
    # programs didn't exist. Since then, if the kernel was not configured with
    # CONFIG_CGROUP_BPF, then struct cgroup_bpf is an empty structure.
    try:
        effective = cgrp.bpf.effective[bpf_attach_type]
    except AttributeError:
        return
    # Since Linux kernel commit 324bda9e6c5a ("bpf: multi program support for
    # cgroup+bpf") (in v4.15), struct cgroup_bpf::effective is an array of
    # struct bpf_prog_array. Before that, only one program of each attach type
    # could be effective for a cgroup, so struct cgroup_bpf::effective is an
    # array of struct bpf_prog *.
    try:
        effective_items = effective.items
    except AttributeError:
        if effective:
            yield effective
    else:
        for i in itertools.count():
            prog = effective_items[i].prog.read_()
            if not prog:
                break
            yield prog
