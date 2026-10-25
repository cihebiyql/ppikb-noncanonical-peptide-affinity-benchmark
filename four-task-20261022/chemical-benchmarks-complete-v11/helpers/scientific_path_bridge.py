"""Explicit execution-only path rebinding for immutable scientific input bytes.

This does not rewrite manifests, disable SHA guards or change scientific source.
Only declared original project prefixes map into the supplied recovered tree.
Use in a fresh, single-owner replay process, never a shared interactive runtime.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import threading

_LOCK=threading.RLock()
_ACTIVE=False
ORIGINAL_PREFIXES=(
    '/data/qlyu/projects/peptide-four-task-benchmark-20261022',
    'D:/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022',
)


def mapped_text(raw,destination,prefixes=ORIGINAL_PREFIXES):
    text=os.fspath(raw).replace('\\','/')
    rendered_destination=os.fspath(destination).replace('\\','/').rstrip('/')
    destination=rendered_destination[4:] if rendered_destination.startswith('//?/') else rendered_destination
    if text.startswith('//?/'):text=text[4:]
    if text==destination or text.startswith(destination+'/'):return rendered_destination+text[len(destination):]
    for prefix in prefixes:
        prefix=prefix.replace('\\','/').rstrip('/')
        if text==prefix or text.startswith(prefix+'/'):
            suffix=text[len(prefix):].lstrip('/')
            parts=suffix.split('/') if suffix else []
            if any(part in ('','.','..') or ':' in part for part in parts):raise ValueError('Unsafe original scientific path suffix')
            return rendered_destination+('/'+'/'.join(parts) if parts else '')
    return os.fspath(raw)


@contextmanager
def path_bridge(destination,prefixes=ORIGINAL_PREFIXES):
    global _ACTIVE
    with _LOCK:
        if _ACTIVE:raise RuntimeError('Nested/global concurrent path bridges are forbidden')
        destination=Path(destination).resolve()
        if any(str(destination).replace('\\','/').rstrip('/')==x.replace('\\','/').rstrip('/') for x in prefixes):raise ValueError('Use a fresh recovery tree, not the original scientific project')
        original_descriptor=Path.__dict__['__new__'];original_new=Path.__new__
        def bridged_new(cls,*args,**kwargs):
            if args and isinstance(args[0],(str,os.PathLike)):
                first=mapped_text(args[0],destination,prefixes)
                args=(first,)+args[1:]
            return original_new(cls,*args,**kwargs)
        Path.__new__=staticmethod(bridged_new)
        _ACTIVE=True
        try:yield
        finally:
            Path.__new__=original_descriptor
            _ACTIVE=False


def main():
    import argparse,runpy,sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--script',required=True,help='Project-relative self-authored script; explicitly executes it')
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    relative=args.script.replace('\\','/').split('/')
    if any(x in ('','.','..') or ':' in x for x in relative):raise ValueError('Unsafe script path')
    raw_root=os.path.abspath(os.fspath(args.project))
    if os.name=='nt' and not raw_root.startswith('\\\\?\\'):raw_root='\\\\?\\'+raw_root
    root=Path(raw_root).resolve();script=root.joinpath(*relative)
    if not script.resolve().is_relative_to(root) or script.is_symlink():raise ValueError('Script must stay inside recovered project')
    sys.argv=[str(script)]+(args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments)
    with path_bridge(root):runpy.run_path(str(script),run_name='__main__')


if __name__=='__main__':main()
