"""Index-independent comparison with every immutable historical native Git blob.

Uses ls-tree/cat-file rather than archive: export-ignore/export-subst and
refs/replace cannot alter the reviewed object inventory or delivered bytes.
This is Git content consistency, not authentication of the original editor.
"""
from __future__ import annotations
from pathlib import Path
from git_object_integrity import verify_worktree_blobs
NATIVE_FOLDERS=("profiles/gentle-shell","profiles/omp",
                "profiles/gentle-shell-variants/critical-review")
EXPECTED_COUNT=3744

def verify_native_blobs(root:Path,anchor:str)->dict:
    proof=verify_worktree_blobs(root,anchor,NATIVE_FOLDERS,
                                required_count=EXPECTED_COUNT)
    return {"nativeFilesComparedDirectlyToGitBlobs":proof["trackedGitBlobsCompared"],
            "historicalNativeCommit":anchor,"usesGitIndex":False,
            "usesGitArchive":False,"objectHashesVerified":True,
            "exportAttributesIgnored":True,
            "gitReplaceObjectsDisabled":True,
            "authentication":"not-a-signature"}
