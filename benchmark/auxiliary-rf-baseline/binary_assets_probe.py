"""Supplement Python source facts with actual installed compiled dependency SHA."""
from pathlib import Path
import inspect
import importlib.metadata
import json
import shutil
import common
def main():
    import sklearn.tree._tree as tree
    import sklearn.tree._splitter as splitter
    import sklearn.tree._criterion as criterion
    import sklearn.ensemble._forest as forest
    binaries={name:dict(path=str(module.__file__),sha256=common.sha(module.__file__))
              for name,module in [('tree',tree),('splitter',splitter),('criterion',criterion)]}
    licenses=[]
    distribution=importlib.metadata.distribution('scikit-learn')
    dest=common.HERE/'assets/sklearn-licenses';dest.mkdir(exist_ok=False)
    for file in distribution.files or []:
        if 'licenses' in str(file).lower() and Path(str(file)).name.upper().startswith(('LICENSE','COPYING')):
            source=distribution.locate_file(file);target=dest/Path(str(file)).name
            if target.exists():target=dest/(str(len(licenses))+'-'+target.name)
            shutil.copy2(source,target);licenses.append(dict(source=str(source),frozen=str(target),sha256=common.sha(source)))
    common.write(common.HERE/'installed-binaries-v1.json',dict(binaries=binaries,licenses=licenses,
        installed_assets_sha256=common.sha(common.HERE/'installed-assets-v1.json'),
        raw_source_copies_not_modified=True,real_fits=0,gold_reads=0))
    print('Installed compiled tree assets and license facts frozen; no fitting.')
if __name__=='__main__':main()
