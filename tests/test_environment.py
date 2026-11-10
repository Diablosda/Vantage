"""Default test stores are isolated from real user data and cleaned on exit."""
import atexit,os,tempfile
from pathlib import Path
_temp=None
if not os.environ.get('VANTAGE_DATA_DIR') or not os.environ.get('VANTAGE_CACHE_DIR'):
    _temp=tempfile.TemporaryDirectory(prefix='.vantage-tests-',dir=Path(__file__).resolve().parent)
    os.environ.setdefault('VANTAGE_DATA_DIR',str(Path(_temp.name)/'Data'))
    os.environ.setdefault('VANTAGE_CACHE_DIR',str(Path(_temp.name)/'Cache'))
    atexit.register(_temp.cleanup)
Path(os.environ['VANTAGE_DATA_DIR']).mkdir(parents=True,exist_ok=True)
(Path(os.environ['VANTAGE_CACHE_DIR'])/'Jobs').mkdir(parents=True,exist_ok=True)
