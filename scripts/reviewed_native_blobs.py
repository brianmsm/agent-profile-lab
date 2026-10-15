"""Compare each native worktree byte directly with the approved Git tree.

Does NOT consult Git's index/diff or receipt-issued digests for originality.
These are historical Git consistency checks, not a publisher signature.
"""
from __future__ import annotations
import subprocess,tarfile
from pathlib import Path

NATIVE_FOLDERS=('profiles/gentle-shell','profiles/omp',
                'profiles/gentle-shell-variants/critical-review')
EXPECTED_COUNT=3744

def verify_native_blobs(root:Path, anchor:str) -> dict:
    root=root.resolve()
    expected={p.relative_to(root).as_posix() for name in NATIVE_FOLDERS
              for p in (root/name).iterdir() if p.is_file() or p.is_symlink()}
    if len(expected)!=EXPECTED_COUNT:
        raise ValueError(f'Native worktree inventory differs: {len(expected)}')
    seen=set()
    archive=subprocess.Popen(
        ['git','-C',str(root),'archive','--format=tar',anchor,'--',*NATIVE_FOLDERS],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert archive.stdout is not None
        with tarfile.open(fileobj=archive.stdout,mode='r|') as contents:
            for member in contents:
                if member.isdir():continue
                rel=member.name.rstrip('/')
                if (not member.isfile() or rel not in expected or rel in seen
                    or member.size>4_000_000):
                    raise ValueError('Unapproved native Git blob type, size or path: '+rel)
                path=root/rel
                if (path.is_symlink() or not path.is_file()
                        or not path.resolve().is_relative_to(root)
                        or path.stat().st_size!=member.size):
                    raise ValueError('Historical native worktree file invalid: '+rel)
                stream=contents.extractfile(member)
                if stream is None or path.read_bytes()!=stream.read():
                    raise ValueError('Native worktree differs from immutable historic Git blob: '+rel)
                seen.add(rel)
        if seen!=expected or len(seen)!=EXPECTED_COUNT:
            raise ValueError(f'Native historical inventory differs: actual={len(seen)} expected={len(expected)}')
        archive.stdout.close()
        result=archive.wait(timeout=15)
        if result:
            raise ValueError('Unable to verify approved historical native archive')
    finally:
        if archive.poll() is None:
            archive.kill()
        if archive.stdout:archive.stdout.close()
        if archive.stderr:archive.stderr.close()
        archive.wait()
    return {'nativeFilesComparedDirectlyToGitBlobs':len(seen),
            'historicalNativeCommit':anchor,
            'usesGitIndex':False,'authentication':'not-a-signature'}
