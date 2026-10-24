"""Fixed audit-reference commits, outside the self-reissued metadata receipt.

This is a *Git history consistency check*, not a digital signature or proof
of publisher identity. Changes to this code or the trusted refs need an
independent code review and a protected release workflow.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
from git_object_integrity import git_bytes,read_committed_blob

# Approved historical commits (different Git histories; never import private
# Git data into the public edition). Review any change to either constant.
PRIVATE_BEFORE_LABELS='' # Public distribution contains no private Git revision identifier.
PUBLIC_BEFORE_LABELS='4bbcf2e962ff2630a1c1c0064d7c74ba8ebba26a'
PUBLIC_BFCL_APPROVED='691bfc8c6088371b83de223ff4b437da98827327'
PUBLIC_BFCL_ROWS_SHA256='c806614ac8819c256b15d9354538d8cd51f339569264159f548ddd860de7be5d'

def git(root: Path,*args: str) -> bytes:
    return git_bytes(root,*args)

def reviewed_anchor(root: Path) -> tuple[str,str]:
    root=root.resolve()
    try:
        actual=Path(git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()
    except (subprocess.CalledProcessError,ValueError,OSError) as e:
        raise ValueError('Full Git history is required to verify historical source provenance') from e
    if actual!=root: raise ValueError('Historical attestation root must be a standalone repository')
    for edition,pin in [('private',PRIVATE_BEFORE_LABELS),('public',PUBLIC_BEFORE_LABELS)]:
        if not pin:continue
        try:
            if git(root,'cat-file','-t',pin).decode().strip()!='commit':continue
            git(root,'merge-base','--is-ancestor',pin,'HEAD')
            return edition,pin
        except (subprocess.CalledProcessError,ValueError):continue
    raise ValueError('Approved historic commit not found as ancestor; shallow/untrusted history refused')

def reviewed_blob(root: Path, ref: str, relative: str) -> bytes:
    # Relative filenames come from a fixed list, not untrusted manifest entries.
    if relative.startswith('/') or '..' in Path(relative).parts or '\\' in relative:
        raise ValueError('Unsafe historical pathname')
    return read_committed_blob(root,ref,relative)
